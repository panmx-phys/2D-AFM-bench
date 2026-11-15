"""Synthetic tests for Gwyddion's line-alignment definitions and edge cases."""

import json
from pathlib import Path
import unittest

import numpy as np

from afm_workbench.line_alignment import METHODS, align_lines, gwy_median


class LineAlignmentTests(unittest.TestCase):
    def test_executed_gwyddion_271_reference_outputs(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" / "gwyddion-2.71.json").read_text())
        for case in fixture["alignment"] + fixture["alignment_masked"] + [fixture["matching_si"]]:
            with self.subTest(method=case["method"]):
                mask = np.asarray(case["mask"], dtype=bool) if "mask" in case else None
                result, _ = align_lines(case["input"], mask, method=case["method"],
                                        degree=case.get("degree", 1), trim_fraction=case.get("trim_fraction", .05),
                                        pixel_size=case.get("pixel_size", 1.), value_scale=case.get("value_scale", 1.))
                np.testing.assert_allclose(result, case["output"], rtol=2e-13, atol=5e-13)

    def test_upper_median_and_mean_centered_shifts(self):
        data = np.array([[0., 1, 2, 100], [10, 11, 50, 100]])
        result, model = align_lines(data)
        self.assertEqual(gwy_median([0, 2, 10, 100]), 10)
        np.testing.assert_array_equal(model["offsets"], [-24, 24])
        np.testing.assert_array_equal(result, data - np.array([-24, 24])[:, None])
        self.assertAlmostEqual(result.mean(), data.mean())

    def test_trim_rounding_and_polynomial_zero_mean_alias(self):
        data = np.array([list(range(9)) + [100], list(range(10, 20))], dtype=float)
        # round(0.05*10) = 1, unlike Python's bankers rounding or floor.
        result, model = align_lines(data, method="trimmed_mean", trim_fraction=.05)
        np.testing.assert_allclose(result, data + np.array([5, -5])[:, None])
        mean, _ = align_lines(data, method="mean")
        poly, _ = align_lines(data, method="polynomial", degree=0)
        trim, _ = align_lines(data, method="trimmed_mean", trim_fraction=0)
        np.testing.assert_array_equal(poly, mean)
        np.testing.assert_array_equal(trim, mean)
        np.testing.assert_allclose(mean.mean(axis=1), data.mean())

    def test_difference_methods_preserve_affine_slow_axis_trend(self):
        base = np.array([0., 0, 0, 0, 9, 9, 9, 9])
        offsets = np.array([0., 4, -3, 7, 2])
        data = base + offsets[:, None]
        expected = base + np.array([.6, 1.3, 2., 2.7, 3.4])[:, None]
        for method in ("median_difference", "trimmed_difference"):
            result, model = align_lines(data, method=method)
            np.testing.assert_allclose(result, expected, atol=1e-14)
            self.assertAlmostEqual(sum(model["offsets"]), 0)
        # A lone row and a two-row affine shift have no removable curvature.
        for count in (1, 2):
            result, _ = align_lines(data[:count], method="median_difference")
            np.testing.assert_allclose(result, data[:count])

    def test_difference_mask_uses_boolean_shared_pixels(self):
        offsets = np.array([0., 4, -3, 7, 2])
        data = np.zeros((5, 12)) + offsets[:, None]
        data[:, 6:] += np.arange(5)[:, None] ** 3
        mask = np.zeros(data.shape, bool)
        mask[:, :6] = True
        result, model = align_lines(data, mask, method="median_difference")
        np.testing.assert_allclose(result[:, :6], np.broadcast_to(np.array([.6, 1.3, 2, 2.7, 3.4])[:, None], (5, 6)))
        np.testing.assert_allclose(result[:, 6:] - result[:, :6], data[:, 6:] - data[:, :6])
        self.assertIn("exclusion", model["mask_policy"])

    def test_mask_fallback_is_global_upper_median(self):
        data = np.array([[0., 1, 2, 3, 4], [10, 11, 12, 13, 14], [20, 21, 22, 23, 24]])
        mask = np.ones(data.shape, bool)
        mask[1] = False
        result, model = align_lines(data, mask)
        # Selected population: [0..4,20..24], upper median 20.
        np.testing.assert_allclose(model["offsets"], np.array([2, 20, 22]) - 44/3)
        self.assertAlmostEqual(result.mean(), data.mean())

    def test_modus_densest_interval_and_tie_behavior(self):
        data = np.array([[0., 1, 2, 20, 30, 40, 50, 60, 100],
                         [10, 20, 30, 50, 51, 52, 90, 100, 110]])
        result, model = align_lines(data, method="modus")
        np.testing.assert_allclose(model["offsets"], [-25, 25])
        self.assertAlmostEqual(result.mean(), data.mean())

    def test_polynomial_level_preserves_global_mean_and_reference_features(self):
        x = np.linspace(-1, 1, 21)
        data = np.array([1 + 2*x + x*x, -3 - x + 3*x*x, 20 - 4*x - 2*x*x])
        data[:, 15:] += 15
        mask = np.ones(data.shape, bool)
        mask[:, 15:] = False
        result, model = align_lines(data, mask, method="polynomial", degree=2)
        np.testing.assert_allclose(result[:, :15], data.mean(), atol=2e-14)
        np.testing.assert_allclose(result[:, 15:], data.mean() + 15, atol=2e-14)
        self.assertEqual(model["skipped_lines"], [])

    def test_polynomial_insufficient_reference_keeps_line_unchanged(self):
        data = np.arange(18, dtype=float).reshape(3, 6)
        mask = np.ones(data.shape, bool)
        mask[1, 1:] = False
        result, model = align_lines(data, mask, method="polynomial", degree=2)
        np.testing.assert_array_equal(result[1], data[1])
        self.assertEqual(model["skipped_lines"], [1])
        self.assertTrue(model["warnings"])

    def test_matching_keeps_constant_offset_and_accounts_for_si_scale(self):
        # This surprising no-correction case follows Gwyddion 2.71.
        data = np.array([[0., 1, 4, 6], [10, 11, 14, 16]])
        result, _ = align_lines(data, method="matching")
        np.testing.assert_array_equal(result, data)
        data[1, 1] += 2
        numeric, _ = align_lines(data, method="matching")
        nm, _ = align_lines(data, method="matching", value_scale=1e-9)
        si, _ = align_lines(data * 1e-9, method="matching")
        np.testing.assert_allclose(nm * 1e-9, si, atol=1e-22)
        self.assertGreater(np.max(np.abs(numeric-nm)), .01)

    def test_facet_tilt_removes_ramps_keeps_offsets_and_steps(self):
        x = np.arange(40, dtype=float) - 19.5
        data = np.array([3 + .2*x, 7 - .15*x, 9 + .3*x])
        data[:, 20:] += 10
        result, model = align_lines(data, method="facet_tilt", pixel_size=10)
        expected = np.broadcast_to(np.array([3., 7, 9])[:, None], data.shape).copy()
        expected[:, 20:] += 10
        np.testing.assert_allclose(result, expected, atol=1e-12)
        self.assertEqual(model["backend"]["engine"], "Gwyddion C")
        flat, _ = align_lines(np.full((3, 12), 8.), method="facet_tilt")
        np.testing.assert_array_equal(flat, 8.)

    def test_all_methods_transpose_immutable_invalid_and_serializable(self):
        rng = np.random.default_rng(14)
        data = rng.normal(size=(7, 13)) + np.arange(7)[:, None]
        data[2, 3] = np.nan
        original = data.copy()
        mask = np.ones(data.shape, bool)
        mask[:, -3:] = False
        for method in METHODS:
            rows, model = align_lines(data, mask, method=method)
            columns, _ = align_lines(data.T, mask.T, axis="columns", method=method)
            np.testing.assert_array_equal(rows, columns.T)
            np.testing.assert_array_equal(np.isnan(rows), np.isnan(data))
            self.assertTrue(np.isfinite(rows[np.isfinite(data)]).all())
            np.testing.assert_array_equal(data, original)
            json.dumps(model, allow_nan=False)

    def test_input_validation(self):
        data = np.arange(12).reshape(3, 4)
        for arguments in ({"axis": "auto"}, {"method": "unknown"}, {"degree": True},
                          {"degree": 6}, {"trim_fraction": float("nan")},
                          {"trim_fraction": -.1}, {"value_scale": 0}, {"pixel_size": True}):
            with self.assertRaises(ValueError):
                align_lines(data, **arguments)
        for mask in (np.zeros(data.shape, bool), np.ones((2, 2), bool), np.ones(data.shape)):
            with self.assertRaises(ValueError):
                align_lines(data, mask)


if __name__ == "__main__":
    unittest.main()
