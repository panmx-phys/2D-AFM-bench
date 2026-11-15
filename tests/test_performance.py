"""Cache correctness and lossless desktop transport, using synthetic data."""
import base64
import json
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from afm_workbench.cache import MemoryCache
from afm_workbench.science import apply_recipe
from afm_workbench.service import Workbench


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workbench = Workbench(self.tmp.name)
        session = self.workbench.demo()
        self.id = next(s['id'] for s in session['scans'] if s['channel'] == 'Z Height')
        self.row = self.workbench._row(self.id)
        self.source = np.load(self.workbench.data_dir / self.row['array_artifact'])
        self.meta = json.loads(self.row['metadata'])
        self.ops = [{'type': 'plane', 'method': 'gwyddion'}]

    def tearDown(self):
        self.workbench.close()
        self.tmp.cleanup()

    def test_result_reused_for_display_measurement_and_identical_prefix(self):
        w = self.workbench
        with patch('afm_workbench.science.apply_recipe', wraps=apply_recipe) as replay:
            w.dispatch('process', {'id': self.id, 'operations': self.ops, 'data_encoding': 'f64le'})
            w.dispatch('display_range', {'id': self.id})
            w.dispatch('scan', {'id': self.id})
            w.dispatch('profile', {'id': self.id, 'start': [0, .5], 'end': [1, .5]})
            self.assertEqual(replay.call_count, 1)
            ops = self.ops + [{'type': 'zero_min', 'method': 'gwyddion'}]
            result = w.dispatch('process', {'id': self.id, 'operations': ops})
            self.assertEqual(replay.call_args.args[1], ops[1:])
        expected, history = apply_recipe(self.source, ops, metadata=self.meta)
        np.testing.assert_array_equal(result['data'], expected)
        self.assertEqual(result['history'], history)
        # Public response histories and arrays cannot corrupt cached results.
        result['history'][0]['model'].clear()
        result['data'][0][0] = 1e99
        self.assertEqual(w.scan(self.id)['history'], history)
        self.assertFalse(w._array(w._row(self.id))[0].flags.writeable)

    def test_changed_earlier_step_eviction_and_restart_equal_full_replay(self):
        w = self.workbench
        w.process(self.id, self.ops)
        changed = [{'type': 'align_rows', 'method': 'median'}, *self.ops]
        expected, history = apply_recipe(self.source, changed, metadata=self.meta)
        result = w.process(self.id, changed)
        np.testing.assert_array_equal(result['data'], expected)
        self.assertEqual(result['history'], history)
        w._results.clear()
        np.testing.assert_array_equal(w.scan(self.id)['data'], expected)
        w.close()
        self.workbench = Workbench(self.tmp.name)
        np.testing.assert_array_equal(self.workbench.scan(self.id)['data'], expected)
        self.assertEqual(self.workbench.scan(self.id)['history'], history)
        np.testing.assert_array_equal(self.workbench.scan(self.id, raw=True)['data'], self.source)

    def test_saved_mask_changes_are_new_keys_and_old_snapshots_survive(self):
        w = self.workbench
        op = [{'type': 'plane', 'method': 'gwyddion', 'use_saved_mask': True}]
        first = w.process(self.id, op)
        w.edit_mask(self.id, 'rectangle', roi={'x0': .1, 'x1': .6, 'y0': .1, 'y1': .8})
        np.testing.assert_array_equal(w.scan(self.id)['data'], first['data'])
        second = w.process(self.id, op)
        self.assertNotEqual(first['operations'], second['operations'])
        expected, history = apply_recipe(self.source, second['operations'], metadata=self.meta)
        np.testing.assert_array_equal(second['data'], expected)
        self.assertEqual(second['history'], history)
        w.update_mask(self.id, masking='include')
        included = w.scan(self.id)
        self.assertNotEqual(included['masked_statistics']['count'], included['statistics']['count'])
        np.testing.assert_array_equal(included['data'], expected)

    def test_thumbnail_cache_tracks_recipe_and_display_without_reprocessing(self):
        w = self.workbench
        first = w.thumbnail(self.id)
        with patch.object(w, '_array', side_effect=AssertionError('Thumbnail rerendered')):
            self.assertEqual(w.thumbnail(self.id), first)
        w.set_display(self.id, {'palette': 'gray'})
        second = w.thumbnail(self.id)
        self.assertNotEqual(second, first)
        w.process(self.id, self.ops)
        self.assertNotEqual(w.thumbnail(self.id), second)
        w.process(self.id, [])
        self.assertEqual(w.thumbnail(self.id), second)

    def test_failed_recipe_and_invalid_encoding_do_not_commit(self):
        w = self.workbench
        first = w.process(self.id, self.ops)
        for extra in ({'type': 'unknown'}, {'type': 'three_point', 'points': [[0, 0]] * 3}):
            with self.assertRaises(ValueError):
                w.process(self.id, self.ops + [extra])
        with self.assertRaises(ValueError):
            w.process(self.id, [], data_encoding='float32')
        self.assertEqual(w.scan(self.id)['history'], first['history'])
        self.assertEqual(w._db.execute('SELECT COUNT(*) FROM runs WHERE scan_id=?', (self.id,)).fetchone()[0], 1)

    def test_compact_pixels_preserve_float64_nan_and_default_json_contract(self):
        w = self.workbench
        values = self.source.copy()
        values[0, :3] = [np.nan, 1000.000000001, -1.2345678901234567e5]
        with w._db:
            scan_id = w._insert_scan(self.row['session_id'], 'precision', 'precision', values, self.meta)
        compact = w.dispatch('scan', {'id': scan_id, 'data_encoding': 'f64le'})
        decoded = np.frombuffer(base64.b64decode(compact['data_base64']), dtype='<f8').reshape(values.shape)
        np.testing.assert_array_equal(decoded, values)
        regular = w.dispatch('scan', {'id': scan_id})
        self.assertIsNone(regular['data'][0][0])
        self.assertNotIn('data_base64', regular)
        self.assertNotIn('data', compact)
        self.assertEqual(compact['statistics'], regular['statistics'])
        json.dumps(compact, allow_nan=False)
        json.dumps(regular, allow_nan=False)

    def test_memory_budget_and_lru_eviction(self):
        cache = MemoryCache(1024, 2)
        cache.put('a', 1, 100)
        cache.put('b', 2, 100)
        self.assertEqual(cache.get('a'), 1)
        cache.put('c', 3, 100)
        self.assertIsNone(cache.get('b'))
        cache.put('large', 4, 2048)
        self.assertIsNone(cache.get('large'))
        self.assertLessEqual(cache.size, cache.max_bytes)
        cache.max_bytes = 1
        cache.clear()
        cache.put('a', 1, 100)
        self.assertIsNone(cache.get('a'))


if __name__ == '__main__':
    unittest.main()
