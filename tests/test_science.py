"""Synthetic ground truth; no laboratory data or external fixtures required."""

import copy
import json
import unittest

import numpy as np

from afm_workbench.science import apply_recipe, profile, statistics, step_height


class ScienceTests(unittest.TestCase):
    def test_known_areal_statistics(self):
        result = statistics(np.array([[0, 2], [4, 6]], dtype=float))
        self.assertEqual(result["mean"], 3)
        self.assertEqual(result["sa"], 2)
        self.assertAlmostEqual(result["sq"], np.sqrt(5))
        self.assertEqual(result["peak_to_valley"], 6)
        self.assertEqual(result["count"], 4)

    def test_masked_statistics_exclude_invalid_and_other_region(self):
        data = np.array([[1, np.nan, 100], [3, 5, 200]])
        result = statistics(data, {"x0": 0, "x1": 2/3, "y0": 0, "y1": 1})
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["mean"], 3)

    def test_plane_ground_truth_and_immutable_input(self):
        y, x = np.mgrid[:11, :15]
        data = 7 + 2 * ((x+.5)/15) - 4 * ((y+.5)/11)
        original = data.copy()
        result, history = apply_recipe(data, [{"type": "plane"}])
        np.testing.assert_allclose(result, 0, atol=1e-13)
        np.testing.assert_array_equal(data, original)
        np.testing.assert_allclose(history[0]["model"]["coefficients"], [7, 2, -4], atol=1e-13)
        self.assertEqual(history[0]["reference"]["valid_pixel_count"], 165)

    def test_background_reference_preserves_raised_feature(self):
        y, x = np.mgrid[:20, :20]
        data = 10 + x*0.5 + y*0.25
        data[:, 10:] += 12
        roi = {"x0": 0, "x1": .5, "y0": 0, "y1": 1}
        result, _ = apply_recipe(data, [{"type": "plane", "roi": roi}])
        np.testing.assert_allclose(result[:, :10], 0, atol=1e-12)
        np.testing.assert_allclose(result[:, 10:], 12, atol=1e-12)

    def test_row_alignment_preserves_feature_with_background_stripe(self):
        offsets = np.array([0, 4, -3, 7, 2])
        data = np.tile(np.array([0, 0, 0, 9, 9, 9]), (5, 1)) + offsets[:, None]
        region = {"x0": 0, "x1": .5, "y0": 0, "y1": 1}
        result, history = apply_recipe(data, [{"type": "align_rows", "roi": region}])
        np.testing.assert_allclose(result[:, :3], 2)
        np.testing.assert_allclose(result[:, 3:], 11)
        self.assertEqual(history[0]["model"]["axis"], "rows")

    def test_column_alignment_uses_correct_axis(self):
        data = np.tile(np.array([0, 4, -3, 7, 2]), (6, 1)).astype(float)
        data[3:] += 9
        region = {"x0": 0, "x1": 1, "y0": 0, "y1": .5}
        result, _ = apply_recipe(data, [{"type": "align_columns", "roi": region}])
        np.testing.assert_allclose(result[:3], 2)
        np.testing.assert_allclose(result[3:], 11)

    def test_alignment_missing_reference_is_rejected(self):
        data = np.arange(24).reshape(4, 6)
        for kind, roi in [
            ("align_rows", {"x0": 0, "x1": 1, "y0": 0, "y1": .5}),
            ("align_columns", {"x0": 0, "x1": .5, "y0": 0, "y1": 1}),
        ]:
            with self.assertRaisesRegex(ValueError, "every"):
                apply_recipe(data, [{"type": kind, "roi": roi}])

    def test_zero_mean_reference_and_invalid_pixel_preservation(self):
        data = np.array([[np.nan, 1, 3], [5, 7, 9]])
        result, _ = apply_recipe(data, [{"type": "zero_mean"}])
        self.assertTrue(np.isnan(result[0, 0]))
        self.assertEqual(statistics(result)["mean"], 0)
        self.assertEqual(statistics(result)["sq"], statistics(data)["sq"])

    def test_replay_determinism_history_json_and_undo(self):
        rng = np.random.default_rng(123)
        data = rng.normal(size=(20, 25)) + np.arange(20)[:, None]
        operations = [{"type": "plane"}, {"type": "align_rows"}, {"type": "zero_mean"}]
        before = copy.deepcopy(operations)
        a, ha = apply_recipe(data, operations)
        b, hb = apply_recipe(data, json.loads(json.dumps(operations)))
        np.testing.assert_array_equal(a, b)
        self.assertEqual(ha, hb)
        json.dumps(ha, allow_nan=False)
        self.assertEqual(before, operations)
        untouched, empty = apply_recipe(data, [])
        np.testing.assert_array_equal(untouched, data)
        self.assertIsNot(untouched, data)
        self.assertEqual(empty, [])

    def test_profile_linear_plane_matches_bilinear_truth(self):
        y, x = np.mgrid[:8, :10]
        data = 3*((x+.5)/10) + 7*((y+.5)/8) + 2
        result = profile(data, 10, 4, [.1, .2], [.9, .8], samples=31)
        expected = 3*np.linspace(.1, .9, 31) + 7*np.linspace(.2, .8, 31) + 2
        np.testing.assert_allclose(result["values"], expected, atol=1e-13)
        self.assertAlmostEqual(result["length_um"], np.hypot(8, 2.4))
        self.assertEqual(result["start_um"], [1, .8])
        self.assertEqual(result["invalid_sample_count"], 0)

    def test_profile_border_and_nan_handling(self):
        data = np.array([[1, 2, np.nan], [4, 5, 6]])
        result = profile(data, 3, 2, [0, .25], [1, .25], samples=7)
        self.assertEqual(result["values"][0], 1)
        self.assertEqual(result["values"][3], 2)
        self.assertIsNone(result["values"][-1])
        json.dumps(result, allow_nan=False)

    def test_known_signed_step_and_population_dispersion(self):
        data = np.array([[1, 3, 11, 13], [1, 3, 11, 13]])
        a = {"x0": 0, "x1": .5, "y0": 0, "y1": 1}
        b = {"x0": .5, "x1": 1, "y0": 0, "y1": 1}
        result = step_height(data, a, b)
        self.assertEqual(result["difference"], 10)
        self.assertEqual(result["region_a"]["sq"], 1)
        self.assertEqual(result["region_b"]["count"], 4)
        self.assertEqual(step_height(data, b, a)["difference"], -10)
        with self.assertRaisesRegex(ValueError, "share"):
            step_height(data, a, a)

    def test_rejects_unsupported_or_degenerate_inputs(self):
        for data in [[], [[np.nan]], [[np.inf]], [1, 2, 3]]:
            with self.assertRaises(ValueError):
                statistics(data)
        with self.assertRaises(ValueError):
            statistics([[1, 2]], {"x0": .8, "x1": .9, "y0": 0, "y1": 1})
        with self.assertRaises(ValueError):
            apply_recipe([[1, 2, 3]], [{"type": "plane"}])
        with self.assertRaises(ValueError):
            apply_recipe([[1, 2], [3, 4]], [{"type": "contrast"}])
        with self.assertRaises(ValueError):
            profile([[1, 2], [3, 4]], 1, 1, [0, 0], [0, 0])
        with self.assertRaises(ValueError):
            profile([[1, 2], [3, 4]], 1, 1, [0, 0], [1, 1], samples=2.5)


if __name__ == "__main__":
    unittest.main()
