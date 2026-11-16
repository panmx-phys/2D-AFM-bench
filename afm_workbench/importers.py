"""Calibrated numerical import; TIFF preview pixels are never analyzed.

The implementation is original. Public format field references are documented
in docs/formats.md. Source files are opened read-only and are never modified.
"""
from __future__ import annotations

import base64
import math
from pathlib import Path
import re
import struct
from typing import Any

import numpy as np


class ImportError(ValueError):
    """A file cannot be safely interpreted as a calibrated AFM image."""


MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_PIXELS = 32 * 1024 * 1024
PARK_MAGIC = 0x0E031301
VERSIONS = {0x01000001: 356, 0x01000002: 580}
TIFF_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2,
              9: 4, 10: 8, 11: 4, 12: 8, 13: 4}
LEGACY_POSITION_WARNING = "Scanner footprint placement is unavailable: non-finite position or swapped fast/slow axes need explicit registration."


def map_footprint(metadata: dict) -> dict | None:
    """Derive an overview footprint without rewriting imported provenance.

    Importer 1.0.0 incorrectly withheld finite Park positions when fast/slow
    axes were swapped. Recover only that identified case. A footprint says
    nothing about image registration; stored pixels are not transformed.
    """
    p = metadata.get('position')
    if not isinstance(p, dict) or p.get('reference') not in ('center', 'corner'):
        return None
    values = [p.get('x_um'), p.get('y_um'), p.get('rotation_deg'),
              metadata.get('width_um'), metadata.get('height_um')]
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        return None
    if values[3] <= 0 or values[4] <= 0:
        return None
    swapped = (metadata.get('orientation') or {}).get('swap_fast_slow') is True
    legacy = (p.get('calibrated') is False and swapped
              and metadata.get('format') == 'Park TIFF'
              and metadata.get('importer_version') == '1.0.0'
              and p.get('source') == 'Park header tag 50435'
              and p.get('reference') == 'center'
              and LEGACY_POSITION_WARNING in metadata.get('warnings', []))
    if p.get('calibrated') is not True and not legacy:
        return None
    return dict(p, calibrated=True, recovered_legacy_position=legacy,
                orientation_note='Fast/slow axes swapped · pixels not registered' if swapped else '')


def _slice(blob: bytes, offset: int, count: int, label: str) -> bytes:
    if offset < 0 or count < 0 or offset + count > len(blob):
        raise ImportError(f"Truncated or invalid {label}.")
    return blob[offset:offset + count]


def _tags(blob: bytes) -> dict[int, tuple[int, int, bytes]]:
    if len(blob) < 8 or blob[:4] != b'II*\x00':
        raise ImportError("Only little-endian classic Park TIFF is supported; this is not a calibrated Park TIFF.")
    offset = struct.unpack_from('<I', blob, 4)[0]
    if offset < 8:
        raise ImportError("Invalid TIFF directory offset.")
    count = struct.unpack('<H', _slice(blob, offset, 2, 'TIFF directory'))[0]
    _slice(blob, offset + 2, count * 12 + 4, 'TIFF directory')
    result = {}
    wanted = {305, 306, 50432, 50433, 50434, 50435, 50436, 50441}
    for index in range(count):
        start = offset + 2 + 12 * index
        tag, kind, length, pointer = struct.unpack_from('<HHII', blob, start)
        if tag not in wanted:
            continue
        if tag in result:
            raise ImportError(f"Duplicate metadata tag {tag}.")
        if kind not in TIFF_SIZES:
            raise ImportError(f"Unsupported TIFF field type {kind} for tag {tag}.")
        size = length * TIFF_SIZES[kind]
        value = _slice(blob, start + 8 if size <= 4 else pointer, size, f'TIFF tag {tag}')
        result[tag] = (kind, length, value)
    return result


def _uint_tag(tags: dict, tag: int) -> int:
    value = tags.get(tag)
    if value is None or value[:2] != (4, 1):
        raise ImportError(f"Missing or invalid Park identifier tag {tag}.")
    return struct.unpack('<I', value[2])[0]


def _text(raw: bytes) -> str:
    try:
        return raw.decode('utf-16le').split('\x00', 1)[0].strip()
    except UnicodeDecodeError as exc:
        raise ImportError("Invalid UTF-16 metadata string.") from exc


def _ascii_tag(tags: dict, tag: int) -> str:
    return tags[tag][2].rstrip(b'\0').decode('utf-8', errors='replace') if tag in tags else ''


def _value_unit(unit: str) -> tuple[str, float]:
    unit = unit.strip().replace('μ', 'µ')
    lengths = {'m': 1e9, 'mm': 1e6, 'um': 1e3, 'µm': 1e3, 'nm': 1.0,
               'pm': 1e-3, 'Å': 0.1, 'Angstrom': 0.1}
    if unit in lengths:
        return 'nm', lengths[unit]
    if unit in {'deg', 'degree', 'degrees', '°'}:
        return '°', 1.0
    if not unit:
        raise ImportError("Missing value unit; numerical calibration cannot be inferred.")
    return unit, 1.0


def load_scan(path: str | Path) -> dict[str, Any]:
    """Read one Park v1/v2 mapped image and retain calibration and source metadata.

    ``data`` is float64 in ``metadata.value_unit``. Stored array row/column
    order is retained; no numerical rotation, flattening, or sign adjustment
    other than the file's explicit calibration is performed.
    """
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ImportError("File exceeds the 512 MiB import limit.")
    blob = path.read_bytes()
    tags = _tags(blob)
    if _uint_tag(tags, 50432) != PARK_MAGIC:
        raise ImportError("TIFF has no recognized Park numerical-data signature. Preview images cannot be analyzed.")
    version = _uint_tag(tags, 50433)
    if version not in VERSIONS:
        raise ImportError(f"Unsupported Park TIFF version 0x{version:08x}.")
    for tag in (50434, 50435):
        if tag not in tags or tags[tag][0] not in (1, 7):
            raise ImportError(f"Missing or invalid numerical-data tag {tag}.")
    header = tags[50435][2]
    if len(header) < VERSIONS[version]:
        raise ImportError("Park image header is truncated.")
    u = lambda offset: struct.unpack_from('<I', header, offset)[0]
    d = lambda offset: struct.unpack_from('<d', header, offset)[0]
    if u(0) != 0:
        raise ImportError("Only 2D mapped Park images are supported; spectroscopy/profile records are not height maps.")
    width, height = u(100), u(104)
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ImportError("Invalid or oversized numerical image dimensions.")
    dtype_code = u(348) if version == 0x01000002 else 0
    dtype = {0: '<i2', 1: '<i4', 2: '<f4'}.get(dtype_code)
    if dtype is None:
        raise ImportError(f"Unsupported Park numerical data type {dtype_code}.")
    if u(272) or u(276) or u(280):
        raise ImportError("Compressed, logarithmic, or squared Park payloads are not supported.")
    payload = tags[50434][2]
    required = width * height * np.dtype(dtype).itemsize
    if len(payload) != required:
        raise ImportError(f"Numerical payload size mismatch: expected {required}, found {len(payload)} bytes.")
    gain, scale, offset = d(220), d(228), d(236)
    if not all(math.isfinite(x) for x in (gain, scale, offset)) or gain == 0 or scale == 0:
        raise ImportError("Missing, zero, or non-finite vertical calibration.")
    width_um, height_um = d(140), d(148)
    if not all(math.isfinite(x) and x > 0 for x in (width_um, height_um)):
        raise ImportError("Missing or invalid lateral calibration.")
    source_unit = _text(header[244:260])
    value_unit, unit_factor = _value_unit(source_unit)
    raw = np.frombuffer(payload, dtype=dtype).reshape(height, width)
    data = (raw.astype(np.float64) * scale + offset) * gain * unit_factor
    if np.isinf(data).any() or not np.isfinite(data).any():
        raise ImportError("Numerical data has no finite values or contains infinities.")
    warnings = []
    invalid_count = int(np.count_nonzero(~np.isfinite(data)))
    if invalid_count:
        warnings.append(f"{invalid_count} missing pixels are retained as NaN.")
    channel = _text(header[4:68]) or 'Unnamed channel'
    header_direction = 'Forward' if u(128) else 'Backward'
    direction_match = re.search(r'(?:^|[_\s-])(Forward|Backward|Trace|Retrace)(?:[_\s.-]|$)', path.name, re.I)
    direction = header_direction
    direction_source = 'Park header fast-scan flag'
    if direction_match:
        hint = direction_match.group(1).lower()
        direction = 'Forward' if hint in ('forward', 'trace') else 'Backward'
        direction_source = 'filename label'
        if direction != header_direction:
            warnings.append(f"Direction conflict: filename says {direction}, Park header says {header_direction}. Filename label is shown; orientation is not inferred from it.")
    acquisition_match = re.match(r'^(\d+)[_\s-]', path.stem)
    acquisition = acquisition_match.group(1) if acquisition_match else path.stem
    x_offset, y_offset, angle = d(156), d(164), d(108)
    swap_xy = bool(u(136))
    position_available = all(math.isfinite(x) for x in (x_offset, y_offset, angle))
    if not position_available:
        warnings.append("Scanner footprint placement is unavailable: position or angle is non-finite.")
    if swap_xy:
        warnings.append("Fast/slow axes are swapped; image pixels are not registered.")
    if u(92):
        warnings.append("Instrument header records automatic flattening; this import preserves the saved numerical payload.")
    def finite(value):
        return value if math.isfinite(value) else None
    metadata = {
        'filename': path.name, 'format': 'Park TIFF', 'importer_version': '1.0.1',
        'channel': channel, 'direction': direction, 'direction_source': direction_source,
        'acquisition': acquisition, 'acquisition_source': 'filename prefix' if acquisition_match else 'filename',
        'width_um': width_um, 'height_um': height_um, 'width': width, 'height': height,
        'value_unit': value_unit, 'instrument': 'Park Systems',
        'acquired_at': _ascii_tag(tags, 306),
        'x_offset_um': finite(x_offset), 'y_offset_um': finite(y_offset),
        'scan_angle_deg': finite(angle),
        'position': {
            'x_um': finite(x_offset), 'y_um': finite(y_offset), 'reference': 'center',
            'rotation_deg': finite(angle), 'calibrated': position_available,
            'coordinate_frame': 'scanner-relative', 'source': 'Park header tag 50435',
            'registration': 'metadata footprint only; stage motion and image registration are not established',
        },
        'calibration': {
            'formula': 'value = gain * (scale * raw + offset) * unit_factor',
            'gain': gain, 'scale': scale, 'offset': offset,
            'source_unit': source_unit, 'output_unit': value_unit, 'unit_factor': unit_factor,
            'slope': gain * scale * unit_factor, 'intercept': gain * offset * unit_factor,
            'dtype': dtype, 'source_tag': 50434,
            'pixel_width_um': width_um / width, 'pixel_height_um': height_um / height,
        },
        'orientation': {
            'array_order': 'stored rows and columns; row 0 is first stored row',
            'transform_applied': 'none', 'scan_angle_deg': finite(angle),
            'header_fast_direction': header_direction,
            'slow_direction': 'Up' if u(132) else 'Down', 'swap_fast_slow': swap_xy,
            'image_registration': 'not established',
        },
        'invalid_pixel_count': invalid_count,
        'validity_mask': 'finite(data)', 'warnings': warnings,
        'original_metadata': {
            'park_version': f'0x{version:08x}', 'header_base64': base64.b64encode(header).decode('ascii'),
            'software': _ascii_tag(tags, 305), 'date_time': _ascii_tag(tags, 306),
            'comments': _ascii_tag(tags, 50436), 'extended_header': _ascii_tag(tags, 50441),
            'source_name': channel, 'image_mode': _text(header[68:84]),
            'auto_flatten': bool(u(92)), 'ac_track': u(96),
            'fast_scan_flag': u(128), 'slow_scan_flag': u(132), 'xy_swap_flag': u(136),
            'x_offset_um': finite(x_offset), 'y_offset_um': finite(y_offset), 'scan_angle_deg': finite(angle),
            'scan_rate_hz': finite(d(172)), 'set_point': finite(d(180)),
            'set_point_unit': _text(header[188:204]), 'tip_bias_v': finite(d(204)),
            'sample_bias_v': finite(d(212)),
        },
    }
    return {'data': data, 'metadata': metadata}
