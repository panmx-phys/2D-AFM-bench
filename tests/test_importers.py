"""Synthetic Park fixtures authored for this project; no private data required."""
import hashlib
import copy
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from afm_workbench.importers import ImportError, load_scan, map_footprint, LEGACY_POSITION_WARNING


def park_fixture(values, *, dtype=2, version=0x01000002, gain=-2.0,
                 scale=3.0, offset=4.0, unit='um', x_offset=12.0,
                 y_offset=-7.0, angle=30.0, width_um=20.0, height_um=10.0,
                 forward=1, swap=0, edits=None):
    """Construct the independent field-layout fixture from known numeric inputs."""
    values = np.asarray(values)
    header = bytearray(580 if version == 0x01000002 else 356)
    for start, text, length in [(4, 'Z Height', 64), (68, 'Tapping', 16), (244, unit, 16)]:
        encoded = text.encode('utf-16le')
        header[start:start + length] = encoded.ljust(length, b'\0')
    for start, value in [(100, values.shape[1]), (104, values.shape[0]),
                         (128, forward), (132, 1), (136, swap), (348, dtype)]:
        struct.pack_into('<I', header, start, value)
    for start, value in [(108, angle), (140, width_um), (148, height_um),
                         (156, x_offset), (164, y_offset), (220, gain),
                         (228, scale), (236, offset)]:
        struct.pack_into('<d', header, start, value)
    if edits:
        for start, fmt, value in edits:
            struct.pack_into('<' + fmt, header, start, value)
    payload = values.astype({0: '<i2', 1: '<i4', 2: '<f4'}[dtype]).tobytes()
    # Four private tags; a fifth public image-width tag deliberately disagrees.
    count = 5
    payload_offset = 8 + 2 + count * 12 + 4
    header_offset = payload_offset + len(payload)
    entries = [(256, 4, 1, 99), (50432, 4, 1, 0x0E031301),
               (50433, 4, 1, version), (50434, 1, len(payload), payload_offset),
               (50435, 7, len(header), header_offset)]
    return (b'II*\0' + struct.pack('<I', 8) + struct.pack('<H', count)
            + b''.join(struct.pack('<HHII', *e) for e in entries)
            + b'\0' * 4 + payload + header)


class ParkImporterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def load(self, blob, filename='001_scan_Forward_001.tiff'):
        path = Path(self.directory.name) / filename
        path.write_bytes(blob)
        digest = hashlib.sha256(blob).digest()
        result = load_scan(path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest)
        return result

    def test_calibration_gain_scale_offset_units_and_private_dimensions(self):
        values = np.arange(12).reshape(3, 4)
        scan = self.load(park_fixture(values))
        np.testing.assert_array_equal(scan['data'], -2 * (3 * values + 4) * 1000)
        self.assertEqual(scan['data'].dtype, np.float64)
        self.assertEqual(scan['metadata']['width'], 4)
        self.assertEqual(scan['metadata']['height'], 3)
        self.assertEqual(scan['metadata']['value_unit'], 'nm')
        self.assertEqual(scan['metadata']['calibration']['source_tag'], 50434)

    def test_all_supported_dtypes_and_header_versions(self):
        values = np.array([[-12, 9, 4], [327, 1, -7]])
        for dtype, version in [(0, 0x01000001), (0, 0x01000002), (1, 0x01000002), (2, 0x01000002)]:
            with self.subTest(dtype=dtype, version=version):
                result = self.load(park_fixture(values, dtype=dtype, version=version, unit='V'))
                np.testing.assert_array_equal(result['data'], -2 * (3 * values + 4))
                self.assertEqual(result['metadata']['value_unit'], 'V')

    def test_float_precision_phase_units_and_extension_independence(self):
        values = np.array([[0.25, -0.75, 1.5], [2.5, 0.0, 3.0]])
        result = self.load(park_fixture(values, gain=180, scale=1, offset=0, unit='deg'), 'scan.dat')
        np.testing.assert_array_equal(result['data'], values * 180)
        self.assertEqual(result['metadata']['value_unit'], '°')

    def test_position_is_scanner_relative_center(self):
        result = self.load(park_fixture(np.zeros((3, 4))))['metadata']
        self.assertEqual(result['position']['reference'], 'center')
        self.assertEqual(result['position']['coordinate_frame'], 'scanner-relative')
        self.assertTrue(result['position']['calibrated'])
        self.assertEqual((result['position']['x_um'], result['position']['y_um']), (12, -7))
        self.assertEqual(result['position']['rotation_deg'], 30)
        self.assertEqual((result['width_um'], result['height_um']), (20, 10))

    def test_stored_orientation_preserved_and_conflict_explicit(self):
        values = np.arange(6).reshape(2, 3)
        result = self.load(park_fixture(values), '002_scan_Backward_002.tiff')
        np.testing.assert_array_equal(result['data'], -2 * (3 * values + 4) * 1000)
        m = result['metadata']
        self.assertEqual(m['direction'], 'Backward')
        self.assertEqual(m['direction_source'], 'filename label')
        self.assertEqual(m['orientation']['header_fast_direction'], 'Forward')
        self.assertTrue(any('Direction conflict' in w for w in m['warnings']))
        self.assertEqual(m['acquisition'], '002')

    def test_swapped_axes_retain_footprint_without_registering_pixels(self):
        result = self.load(park_fixture(np.zeros((3, 4)), swap=1))
        self.assertTrue(result['metadata']['position']['calibrated'])
        self.assertTrue(result['metadata']['orientation']['swap_fast_slow'])
        self.assertEqual(result['metadata']['orientation']['transform_applied'], 'none')
        self.assertEqual(result['metadata']['orientation']['image_registration'], 'not established')

    def test_map_footprint_recovers_only_known_legacy_axis_exclusion(self):
        meta = self.load(park_fixture(np.zeros((3, 4)), swap=1))['metadata']
        meta['importer_version'] = '1.0.0'
        meta['position']['calibrated'] = False
        meta['warnings'] = [LEGACY_POSITION_WARNING]
        original = copy.deepcopy(meta)
        footprint = map_footprint(meta)
        self.assertTrue(footprint['recovered_legacy_position'])
        self.assertEqual((footprint['x_um'], footprint['y_um'], footprint['rotation_deg']), (12, -7, 30))
        self.assertIn('not registered', footprint['orientation_note'])
        self.assertEqual(meta, original, 'Stored provenance must not be rewritten.')
        for key, value in [('format', 'Other'), ('importer_version', 'unknown'), ('warnings', [])]:
            with self.subTest(key=key):
                changed = copy.deepcopy(meta)
                changed[key] = value
                self.assertIsNone(map_footprint(changed))
        meta['orientation']['swap_fast_slow'] = False
        self.assertIsNone(map_footprint(meta))

    def test_map_footprint_rejects_missing_or_invalid_geometry(self):
        meta = self.load(park_fixture(np.zeros((3, 4))))['metadata']
        for key in ('x_um', 'y_um', 'rotation_deg'):
            for value in (None, float('nan'), float('inf'), '0', True):
                with self.subTest(key=key, value=value):
                    changed = copy.deepcopy(meta)
                    changed['position'][key] = value
                    self.assertIsNone(map_footprint(changed))
        for key in ('width_um', 'height_um'):
            for value in (None, 0, -1, float('inf')):
                changed = copy.deepcopy(meta)
                changed[key] = value
                self.assertIsNone(map_footprint(changed))
        meta['position']['reference'] = 'unknown'
        self.assertIsNone(map_footprint(meta))

    def test_missing_pixels_retained_and_mask_recorded(self):
        result = self.load(park_fixture([[1, np.nan, 2], [3, 4, 5]]))
        self.assertTrue(np.isnan(result['data'][0, 1]))
        self.assertEqual(result['metadata']['invalid_pixel_count'], 1)
        self.assertEqual(result['metadata']['validity_mask'], 'finite(data)')

    def test_reject_generic_tiff_preview(self):
        blob = b'II*\0' + struct.pack('<I', 8) + b'\0' * 6
        with self.assertRaisesRegex(ImportError, 'Park identifier'):
            self.load(blob)

    def test_reject_truncation_and_invalid_directory(self):
        good = park_fixture(np.zeros((3, 4)))
        for blob in [b'', good[:7], good[:30], good[:-1], b'II*\0\xff\xff\xff\xff']:
            with self.subTest(size=len(blob)), self.assertRaises(ImportError):
                self.load(blob)

    def test_reject_invalid_calibration_and_payload_modes(self):
        cases = [dict(gain=0), dict(scale=0), dict(gain=float('nan')),
                 dict(width_um=0), dict(height_um=-1), dict(unit=''),
                 dict(edits=[(272, 'I', 1)]), dict(edits=[(276, 'I', 1)]),
                 dict(edits=[(280, 'I', 1)]), dict(edits=[(0, 'I', 2)]),
                 dict(edits=[(348, 'I', 12)]), dict(edits=[(100, 'I', 5)])]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ImportError):
                self.load(park_fixture(np.zeros((3, 4)), **kwargs))

    def test_reject_infinite_and_all_missing_data(self):
        for value in (float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ImportError):
                self.load(park_fixture(np.full((3, 4), value)))

    def test_unavailable_position_does_not_invent_origin(self):
        m = self.load(park_fixture(np.zeros((3, 4)), x_offset=float('nan')))['metadata']
        self.assertIsNone(m['position']['x_um'])
        self.assertFalse(m['position']['calibrated'])


if __name__ == '__main__':
    unittest.main()
