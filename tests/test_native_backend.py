"""Integration checks for the required Gwyddion shared-library backend.

These tests intentionally do not skip when the native backend is absent: a
configured development/build environment must provide the production engine.
Reference JSON records independently executed upstream C routines.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from afm_workbench.science import apply_recipe, profile, statistics


FIXTURE = Path(__file__).parent / 'fixtures' / 'gwyddion-2.71.json'
ROOT = Path(__file__).resolve().parents[1]


class NativeBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from afm_workbench import native_backend
        cls.native = native_backend
        cls.fixtures = json.loads(FIXTURE.read_text())

    def test_engine_reports_pinned_real_gwyddion_version_and_abi(self):
        description = self.native.describe()
        self.assertEqual({key: description[key] for key in ('engine', 'gwyddion_version', 'adapter_version', 'abi_version')}, {
            'engine': 'Gwyddion C', 'gwyddion_version': '2.71',
            'adapter_version': '1.0.0', 'abi_version': 1,
        })
        self.assertEqual(len(description['adapter_sha256']), 64)
        self.assertEqual(description['gwyddion_source_sha256'], self.fixtures['source_archive_sha256'])
        _, history = apply_recipe([[0., 1., 2.], [3., 4., 5.], [1., 2., 8.]],
                                  [{'type': 'align_rows', 'method': 'median'}])
        self.assertEqual(history[0]['model']['backend'], self.native.describe())

    def test_every_native_alignment_method_matches_executed_reference_both_axes(self):
        cases = self.fixtures['alignment'] + self.fixtures['alignment_masked'] + [self.fixtures['matching_si']]
        self.assertEqual({case['method'] for case in self.fixtures['alignment']},
                         {'mean', 'median', 'median_difference', 'modus', 'matching', 'polynomial',
                          'trimmed_mean', 'trimmed_difference', 'facet_tilt'})
        for case in cases:
            data = np.asarray(case['input'], dtype=float)
            expected = np.asarray(case['output'])
            mask = np.asarray(case['mask'], dtype=bool) if 'mask' in case else None
            parameters = dict(method=case['method'], degree=case.get('degree', 1),
                              trim_fraction=case.get('trim_fraction', .05),
                              pixel_size=case.get('pixel_size', 1.), value_scale=case.get('value_scale', 1.))
            for axis in ('rows', 'columns'):
                with self.subTest(method=case['method'], axis=axis, masked=mask is not None):
                    source = data if axis == 'rows' else data.T
                    selected = mask if axis == 'rows' or mask is None else mask.T
                    untouched = source.copy()
                    result, model = self.native.align_lines(source, selected, axis=axis, **parameters)
                    self.assertEqual(model['backend'], self.native.describe())
                    np.testing.assert_allclose(result if axis == 'rows' else result.T, expected,
                                               rtol=1e-11, atol=1e-11)
                    np.testing.assert_array_equal(source, untouched)

    def test_native_plane_matches_executed_reference_and_preserves_nan(self):
        for case in self.fixtures['planes']:
            with self.subTest(masked=case['mask'] is not None):
                data = np.asarray(case['input'], dtype=float)
                mask = np.ones(data.shape, dtype=bool) if case['mask'] is None else np.asarray(case['mask'], dtype=bool)
                result, _ = self.native.plane_level(data, mask)
                np.testing.assert_allclose(result, case['output'], rtol=1e-12, atol=1e-12)
        y, x = np.mgrid[:7, :10]
        data = 30. + 2*x - 3*y
        data[2, 3] = np.nan
        result, _ = self.native.plane_level(data, np.isfinite(data))
        self.assertTrue(np.isnan(result[2, 3]))
        np.testing.assert_allclose(result[np.isfinite(data)], 29.5, atol=1e-12)

    def test_native_polynomial_analytical_cross_term_mask_and_both_modes(self):
        yy, xx = np.mgrid[:11, :13]
        x, y = 2*xx/12-1, 2*yy/10-1
        reference = xx < 8
        background = 4 + .3*x - .7*y + 2*x*y + .8*x*x*y*y
        data = background + np.where(reference, 0, 7.)
        data[0, 0] = np.nan
        selected = reference & np.isfinite(data)
        out, _ = self.native.polynomial_level(data, selected, mode='independent', degree_x=2, degree_y=2)
        self.assertTrue(np.isnan(out[0, 0]))
        np.testing.assert_allclose(out[selected], 0., atol=2e-11)
        np.testing.assert_allclose(out[~reference], 7., atol=2e-11)
        total, _ = self.native.polynomial_level(background, np.ones(data.shape, dtype=bool), mode='total', degree=4)
        np.testing.assert_allclose(total, 0., atol=2e-11)
        low, _ = self.native.polynomial_level(background, np.ones(data.shape, dtype=bool), mode='total', degree=2)
        self.assertGreater(np.std(low), .02)
        with self.assertRaises(ValueError):
            self.native.polynomial_level(data, yy == 5, mode='total', degree=2)

    def test_native_statistics_reference_and_finite_selection(self):
        case = self.fixtures['statistics']
        native = self.native.statistics_values(np.asarray(case['input']).ravel())
        for key, value in case['output'].items():
            with self.subTest(metric=key):
                np.testing.assert_allclose(native[key], value, rtol=1e-13, atol=1e-13)
        self.assertEqual(native['median'], 4.)
        selected = statistics([[1, np.nan, 100], [3, 5, 200]],
                              {'x0': 0, 'x1': 2/3, 'y0': 0, 'y1': 1})
        self.assertEqual(selected['mean'], 3.)
        self.assertEqual(selected['median'], 3.)
        self.assertEqual(selected['count'], 3)
        flat = self.native.statistics_values(np.full(9, 17.))
        self.assertEqual(flat['sq'], 0.)
        self.assertEqual(flat['skewness'], 0.)
        self.assertEqual(flat['excess_kurtosis'], 0.)

    def test_public_analysis_executes_native_functions(self):
        data = np.arange(20., dtype=float).reshape(4, 5)
        with patch.object(self.native, 'statistics_values', wraps=self.native.statistics_values) as call:
            statistics(data)
        self.assertEqual(call.call_count, 1)
        with patch.object(self.native, 'profile_values', wraps=self.native.profile_values) as call:
            profile(data, 10, 4, [.1, .2], [.9, .8], samples=11, averaging_width_pixels=3)
        self.assertEqual(call.call_count, 1, 'profile values must come from the native engine')

    def test_native_profile_reference_width_interpolation_and_calibration(self):
        for case in self.fixtures['profiles']:
            with self.subTest(interpolation=case['interpolation'], width=case['width']):
                distances, values = self.native.profile_values(
                    case['input'], case['width_um'], case['height_um'], case['start'], case['end'],
                    case['samples'], width=case['width'], interpolation=case['interpolation'])
                np.testing.assert_allclose(values, case['values'], rtol=1e-13, atol=1e-13)
                np.testing.assert_allclose(distances, case['distance_um'], rtol=1e-13, atol=1e-13)
                result = profile(case['input'], case['width_um'], case['height_um'],
                                 case['start'], case['end'], samples=case['samples'],
                                 interpolation=case['interpolation'], averaging_width_pixels=case['width'])
                np.testing.assert_allclose(result['values'], case['values'], rtol=1e-13, atol=1e-13)
                np.testing.assert_allclose(result['distance_um'], case['distance_um'], rtol=1e-13, atol=1e-13)

    def test_native_profile_retains_masked_distance_slots_and_nan_validity(self):
        data = [[1, 2, np.nan, 8], [5, 6, 7, 8]]
        result = profile(data, 4, 2, [.125, .25], [.875, .25], samples=4)
        self.assertEqual(result['values'], [1., 2., None, 8.])
        self.assertEqual(result['distance_um'], [0., 1., 2., 3.])
        mask = [[1, 0, .5, 1], [1, 0, .5, 1]]
        included = profile([[0, 1, 2, 3]] * 2, 4, 2, [.125, .25], [.875, .25],
                           samples=4, mask=mask, masking='include')
        excluded = profile([[0, 1, 2, 3]] * 2, 4, 2, [.125, .25], [.875, .25],
                           samples=4, mask=mask, masking='exclude')
        self.assertEqual(included['values'], [0., None, 2., 3.])
        self.assertEqual(excluded['values'], [None, 1., 2., None])
        self.assertEqual(excluded['invalid_sample_count'], 2)
        empty = profile([[0, 1, 2, 3]] * 2, 4, 2, [.125, .25], [.875, .25],
                        samples=4, mask=np.zeros((2, 4)), masking='include')
        self.assertEqual(empty['values'], [None] * 4)
        self.assertEqual(empty['distance_um'], [0., 1., 2., 3.])
        json.dumps(excluded, allow_nan=False)
        wide = profile(data, 4, 2, [.125, .75], [.875, .75], samples=4, averaging_width_pixels=2)
        self.assertIsNone(wide['values'][2])

    def test_native_alignment_omits_invalid_reference_and_preserves_original(self):
        data = np.array([[0., 1, 2, 3], [8, 9, 10, 11], [-2, -1, 0, 1]])
        data[1, 0] = np.nan
        original = data.copy()
        result, _ = self.native.align_lines(data, np.isfinite(data), method='median')
        expected = data - np.array([-2., 6., -4.])[:, None]
        np.testing.assert_allclose(result, expected, equal_nan=True, atol=1e-13)
        np.testing.assert_array_equal(data, original)

    def test_matching_invalid_endpoint_placeholders_cannot_change_valid_correction(self):
        y, x = np.mgrid[:5, :12]
        data = np.sin(x + .3*y) + .2*x*y + y*y
        data[1, 4] = np.nan
        data[2, 7] = np.nan
        finite = np.isfinite(data)
        # Upstream Matching uses the left endpoint mask for an interval.
        # Suppress intervals touching invalid right endpoints as well.
        effective = finite.copy()
        effective[:, :-1] &= finite[:, 1:]
        for axis in ('rows', 'columns'):
            source = data if axis == 'rows' else data.T
            reference = finite if axis == 'rows' else finite.T
            result, _ = self.native.align_lines(source, reference, axis=axis, method='matching')
            for placeholder in (0., 1e9):
                filled = np.where(finite, data, placeholder)
                if axis == 'columns':
                    filled = filled.T
                mask = effective if axis == 'rows' else effective.T
                comparison, _ = self.native.align_lines(filled, mask, axis=axis, method='matching')
                np.testing.assert_allclose(result[reference], comparison[reference], atol=1e-12)

    def test_native_zero_reference_and_detected_polynomial_failure(self):
        data = np.array([[np.nan, 2., 4.], [6., 8., 10.]])
        selected = np.array([[False, True, True], [True, False, False]])
        for mode, offset in [('mean', 4.), ('min', 2.), ('max', 6.)]:
            result, model = self.native.zero_level(data, selected, mode)
            np.testing.assert_allclose(result, data-offset, equal_nan=True)
            self.assertEqual(model['offset'], offset)
            self.assertEqual(model['backend']['engine'], 'Gwyddion C')
        y, x = np.mgrid[:12, :12] / 11
        data = 1+x+y+x*x*y*y
        original = data.copy()
        # Upstream normal equations can silently return zero coefficients for
        # this ill-conditioned degree; the adapter must not report success.
        try:
            result, _ = self.native.polynomial_level(data, np.ones(data.shape, bool), degree_x=11, degree_y=11)
        except ValueError as error:
            self.assertIn('native calculation failed', str(error))
        else:
            # A different compiler may successfully solve this fit. It must
            # actually subtract the known background rather than silently no-op.
            np.testing.assert_allclose(result, 0, atol=1e-6)
        np.testing.assert_array_equal(data, original)

    def test_missing_explicit_library_fails_without_python_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = str(Path(temporary) / 'missing-gwyddion-library')
            env = {**os.environ, 'AFM_GWY_LIBRARY': library}
            code = ('from afm_workbench.science import statistics; '
                    'print(statistics([[1., 2.], [3., 4.]]))')
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                    text=True, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0, 'missing native library must not silently return Python results')
            self.assertRegex(result.stderr.lower(), r'gwyddion|afm_gwy|native')
            self.assertNotIn("'mean': 2.5", result.stdout)


if __name__ == '__main__':
    unittest.main()
