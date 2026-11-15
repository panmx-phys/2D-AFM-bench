"""Synthetic analytical checks of the documented Gwyddion 2.71 conventions.

These are independent expectations, not claims of a Gwyddion GUI validation.
Upstream pointers: libprocess/stats.c; libgwyddion/gwymath-rank.c;
libprocess/datafield.c:get_profile_mask; modules/tools/profile.c:update_curve.
"""

import json
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

from afm_workbench.science import profile, statistics, step_height


class GwyddionAnalysisTests(unittest.TestCase):
    def test_executed_upstream_c_reference_statistics(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' / 'gwyddion-2.71.json').read_text())
        case = fixture['statistics']
        actual = statistics(case['input'])
        for key, expected in case['output'].items():
            with self.subTest(metric=key):
                np.testing.assert_allclose(actual[key], expected, rtol=1e-13, atol=1e-13)

    def test_executed_upstream_c_reference_profiles(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' / 'gwyddion-2.71.json').read_text())
        for case in fixture['profiles']:
            with self.subTest(interpolation=case['interpolation'], width=case['width']):
                actual = profile(case['input'], case['width_um'], case['height_um'],
                                 case['start'], case['end'], samples=case['samples'],
                                 interpolation=case['interpolation'], averaging_width_pixels=case['width'])
                np.testing.assert_allclose(actual['values'], case['values'], rtol=1e-13, atol=1e-13)
                np.testing.assert_allclose(actual['distance_um'], case['distance_um'], rtol=1e-13, atol=1e-13)

    def test_population_moments_upper_median_and_relative_extrema(self):
        data = np.array([[0, 1, 1], [4, 9, 10]], dtype=float)
        result = statistics(data)
        mean = Fraction(25, 6)
        moments = {order: sum((Fraction(int(v)) - mean) ** order for v in data.ravel()) / 6
                   for order in (2, 3, 4)}
        self.assertAlmostEqual(result['mean'], float(mean))
        self.assertEqual(result['median'], 4.0)  # Gwyddion's rank n//2, not midpoint 2.5.
        self.assertAlmostEqual(result['variance'], float(moments[2]))
        self.assertAlmostEqual(result['skewness'], float(moments[3]) / float(moments[2]) ** 1.5)
        self.assertAlmostEqual(result['excess_kurtosis'], float(moments[4] / moments[2] ** 2 - 3))
        self.assertAlmostEqual(result['sp'], float(10 - mean))
        self.assertAlmostEqual(result['sv'], float(mean))
        self.assertEqual(result['sz'], 10.0)
        self.assertEqual(result['sz'], result['peak_to_valley'])
        np.testing.assert_array_equal(data, [[0, 1, 1], [4, 9, 10]])

    def test_flat_field_moments_match_gwyddion_convention(self):
        result = statistics(np.full((3, 5), 7.0))
        for key in ('variance', 'sq', 'sa', 'skewness', 'excess_kurtosis', 'sp', 'sv', 'sz'):
            self.assertEqual(result[key], 0.0)
        self.assertEqual(result['median'], 7.0)
        json.dumps(result, allow_nan=False)

    def test_statistics_masks_intersect_roi_and_exclude_invalid(self):
        data = [[1, 2, 100], [3, np.nan, 200]]
        mask = [[0, .5, 1], [1, 0, 1]]
        roi = {'x0': 0, 'x1': 2/3, 'y0': 0, 'y1': 1}
        self.assertEqual(statistics(data, roi, mask)['mean'], 2.5)
        self.assertEqual(statistics(data, roi, mask, 'exclude')['mean'], 1)
        self.assertEqual(statistics(data, roi, mask, 'ignore')['mean'], 2)
        with self.assertRaisesRegex(ValueError, 'no valid'):
            statistics(data, mask=np.zeros((2, 3)))

    def test_profile_default_resolution_matches_tool_pixel_endpoint_rule(self):
        data = np.arange(20, dtype=float).reshape(4, 5)
        # Endpoints are distinct but in one pixel: the tool still uses >=4 samples.
        result = profile(data, 5, 4, [.21, .26], [.29, .30])
        self.assertEqual(result['samples'], 4)
        legacy = profile(data, 5, 4, [.21, .26], [.29, .30], sampling='legacy')
        self.assertEqual(legacy['samples'], 2)
        diagonal = profile(data, 5, 4, [.1, .125], [.9, .875])
        self.assertEqual(diagonal['samples'], 6)  # round(hypot(5, 4))
        self.assertEqual(diagonal['sampling'], 'gwyddion')

    def test_profile_nearest_and_linear_share_pixel_centre_geometry(self):
        data = [[2, 8, 3, 12]]
        nearest = profile(data, 4, 1, [0, .5], [1, .5], 9, interpolation='nearest')
        self.assertEqual(nearest['values'], [2, 2, 8, 8, 3, 3, 12, 12, 12])
        linear = profile(data, 4, 1, [.125, .5], [.875, .5], 7)
        np.testing.assert_allclose(linear['values'], [2, 5, 8, 5.5, 3, 7.5, 12])
        np.testing.assert_allclose(linear['distance_um'], np.linspace(0, 3, 7))

    def test_width_averaging_dense_symmetric_cross_samples(self):
        data = np.tile((np.arange(5, dtype=float) ** 2)[:, None], (1, 8))
        narrow = profile(data, 16, 5, [.2, .5], [.8, .5], 7)
        wide = profile(data, 16, 5, [.2, .5], [.8, .5], 7, averaging_width_pixels=3)
        np.testing.assert_allclose(narrow['values'], 4)
        np.testing.assert_allclose(wide['values'], 46/9, atol=1e-14)
        self.assertEqual(wide['transverse_sample_count'], 9)
        self.assertEqual(wide['averaging_width_pixels'], 3)
        # Changing along-line resolution must not change transverse width.
        denser = profile(data, 16, 5, [.2, .5], [.8, .5], 29, averaging_width_pixels=3)
        np.testing.assert_allclose(denser['values'], 46/9, atol=1e-14)

    def test_profile_mask_holes_remain_at_their_distances(self):
        data = np.tile(np.arange(4, dtype=float), (2, 1))
        mask = [[1, 0, .5, 1], [1, 0, .5, 1]]
        included = profile(data, 4, 2, [.125, .25], [.875, .25], 4, mask=mask, masking='include')
        self.assertEqual(included['values'], [0, None, 2, 3])
        excluded = profile(data, 4, 2, [.125, .25], [.875, .25], 4, mask=mask, masking='exclude')
        self.assertEqual(excluded['values'], [None, 1, 2, None])
        self.assertEqual(excluded['distance_um'], [0, 1, 2, 3])
        self.assertEqual(excluded['invalid_sample_count'], 2)
        json.dumps(excluded, allow_nan=False)

    def test_profile_invalid_values_do_not_pollute_zero_weight_neighbours(self):
        data = [[1, 2, np.nan], [5, 6, 7]]
        result = profile(data, 3, 2, [1/6, .25], [5/6, .25], 3)
        self.assertEqual(result['values'], [1, 2, None])
        result = profile(data, 3, 2, [1/6, .75], [5/6, .75], 3, averaging_width_pixels=2)
        self.assertIsNone(result['values'][-1])
        json.dumps(result, allow_nan=False)

    def test_step_estimator_is_explicitly_distinct_from_fitted_step(self):
        first = {'x0': 0, 'x1': .5, 'y0': 0, 'y1': 1}
        second = {'x0': .5, 'x1': 1, 'y0': 0, 'y1': 1}
        result = step_height([[0, 2, 9, 11], [0, 2, 9, 11]], first, second)
        self.assertEqual(result['difference'], 9)
        self.assertEqual(result['method'], 'two_region_mean_difference')
        self.assertFalse(result['gwyddion_equivalent'])

    def test_new_analysis_parameters_reject_invalid_inputs(self):
        data = np.ones((4, 4))
        for kwargs in ({'averaging_width_pixels': True}, {'averaging_width_pixels': 129},
                       {'interpolation': 'cubic'}, {'sampling': 'something'},
                       {'mask': [[1]]}, {'masking': 'invalid'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                profile(data, 4, 4, [.1, .2], [.9, .8], **kwargs)
        for mask in ([[1]], [[np.nan] * 4] * 4, [[2] * 4] * 4):
            with self.assertRaises(ValueError):
                statistics(data, mask=mask)


if __name__ == '__main__':
    unittest.main()
