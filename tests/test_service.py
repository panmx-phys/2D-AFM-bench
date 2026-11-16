"""Integration checks with generated data; no local instrument files required."""
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np

from afm_workbench.importers import load_scan, LEGACY_POSITION_WARNING
from afm_workbench.mcp import handle, serve
from afm_workbench.server import create_server
from afm_workbench.service import Workbench
from test_importers import park_fixture


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workbench = Workbench(self.root / 'catalog')
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.workbench.close()
        # Managed originals are read-only, including on Windows.
        for path in self.root.rglob('*'):
            if path.is_file():
                path.chmod(0o600)
        self.tmp.cleanup()

    def make_folder(self):
        folder = self.root / 'One experimental session'
        folder.mkdir()
        values = np.arange(48, dtype=float).reshape(6, 8)
        for acquisition, direction in [('002', 'Forward'), ('002', 'Backward'), ('003', 'Forward')]:
            (folder / f'{acquisition}__Z Height_{direction}_{acquisition}.tiff').write_bytes(
                park_fixture(values, gain=1, scale=2, offset=3, unit='nm'))
        return folder

    def test_one_folder_one_session_idempotent_import_direction_and_immutable_sources(self):
        folder = self.make_folder()
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
        first = self.workbench.dispatch('import_folder', {'path': str(folder)})
        self.assertEqual(first['scan_count'], 3)
        self.assertEqual({s['acquisition'] for s in first['scans']}, {'002', '003'})
        self.assertEqual({s['direction'] for s in first['scans']}, {'Forward', 'Backward'})
        again = self.workbench.dispatch('import_folder', {'path': str(folder)})
        self.assertEqual(first['id'], again['id'])
        self.assertEqual([s['id'] for s in first['scans']], [s['id'] for s in again['scans']])
        self.assertEqual(len(self.workbench.bootstrap()['sessions']), 1)
        scan_id = first['scans'][0]['id']
        original = self.workbench.scan(scan_id)
        processed = self.workbench.process(scan_id, [{'type':'plane'}])
        self.assertLess(processed['statistics']['sq'], 1e-12)
        np.testing.assert_array_equal(self.workbench.scan(scan_id, raw=True)['data'], original['data'])
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()})
        row = self.workbench._row(scan_id)
        self.assertEqual(hashlib.sha256((self.workbench.data_dir / row['source_artifact']).read_bytes()).hexdigest(), row['sha256'])

    def test_map_footprint_available_for_existing_catalog_without_reimport(self):
        folder = self.make_folder()
        session = self.workbench.import_folder(str(folder))
        scan_id = session['scans'][0]['id']
        row = self.workbench._row(scan_id)
        meta = json.loads(row['metadata'])
        meta['importer_version'] = '1.0.0'
        meta['position']['calibrated'] = False
        meta['orientation']['swap_fast_slow'] = True
        meta['warnings'].append(LEGACY_POSITION_WARNING)
        stored = json.dumps(meta)
        self.workbench._db.execute('UPDATE scans SET metadata=? WHERE id=?', (stored, scan_id))
        self.workbench._db.commit()
        summary = self.workbench.session(session['id'])['scans'][0]
        self.assertTrue(summary['map_footprint']['calibrated'])
        self.assertFalse(summary['position']['calibrated'], 'Original interpretation remains inspectable.')
        detail = self.workbench.scan(scan_id)
        self.assertEqual(detail['map_footprint'], summary['map_footprint'])
        self.assertEqual(detail['metadata'], meta)
        self.assertEqual(self.workbench._row(scan_id)['metadata'], stored)

    def test_background_update_is_responsive_and_cancel_preserves_completed_files(self):
        folder = self.make_folder()
        session = self.workbench.dispatch('import_folder', {'path': str(folder)})
        scan_id = session['scans'][0]['id']
        self.workbench.dispatch('process', {'id': scan_id, 'operations': [{'type': 'plane'}]})
        new_bytes = park_fixture(np.ones((6, 8)), gain=1, scale=2, offset=3, unit='nm')
        (folder / '004__Z Height_Forward.tiff').write_bytes(new_bytes)
        (folder / '005__Z Height_Forward.tiff').write_bytes(new_bytes)
        entered, release, responsive = threading.Event(), threading.Event(), threading.Event()
        def slow_load(path):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test did not release the importer.')
            return load_scan(path)
        with patch('afm_workbench.importers.load_scan', side_effect=slow_load):
            self.workbench.dispatch('start_import', {'path': str(folder)})
            self.assertTrue(entered.wait(2))
            def browse():
                self.workbench.dispatch('bootstrap')
                self.workbench.dispatch('scan', {'id': scan_id})
                self.workbench.thumbnail(scan_id)
                self.workbench.dispatch('list_folders')
                responsive.set()
            reader = threading.Thread(target=browse)
            reader.start()
            try:
                self.assertTrue(responsive.wait(2), 'Import decoding must not hold the catalog lock.')
                status = self.workbench.dispatch('import_status')
                self.assertEqual(status['skipped'], 3)
                with self.assertRaisesRegex(ValueError, 'already running'):
                    self.workbench.dispatch('start_import', {'path': str(folder)})
                self.assertTrue(self.workbench.dispatch('cancel_import')['cancelling'])
            finally:
                release.set()
                reader.join(5)
                self.workbench._import_thread.join(5)
        status = self.workbench.dispatch('import_status')
        self.assertEqual(status['status'], 'cancelled')
        self.assertEqual(status['added'], 1)
        self.assertEqual(self.workbench.session(session['id'])['scan_count'], 4)
        self.assertEqual(self.workbench.scan(scan_id)['operations'], [{'type': 'plane'}])
        self.workbench.dispatch('start_import', {'path': str(folder)})
        self.workbench._import_thread.join(5)
        resumed = self.workbench.dispatch('import_status')
        self.assertEqual(resumed['status'], 'completed')
        self.assertEqual((resumed['added'], resumed['skipped']), (1, 4))
        self.assertEqual(self.workbench.session(session['id'])['scan_count'], 5)

    def test_archive_restore_reconnect_and_source_provenance(self):
        folder = self.make_folder()
        session = self.workbench.import_folder(str(folder))
        scan_id = session['scans'][0]['id']
        original = self.workbench.scan(scan_id)
        self.workbench.dispatch('update_session', {'id': session['id'], 'name': 'Renamed',
                                                   'notes': 'Keep me', 'archived': True})
        self.assertEqual(self.workbench.dispatch('bootstrap')['sessions'], [])
        self.assertIsNone(self.workbench.bootstrap()['active_session_id'])
        self.assertTrue(self.workbench.dispatch('list_folders')[0]['archived'])
        np.testing.assert_array_equal(self.workbench.scan(scan_id)['data'], original['data'])
        moved = folder.rename(self.root / 'Moved session')
        reconnected = self.workbench.dispatch('import_folder', {'path': str(moved), 'session_id': session['id']})
        self.assertEqual(reconnected['id'], session['id'])
        self.assertEqual(reconnected['source_path'], str(moved.resolve()))
        self.assertEqual(reconnected['source_history'][0]['path'], str(folder.resolve()))
        self.assertEqual(reconnected['import_summary']['skipped'], 3)
        self.assertEqual(self.workbench.scan(scan_id)['metadata']['source_path'],
                         str(folder.resolve() / original['filename']))
        other = self.make_folder()
        other_session = self.workbench.import_folder(str(other))
        with self.assertRaisesRegex(ValueError, 'another session'):
            self.workbench.import_folder(str(other), session_id=session['id'])
        self.workbench.dispatch('update_session', {'id': session['id'], 'archived': False})
        self.workbench.close()
        self.workbench = Workbench(self.root / 'catalog')
        restored = self.workbench.session(session['id'])
        self.assertEqual((restored['name'], restored['notes'], restored['scan_count']), ('Renamed', 'Keep me', 3))
        self.assertFalse(restored['archived'])
        self.assertEqual(len(self.workbench.bootstrap()['sessions']), 2)

    def test_folder_schema_migrates_existing_catalog_without_losing_scans(self):
        session = self.workbench.demo()
        self.workbench._db.execute('ALTER TABLE sessions DROP COLUMN archived')
        self.workbench._db.execute('ALTER TABLE sessions DROP COLUMN source_history')
        self.workbench._db.execute('PRAGMA user_version=2')
        self.workbench._db.commit()
        self.workbench.close()
        self.workbench = Workbench(self.root / 'catalog')
        restored = self.workbench.session(session['id'])
        self.assertFalse(restored['archived'])
        self.assertEqual(restored['source_history'], [])
        self.assertEqual([s['id'] for s in restored['scans']], [s['id'] for s in session['scans']])
        self.assertEqual(self.workbench._db.execute('PRAGMA user_version').fetchone()[0], 3)

    def test_failed_import_can_retry_and_does_not_create_empty_session(self):
        self.workbench.dispatch('start_import', {'path': str(self.root / 'missing')})
        self.workbench._import_thread.join(5)
        self.assertEqual(self.workbench.import_status()['status'], 'failed')
        self.assertEqual(self.workbench.bootstrap()['sessions'], [])
        folder = self.make_folder()
        self.workbench.dispatch('start_import', {'path': str(folder)})
        self.workbench._import_thread.join(5)
        self.assertEqual(self.workbench.import_status()['status'], 'completed')
        self.assertEqual(self.workbench.import_status()['added'], 3)

    def test_restore_notes_review_and_recipe_and_replay_undo(self):
        session = self.workbench.demo()
        scan_id = session['scans'][0]['id']
        original = self.workbench.scan(scan_id)['data']
        self.workbench.update_session(session['id'], name='Membranes', notes='Second preparation')
        self.workbench.update_scan(scan_id, starred=True, review_status='reviewed')
        result = self.workbench.process(scan_id, [{'type':'plane'}])
        self.assertEqual(result['review_status'], 'unreviewed')
        self.workbench.close()
        self.workbench = Workbench(self.root / 'catalog')
        restored = self.workbench.scan(scan_id)
        self.assertTrue(restored['starred'])
        self.assertEqual(restored['operations'], [{'type':'plane'}])
        np.testing.assert_allclose(restored['data'], result['data'], rtol=0, atol=0)
        restored_session = self.workbench.session(session['id'])
        self.assertEqual(restored_session['notes'], 'Second preparation')
        undone = self.workbench.process(scan_id, [])
        np.testing.assert_array_equal(undone['data'], original)
        manifest = json.loads(self.workbench.export_scan(scan_id)['content'])
        self.assertEqual(len(manifest['runs']), 2)

    def test_preview_contrast_and_measurement_provenance(self):
        session = self.workbench.demo()
        scan_id = session['scans'][0]['id']
        original = self.workbench.scan(scan_id)
        preview = self.workbench.preview(scan_id, [{'type':'plane'}])
        self.assertTrue(preview['preview'])
        self.assertNotEqual(preview['statistics']['sq'], original['statistics']['sq'])
        self.assertEqual(self.workbench.scan(scan_id)['operations'], [])
        warm = self.workbench.thumbnail(scan_id, contrast='auto')
        gray = self.workbench.thumbnail(scan_id, palette='gray', contrast='full')
        self.assertTrue(warm.startswith(b'\x89PNG'))
        self.assertNotEqual(warm, gray)
        self.assertEqual(self.workbench.scan(scan_id)['statistics'], original['statistics'])
        profile = self.workbench.profile(scan_id, [0,0], [1,1], samples=25)
        self.assertEqual(len(profile['values']), 25)
        region = {'x0':0.,'x1':.5,'y0':0.,'y1':.5}
        area = self.workbench.measure_area(scan_id, region)
        self.assertEqual(area['statistics']['count'], 128*128)
        manifest = json.loads(self.workbench.export_scan(scan_id)['content'])
        self.assertEqual(len(manifest['measurements']), 2)
        self.assertEqual(manifest['measurements'][0]['operations'], [])
        self.assertIn('numpy', manifest['environment'])

    def test_leveled_browse_thumbnail_is_display_only(self):
        session = self.workbench.demo()
        height = next(s for s in session['scans'] if s['value_unit'] == 'nm' and 'height' in s['channel'].lower()
                      and 'error' not in s['channel'].lower())
        before = self.workbench.scan(height['id'])
        stored = self.workbench.thumbnail(height['id'])
        leveled = self.workbench.thumbnail(height['id'], level=True)
        self.assertTrue(leveled.startswith(b'\x89PNG'))
        self.assertNotEqual(stored, leveled)
        after = self.workbench.scan(height['id'])
        self.assertEqual(after['operations'], [])
        self.assertEqual(after['statistics'], before['statistics'])
        np.testing.assert_array_equal(after['data'], before['data'])
        # Saved recipes take precedence: a processed image is never re-leveled for browsing.
        self.workbench.process(height['id'], [{'type': 'plane', 'method': 'gwyddion'}])
        self.assertEqual(self.workbench.thumbnail(height['id'], level=True), self.workbench.thumbnail(height['id']))
        other = next((s for s in session['scans'] if s['value_unit'] != 'nm' or 'height' not in s['channel'].lower()), None)
        if other:
            self.assertEqual(self.workbench.thumbnail(other['id'], level=True), self.workbench.thumbnail(other['id']))

    def test_exports_full_resolution_and_display_only_settings(self):
        session = self.workbench.demo()
        scan_id = session['scans'][0]['id']
        data = self.workbench.scan(scan_id)['data']
        exported = self.workbench.export_scan(scan_id, format='csv')
        np.testing.assert_array_equal(np.loadtxt(io.StringIO(exported['content']), delimiter=','), data)
        settings = {'palette':'gray','range':[-1,2],'raw':False}
        manifest = json.loads(self.workbench.export_scan(scan_id, display=settings)['content'])
        self.assertEqual(manifest['display']['settings'], settings)
        self.assertIn('Display only', manifest['display']['purpose'])
        full = json.loads(self.workbench.export_session(session['id'])['content'])
        self.assertEqual(len(full['scans']), 8)
        self.assertIn('position', full['scans'][0]['metadata'])
        with self.assertRaisesRegex(ValueError, 'preview'):
            self.workbench.export_scan(scan_id, display={'preview':True})

    def test_partial_import_reports_failure_and_new_bytes_do_not_replace_old_scan(self):
        folder = self.make_folder()
        bad = folder / 'bad.tiff'
        bad.write_bytes(b'Not calibrated data')
        session = self.workbench.import_folder(str(folder))
        self.assertEqual(session['scan_count'], 3)
        self.assertEqual(session['import_errors'][0]['filename'], 'bad.tiff')
        source = next(p for p in folder.iterdir() if p.name != 'bad.tiff')
        source.write_bytes(park_fixture(np.ones((6,8)), gain=1, scale=2, offset=3, unit='nm'))
        next_session = self.workbench.import_folder(str(folder))
        self.assertEqual(next_session['id'], session['id'])
        self.assertEqual(next_session['scan_count'], 4)

    def test_mcp_runs_same_core_and_bad_messages_remain_recoverable(self):
        session = self.workbench.demo()
        scan_id = session['scans'][0]['id']
        request = {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'preview_recipe','arguments':{'id':scan_id,'operations':[{'type':'plane'}]}}}
        response = handle(self.workbench, request)
        result = json.loads(response['result']['content'][0]['text'])
        direct = self.workbench.preview(scan_id, [{'type':'plane'}])
        self.assertEqual(result['statistics'], direct['statistics'])
        self.assertNotIn('data', result)
        for params in ([], False, 3, 'text', None):
            error = handle(self.workbench, {'jsonrpc':'2.0','id':2,'method':'tools/call','params':params})
            self.assertEqual(error['error']['code'], -32602)
        bad_arguments = handle(self.workbench, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'inspect_scan','arguments':[]}})
        self.assertTrue(bad_arguments['result']['isError'])
        self.assertEqual(handle(self.workbench, [])['error']['code'], -32600)
        input_stream = io.StringIO('bad json\n[]\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":5,"method":"ping"}\n')
        output = io.StringIO()
        serve(self.workbench, input_stream, output)
        messages = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[-1], {'jsonrpc':'2.0','id':5,'result':{}})

    def test_capped_terrace_fit_preview_save_failure_and_mcp(self):
        folder = self.root / 'terraces'
        folder.mkdir()
        y, x = np.mgrid[:40, :60]
        values = 2 + x / 60 + y / 40 + (x // 20) * 4
        (folder / '001_height.tiff').write_bytes(park_fixture(values, unit='nm', gain=1, scale=1, offset=0))
        bad = values + (y // 20) * 20
        (folder / '002_height.tiff').write_bytes(park_fixture(bad, unit='nm', gain=1, scale=1, offset=0))
        session = self.workbench.import_folder(str(folder))
        good = next(s for s in session['scans'] if s['acquisition'] == '001')
        bad_scan = next(s for s in session['scans'] if s['acquisition'] == '002')
        ops = [{'type': 'terrace_plane'}]
        preview = self.workbench.preview(good['id'], ops)
        self.assertEqual(preview['history'][0]['model']['plane_count'], 3)
        self.assertEqual(self.workbench.scan(good['id'])['operations'], [])
        request = {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
            'name': 'preview_recipe', 'arguments': {'id': good['id'], 'operations': ops}}}
        response = handle(self.workbench, request)
        self.assertEqual(json.loads(response['result']['content'][0]['text'])['statistics'], preview['statistics'])
        saved = self.workbench.process(good['id'], ops)
        self.assertEqual(saved['statistics'], preview['statistics'])
        before = self.workbench.scan(bad_scan['id'])
        for method in (self.workbench.preview, self.workbench.process):
            with self.assertRaisesRegex(ValueError, '1–3'):
                method(bad_scan['id'], ops)
            self.assertEqual(self.workbench.scan(bad_scan['id']), before)
        self.assertEqual(self.workbench.process(good['id'], [])['statistics'], good['statistics'])
        # Existing imported metadata resolves the stored axis on replay.
        aligned = self.workbench.preview(good['id'], [{'type': 'align_scan'}])
        self.assertEqual(aligned['history'][0]['model']['axis'], 'rows')

    def test_auto_2d_shared_service_history_and_rejection(self):
        folder = self.root / 'auto'
        folder.mkdir()
        y, x = np.mgrid[:60, :90]
        values = 2 + x / 90 + y / 60 + (x // 30) * 4
        (folder / '001_height.tiff').write_bytes(park_fixture(values, unit='nm', gain=1, scale=1, offset=0))
        session = self.workbench.import_folder(str(folder))
        scan = session['scans'][0]
        ops = [{'type': 'auto_2d'}]
        preview = self.workbench.preview(scan['id'], ops)
        self.assertEqual(preview['history'][0]['algorithm_version'], '2.0.0')
        self.assertEqual(preview['history'][0]['model']['plane_count'], 3)
        self.assertEqual(preview['history'][0]['model']['line_correction']['axis'], 'rows')
        self.assertEqual(self.workbench.scan(scan['id'])['operations'], [])
        request = {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
            'name': 'preview_recipe', 'arguments': {'id': scan['id'], 'operations': ops}}}
        response = handle(self.workbench, request)
        self.assertEqual(json.loads(response['result']['content'][0]['text'])['statistics'], preview['statistics'])
        self.workbench.process(scan['id'], ops)
        exported = json.loads(self.workbench.export_scan(scan['id'], format='json')['content'])
        self.assertIn('line_correction', exported['history'][0]['model'])
        self.assertEqual(self.workbench.process(scan['id'], [])['statistics'], scan['statistics'])

    def test_http_token_origin_and_thumbnail_access(self):
        try:
            server = create_server(self.workbench)
        except PermissionError:
            self.skipTest('Execution sandbox does not allow binding a loopback socket.')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        def call(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            connection.close()
            return result
        status, headers, body = call('GET','/')
        self.assertEqual(status, 200)
        self.assertIn(server.token.encode(), body)
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        # Every declared frontend dependency must be reachable through the
        # production allowlist, or a new module can prevent the app booting.
        import re
        for asset in re.findall(rb'(?:src|href)="(/[^\"]+)"', body):
            self.assertEqual(call('GET', asset.decode())[0], 200, asset)
        self.assertEqual(call('POST','/api/bootstrap','{}',{'Content-Type':'application/json'})[0], 403)
        auth = {'Content-Type':'application/json','X-AFM-Token':server.token}
        self.assertEqual(call('POST','/api/bootstrap','{}',auth)[0], 200)
        self.assertEqual(call('POST','/api/bootstrap','{}',{**auth,'Origin':'https://example.com'})[0], 403)
        self.assertEqual(call('GET','/',headers={'Host':'attacker.example'})[0], 403)
        self.assertEqual(call('GET','/../catalog.sqlite3')[0], 404)
        self.assertEqual(call('POST','/api/scan','[]',auth)[0], 400)
        session = self.workbench.demo()
        route = '/api/thumbnail/' + session['scans'][0]['id']
        self.assertEqual(call('GET',route)[0], 403)
        png = call('GET',route,headers={'Cookie':headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(png[0],200)
        self.assertTrue(png[2].startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
