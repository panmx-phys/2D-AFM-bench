"""Ground truth and shared-service checks for explicit Gwyddion methods."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from afm_workbench.mcp import handle
from afm_workbench.science import apply_recipe
from afm_workbench.service import Workbench


class GwyddionProcessingTests(unittest.TestCase):
    def test_plane_against_executed_gwyddion_c_reference(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures' / 'gwyddion-2.71.json').read_text())
        for case in fixtures['planes']:
            with self.subTest(masked=case['mask'] is not None):
                operation = {'type': 'plane', 'method': 'gwyddion'}
                if case['mask'] is not None:
                    operation['mask'] = case['mask']
                result, _ = apply_recipe(case['input'], [operation])
                np.testing.assert_allclose(result, case['output'], rtol=1e-12, atol=1e-12)

    def test_plane_uses_gwyddion_pivot_without_zeroing_fitted_intercept(self):
        y, x = np.mgrid[:7, :10]
        data = 30 + 2*x - 3*y
        original = data.copy()
        result, history = apply_recipe(data, [{'type': 'plane', 'method': 'gwyddion'}])
        np.testing.assert_allclose(result, 30 + 2*10/2 - 3*7/2, atol=1e-13)
        np.testing.assert_array_equal(data, original)
        self.assertEqual(history[0]['algorithm_version'], '3.0.0')
        # Historic recipes keep their old zero-reference behavior.
        legacy, old_history = apply_recipe(data, [{'type': 'plane'}])
        np.testing.assert_allclose(legacy, 0, atol=1e-13)
        self.assertEqual(old_history[0]['algorithm_version'], '1.0.0')

    def test_polynomial_degrees_are_distinct_and_background_reconstructs(self):
        y, x = np.mgrid[:15, :19]
        x, y = x/18, y/14
        data = 1 + x + 2*y + 4*x*y + 2*x*x*y*y
        result, history = apply_recipe(data, [{'type': 'polynomial', 'degree_x': 2, 'degree_y': 2}])
        np.testing.assert_allclose(result, 0, atol=1e-13)
        total, _ = apply_recipe(data, [{'type': 'polynomial', 'mode': 'total', 'degree': 2}])
        self.assertGreater(np.std(total), .01)
        model = history[0]['model']
        coeff = np.zeros((3, 3))
        for (i, j), value in zip(model['powers'], model['coefficients']):
            coeff[i, j] = value
        self.assertTrue(model['basis'].startswith('monomial'))
        reconstructed = np.polynomial.polynomial.polygrid2d(np.linspace(-1, 1, 19), np.linspace(-1, 1, 15), coeff).T
        np.testing.assert_allclose(data - reconstructed, result, atol=1e-13)

    def test_mask_include_exclude_ignore_and_nan_reference(self):
        y, x = np.mgrid[:9, :12]
        data = 3. + .2*x - .3*y
        data[:, 8:] += 17
        data[0, 0] = np.nan
        feature = x >= 8
        base = {'type': 'polynomial', 'mode': 'total', 'degree': 1}
        exclude, _ = apply_recipe(data, [{**base, 'mask': feature.tolist(), 'masking': 'exclude'}])
        include, history = apply_recipe(data, [{**base, 'mask': (~feature).tolist()}])
        np.testing.assert_allclose(exclude, include)
        self.assertTrue(np.isnan(include[0, 0]))
        np.testing.assert_allclose(include[:, 8:], 17, atol=1e-13)
        self.assertEqual(history[0]['reference']['valid_pixel_count'], 71)
        roi = {'x0': 2/3, 'y0': 0, 'x1': 1, 'y1': 1}
        via_roi, _ = apply_recipe(data, [{**base, 'roi': roi, 'masking': 'exclude'}])
        np.testing.assert_allclose(via_roi, include)
        ignored, _ = apply_recipe(data, [{**base, 'mask': feature.tolist(), 'masking': 'ignore'}])
        whole, _ = apply_recipe(data, [base])
        np.testing.assert_allclose(ignored, whole)

    def test_zero_extrema_reference_and_invalid_parameters(self):
        data = np.arange(24.).reshape(4, 6)
        for operation, target in [('zero_min', np.min), ('zero_max', np.max), ('zero_mean', np.mean)]:
            corrected, _ = apply_recipe(data, [{'type': operation}])
            self.assertAlmostEqual(target(corrected), 0)
        for op in [
            {'type': 'plane', 'method': 'median'},
            {'type': 'polynomial', 'degree_x': 12},
            {'type': 'polynomial', 'degree': 2},
            {'type': 'polynomial', 'mode': 'total', 'degree_y': 2},
            {'type': 'align_rows', 'degree': 2},
            {'type': 'align_rows', 'method': 'median', 'trim_fraction': .1},
            {'type': 'zero_min', 'mask': [[0, 1]]},
            {'type': 'zero_mean', 'masking': 'bad'},
            {'type': 'align_rows', 'method': 'facet_tilt'},
        ]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                apply_recipe(data, [op])

    def test_line_recipe_transpose_units_and_replay(self):
        y, x = np.mgrid[:8, :16]
        data = .2*x*x + np.sin(x+y) + np.sin(y)*3
        metadata = {'value_unit': 'nm', 'width_um': 8., 'height_um': 4.}
        operations = [{'type': 'align_rows', 'method': 'matching'},
                      {'type': 'align_rows', 'method': 'facet_tilt'}]
        output, history = apply_recipe(data, operations, metadata)
        transposed, _ = apply_recipe(data.T, [{**op, 'type': 'align_columns'} for op in operations],
                                     {'value_unit': 'nm', 'width_um': 4., 'height_um': 8.})
        np.testing.assert_allclose(output, transposed.T, atol=1e-12)
        self.assertEqual(history[0]['model']['value_scale'], 1e-9)
        self.assertAlmostEqual(history[1]['model']['pixel_size'], 500.)
        replay, again = apply_recipe(data, json.loads(json.dumps(operations)), metadata)
        np.testing.assert_array_equal(output, replay)
        self.assertEqual(history, again)
        json.dumps(history, allow_nan=False)

    def test_effective_history_parameters_replay_and_si_prefixes(self):
        y, x = np.mgrid[:8, :16]
        data = np.sin(x*y*.1) + .1*x + y*y
        operations = [
            {'type': 'align_rows', 'method': 'median'},
            {'type': 'align_rows', 'method': 'polynomial', 'degree': 2},
            {'type': 'align_rows', 'method': 'trimmed_difference', 'trim_fraction': .1},
            {'type': 'polynomial', 'mode': 'total', 'degree': 2},
        ]
        output, history = apply_recipe(data, operations)
        reconstructed = [{'type': step['type'], **step['parameters']} for step in history]
        replay, _ = apply_recipe(data, reconstructed)
        np.testing.assert_allclose(replay, output, atol=1e-12)
        for unit, factor in [('µV', 1e-6), ('uA', 1e-6), ('pA', 1e-12), ('mA', 1e-3), ('kHz', 1e3)]:
            _, history = apply_recipe(data, [{'type': 'align_rows', 'method': 'matching'}], {'value_unit': unit})
            self.assertEqual(history[0]['model']['value_scale'], factor)
        _, history = apply_recipe(data, [{'type': 'align_rows', 'method': 'matching'}], {'value_unit': 'counts'})
        self.assertTrue(any('Unrecognized value unit' in warning for warning in history[0]['model']['warnings']))

    def test_gui_service_mcp_mask_profile_and_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            workbench = Workbench(temporary)
            try:
                scan = workbench.demo()['scans'][0]
                original = workbench.scan(scan['id'], raw=True)
                operations = [{'type': 'align_scan', 'axis': 'columns', 'method': 'trimmed_mean', 'trim_fraction': .1},
                              {'type': 'plane', 'method': 'gwyddion'}, {'type': 'zero_mean'}]
                preview = workbench.preview(scan['id'], operations)
                response = handle(workbench, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': 'preview_recipe', 'arguments': {'id': scan['id'], 'operations': operations}}})
                self.assertFalse(response['result']['isError'])
                mcp = json.loads(response['result']['content'][0]['text'])
                self.assertEqual(preview['history'], mcp['history'])
                self.assertEqual(workbench.scan(scan['id'])['operations'], [])
                saved = workbench.process(scan['id'], operations)
                measured = workbench.profile(scan['id'], [.1, .2], [.8, .7], averaging_width_pixels=3, interpolation='nearest')
                self.assertEqual(measured['averaging_width_pixels'], 3)
                self.assertEqual(measured['interpolation'], 'nearest')
                workbench.close()
                workbench = Workbench(temporary)
                self.assertEqual(workbench.scan(scan['id'])['data'], saved['data'])
                self.assertEqual(workbench.scan(scan['id'], raw=True)['data'], original['data'])
                manifest = json.loads(workbench.export_scan(scan['id'], 'json')['content'])
                self.assertEqual(manifest['measurements'][-1]['sampling'], 'gwyddion')
                self.assertEqual(manifest['history'], saved['history'])
            finally:
                workbench.close()


if __name__ == '__main__':
    unittest.main()
