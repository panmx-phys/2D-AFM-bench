"""Multi-terrace ground truth and metadata-directed line correction."""
import base64
import unittest

import numpy as np

from afm_workbench.science import apply_recipe, scan_line_axis


def park_metadata(swap=False, forward='Forward', angle=0):
    return {'format': 'Park TIFF', 'orientation': {
        'transform_applied': 'none', 'swap_fast_slow': swap,
        'header_fast_direction': forward, 'scan_angle_deg': angle}}


class ProcessingTests(unittest.TestCase):
    def surface(self, noisy=False):
        y, x = np.mgrid[:96, :120]
        # Three terraces: none covers a majority. Sloped substrate under all layers.
        layers = (x // 40) * 2.5
        tilt = 13 + 7 * (x + .5) / 120 - 4 * (y + .5) / 96
        noise = np.random.default_rng(18).normal(0, .008, x.shape) if noisy else 0
        return layers + tilt + noise, layers

    def test_multilayer_plane_preserves_all_steps_without_dominant_background(self):
        data, layers = self.surface()
        original = data.copy()
        result, history = apply_recipe(data, [{'type': 'terrace_plane'}])
        np.testing.assert_allclose(result, layers - np.median(layers), atol=1e-12)
        np.testing.assert_array_equal(data, original)
        self.assertEqual(history[0]['model']['plane_count'], 3)
        np.testing.assert_allclose(history[0]['model']['coefficients'][1:], [7, -4], atol=1e-12)
        for pair in history[0]['model']['pairs']:
            bits = np.unpackbits(np.frombuffer(base64.b64decode(pair['mask_packbits_base64']), dtype=np.uint8))
            self.assertEqual(int(bits.sum()), pair['accepted_pairs'])
            self.assertLessEqual(pair['accepted_pairs'], pair['candidate_pairs'])
        replay, replay_history = apply_recipe(data, [{'type': 'terrace_plane'}])
        np.testing.assert_array_equal(replay, result)
        self.assertEqual(history, replay_history)

    def test_noisy_multiterrace_plane_and_invalid_pixels(self):
        data, layers = self.surface(noisy=True)
        data[2, 2] = np.nan
        result, history = apply_recipe(data, [{'type': 'terrace_plane'}])
        self.assertTrue(np.isnan(result[2, 2]))
        np.testing.assert_allclose(history[0]['model']['coefficients'][1:], [7, -4], atol=.025)
        residual = result - layers
        self.assertLess(np.nanstd(residual), .012)

    def test_reference_selects_tilt_without_erasing_outside_features(self):
        data, layers = self.surface()
        roi = {'x0': 0, 'x1': .25, 'y0': 0, 'y1': .4}
        result, _ = apply_recipe(data, [{'type': 'terrace_plane', 'roi': roi}])
        np.testing.assert_allclose(result, layers, atol=1e-12)
        for bad in (np.ones((1, 8)), np.ones((8, 1))):
            with self.assertRaisesRegex(ValueError, 'adjacent reference pairs'):
                apply_recipe(bad, [{'type': 'terrace_plane'}])

    def test_axis_follows_swap_not_angle_or_trace(self):
        for swap in (False, True):
            for direction in ('Forward', 'Backward'):
                for angle in (0, 45, 90):
                    metadata = park_metadata(swap, direction, angle)
                    axis, _ = scan_line_axis(metadata)
                    self.assertEqual(axis, 'columns' if swap else 'rows')
                    y, x = np.mgrid[:30, :40]
                    base = 3 * ((x > 10) & (x < 19) & (y > 8) & (y < 17))
                    offsets = np.sin(np.arange(40 if swap else 30))
                    data = base + (offsets[None, :] if swap else offsets[:, None])
                    result, history = apply_recipe(data, [{'type': 'align_scan'}], metadata)
                    np.testing.assert_allclose(result - np.median(result), base, atol=1e-12)
                    self.assertEqual(history[0]['model']['axis'], axis)

    def test_unknown_axis_requires_override_and_bad_parameters_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not established'):
            apply_recipe(np.ones((8, 9)), [{'type': 'align_scan'}])
        result, history = apply_recipe(np.ones((8, 9)), [{'type': 'align_scan', 'axis': 'columns'}])
        self.assertIn('override', history[0]['model']['axis_source'])
        for op in ({'type': 'align_scan', 'axis': 'diagonal'}, {'type': 'terrace_plane', 'axis': 'rows'}):
            with self.assertRaises(ValueError):
                apply_recipe(np.ones((8, 9)), [op])

    def test_alignment_requires_shared_reference_and_warns_about_full_width_steps(self):
        data = np.zeros((10, 12)); data[5:] = 4
        result, history = apply_recipe(data, [{'type': 'align_scan', 'axis': 'rows'}])
        self.assertTrue(history[0]['model']['warnings'])
        self.assertEqual(np.ptp(result), 0)  # This ambiguity is explicitly disclosed.
        data[3] = np.nan
        with self.assertRaisesRegex(ValueError, 'shared reference'):
            apply_recipe(data, [{'type': 'align_scan', 'axis': 'rows'}])

    def test_smallest_adequate_model_and_no_more_than_three(self):
        y, x = np.mgrid[:60, :90]
        tilt = 1 + 3 * (x + .5) / 90 - 2 * (y + .5) / 60
        for count in (1, 2, 3):
            layers = (x // (90 // count)) * 5
            result, history = apply_recipe(tilt + layers, [{'type': 'terrace_plane'}])
            self.assertEqual(history[0]['model']['plane_count'], count)
            np.testing.assert_allclose(result, layers - np.median(layers), atol=1e-11)
        for extra in ((x // 15) * 5, 8 * (x / 90) ** 2, np.where(x < 45, 0, 2 + x / 90)):
            data = tilt + extra
            original = data.copy()
            with self.assertRaisesRegex(ValueError, 'Manual corrections'):
                apply_recipe(data, [{'type': 'terrace_plane'}])
            np.testing.assert_array_equal(data, original)

    def test_float32_quantization_with_one_zero_directional_mad(self):
        y, x = np.mgrid[:60, :90]
        z = (3 + x / 90 - y / 60 + (x // 30) * 5).astype(np.float32)
        result, history = apply_recipe(z, [{'type': 'terrace_plane'}])
        self.assertEqual(history[0]['model']['plane_count'], 3)
        np.testing.assert_allclose(history[0]['model']['coefficients'][1:], [1, -1], atol=1e-5)
