"""Known surfaces for three-point preparation, and shared-service replay."""
import base64
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from afm_workbench.science import apply_recipe
from afm_workbench.service import Workbench
from afm_workbench.mcp import handle
from test_importers import park_fixture


class CharacterizationTests(unittest.TestCase):
    def surface(self, noise=0):
        y, x = np.mgrid[:96, :192]
        rng = np.random.default_rng(8)
        terraces = (x // 64) * 3.2
        z = 8 + 12 * (x + .5) / 192 - 7 * (y + .5) / 96 + terraces
        return z + noise * rng.normal(size=z.shape), terraces

    def test_three_planes_points_share_clean_support_and_preserve_steps(self):
        z, layers = self.surface(.01)
        z[20:24, 40:44] += 8  # particle must survive
        original = z.copy()
        result, history = apply_recipe(z, [{'type': 'auto_characterize', 'axis': 'rows'}])
        model = history[0]['model']
        self.assertEqual(model['plane_count'], 3)
        self.assertEqual(len(model['points']), 3)
        labels = np.frombuffer(base64.b64decode(model['assignment_uint8_base64']), dtype=np.uint8).reshape(z.shape)
        for point in model['points']:
            x0, y0, x1, y1 = point['bounds_pixels']
            self.assertTrue((labels[y0:y1, x0:x1] == model['reference_plane']).all())
        self.assertAlmostEqual(float(np.median(result[:, 80:110]) - np.median(result[:, 10:30])), 3.2, delta=.01)
        self.assertGreater(result[21, 41] - result[21, 30], 7.9)
        np.testing.assert_array_equal(z, original)
        # Only an offset per row and one plane are subtracted, preserving local texture.
        np.testing.assert_allclose(np.diff(result, axis=1), np.diff(z, axis=1) - model['coefficients'][1] / 192, atol=1e-12)
        replay, replay_history = apply_recipe(z, [{'type': 'auto_characterize', 'axis': 'rows'}])
        np.testing.assert_array_equal(replay, result)
        self.assertEqual(history, replay_history)

    def test_columns_and_exclusion_mask(self):
        z, layers = self.surface()
        z = z.T.copy()
        mask = np.zeros(z.shape, dtype=int)
        mask[:12, :] = 1
        z[:12, :] += 100
        result, history = apply_recipe(z, [{'type': 'auto_characterize', 'axis': 'columns', 'mask': mask.tolist(), 'masking': 'exclude'}])
        model = history[0]['model']
        self.assertEqual(model['line_correction']['axis'], 'columns')
        for p in model['points']:
            self.assertGreaterEqual(p['pixel'][1], 14)
        self.assertAlmostEqual(float(np.median(result[80:110]) - np.median(result[20:40])), 3.2, places=9)
        self.assertGreater(float(np.median(result[:12]) - np.median(result[20:40])), 99)

    def test_manual_points_flatten_tilt_and_have_reproducible_zero(self):
        z, layers = self.surface()
        op = {'type': 'three_point', 'points': [[.05, .1], [.25, .15], [.1, .9]], 'radius': 2}
        result, history = apply_recipe(z, [op])
        np.testing.assert_allclose(result, layers, atol=1e-12)
        self.assertEqual(history[0]['parameters']['points'], op['points'])
        self.assertEqual(history[0]['model']['points'][0]['pixel_count'], 25)

    def test_plane_only_retains_other_terrace_slope_and_unknown_axis_fails(self):
        y, x = np.mgrid[:96, :192]
        xx, yy = (x + .5) / 192, (y + .5) / 96
        other_plane = np.where(x > 125, 3 + .6 * yy, 0)
        z = 4 + 3 * xx - 2 * yy + other_plane
        result, history = apply_recipe(z, [{'type':'auto_characterize', 'line_correction':False}])
        self.assertFalse(history[0]['model']['line_correction']['enabled'])
        np.testing.assert_allclose(result, other_plane, atol=1e-12)
        with self.assertRaisesRegex(ValueError, 'No correction was applied'):
            apply_recipe(z, [{'type':'auto_characterize'}])

    def test_bad_points_invalid_pixels_and_masks(self):
        z, _ = self.surface()
        for points in ([[.1,.1],[.2,.2],[.3,.3]], [[0,0],[1,1]], [[0,0],[1,1],[2,1]]):
            with self.assertRaises(ValueError):
                apply_recipe(z, [{'type':'three_point', 'points':points}])
        z[:20, :30] = np.nan
        with self.assertRaisesRegex(ValueError, 'no valid'):
            apply_recipe(z, [{'type':'three_point', 'points':[[.05,.1],[.2,.1],[.1,.9]]}])
        with self.assertRaisesRegex(ValueError, 'radius'):
            apply_recipe(z, [{'type':'three_point', 'points':[[.2,.2],[.3,.2],[.2,.9]], 'radius':1.2}])

    def test_ambiguous_planes_and_curvature_fail_without_mutation(self):
        y, x = np.mgrid[:96, :192]
        for z in (x/192 + (x//32)*2., 8*(x/192)**2):
            original = z.copy()
            with self.assertRaisesRegex(ValueError, 'No correction was applied'):
                apply_recipe(z, [{'type':'auto_characterize', 'axis':'rows'}])
            np.testing.assert_array_equal(z, original)

    def test_manual_mask_and_nan_preservation(self):
        z, layers = self.surface()
        z[40, 20] = np.nan
        mask = np.zeros(z.shape, dtype=int); mask[8:12, 8:12] = 1
        op = {'type':'three_point','points':[[.05,.1],[.25,.15],[.1,.9]],'mask':mask.tolist(),'masking':'exclude'}
        result, _ = apply_recipe(z, [op])
        self.assertTrue(np.isnan(result[40,20]))
        np.testing.assert_allclose(result[np.isfinite(z)], layers[np.isfinite(z)], atol=1e-12)

    def test_service_mcp_preview_failure_and_saved_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'input'; folder.mkdir()
            z, _ = self.surface()
            (folder/'001_Z Height.tiff').write_bytes(park_fixture(z, unit='nm', gain=1, scale=1, offset=0))
            workbench = Workbench(Path(tmp)/'catalog')
            try:
                scan = workbench.import_folder(str(folder))['scans'][0]
                identifier = scan['id']; ops = [{'type':'auto_characterize','axis':'rows'}]
                preview = workbench.preview(identifier, ops)
                reply = handle(workbench, {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'preview_recipe','arguments':{'id':identifier,'operations':ops}}})
                self.assertFalse(reply['result']['isError'])
                mcp = json.loads(reply['result']['content'][0]['text'])
                self.assertEqual(preview['history'], mcp['history'])
                self.assertEqual(workbench.scan(identifier)['operations'], [])
                before_display = workbench.scan(identifier)['display']
                workbench.display_range(identifier, operations=ops, mode='roi', roi={'x0':.1,'x1':.2,'y0':.1,'y1':.9})
                self.assertEqual(workbench.scan(identifier)['display'], before_display)
                saved = workbench.process(identifier, ops)
                with self.assertRaises(ValueError):
                    workbench.process(identifier, ops+[{'type':'three_point','points':[[0,0],[.5,.5],[1,1]]}])
                self.assertEqual(workbench.scan(identifier)['history'], saved['history'])
                np.testing.assert_array_equal(workbench.scan(identifier)['data'], preview['data'])
                manifest = json.loads(workbench.export_scan(identifier)['content'])
                self.assertIn('scan_alignment_and_automatic_three_point_plane', json.dumps(manifest))
                self.assertIn('bounds_pixels', json.dumps(manifest))
            finally:
                workbench.close()
                for path in Path(tmp).rglob('*'):
                    if path.is_file(): path.chmod(0o600)


if __name__ == '__main__':
    unittest.main()
