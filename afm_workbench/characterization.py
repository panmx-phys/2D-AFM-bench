"""Deterministic three-point preparation; plane membership is an inference.

The existing terrace detector proposes reference support. Three local averages
on one plane define the actual subtracted surface; output pixels are not filtered.
"""
from __future__ import annotations

import base64
import numpy as np

VERSION = '1.0.0'


def three_point_level(array, mask, points, radius=2):
    """Level three averaged square patches in normalized stored-array coordinates."""
    points = np.asarray(points, dtype=float)
    if points.shape != (3, 2) or not np.isfinite(points).all() or np.any((points < 0) | (points > 1)):
        raise ValueError('Choose exactly three points with x and y between 0 and 1.')
    if isinstance(radius, bool) or not isinstance(radius, int) or not 0 <= radius <= 32:
        raise ValueError('Point averaging radius must be a whole number from 0 to 32 pixels.')
    rows, cols = array.shape
    patches = []
    for px, py in points:
        col, row = min(cols - 1, int(px * cols)), min(rows - 1, int(py * rows))
        x0, x1 = max(0, col - radius), min(cols, col + radius + 1)
        y0, y1 = max(0, row - radius), min(rows, row + radius + 1)
        valid = mask[y0:y1, x0:x1] & np.isfinite(array[y0:y1, x0:x1])
        if not valid.any():
            raise ValueError('A leveling point has no valid unmasked reference pixels. Move it onto a clean plane.')
        yy, xx = np.mgrid[y0:y1, x0:x1]
        patches.append({'point': [float(px), float(py)], 'pixel': [col, row],
                        'centroid': [float(((xx + .5) / cols)[valid].mean()),
                                     float(((yy + .5) / rows)[valid].mean())],
                        'mean': float(array[y0:y1, x0:x1][valid].mean()),
                        'pixel_count': int(valid.sum()),
                        'bounds_pixels': [x0, y0, x1, y1]})
    design = np.array([[1, *patch['centroid']] for patch in patches])
    if np.linalg.cond(design) > 100:
        raise ValueError('The three leveling points are too close or nearly collinear. Spread them across the same plane.')
    coefficients = np.linalg.solve(design, [patch['mean'] for patch in patches])
    yy, xx = np.mgrid[:rows, :cols]
    background = coefficients[0] + coefficients[1] * (xx + .5) / cols + coefficients[2] * (yy + .5) / rows
    return array - background, {'method': 'three_averaged_points', 'algorithm_version': VERSION,
                               'coefficients': coefficients.tolist(), 'points': patches,
                               'radius_pixels': radius, 'condition_number': float(np.linalg.cond(design)),
                               'coordinate_frame': 'normalized stored-array pixel centres; x right, y down',
                               'zero_reference': 'plane through the three patch means',
                               'warnings': ['The three points must belong to the same physical reference plane.']}


def auto_characterize(array, mask, metadata, axis='auto', line_correction=True):
    """Align scan lines, detect planes, then select and verify three reference patches.

    Reuses the versioned auto_2d detector without changing old recipe semantics.
    Failure is atomic: the caller receives no partly corrected result.
    """
    from .auto_processing import auto_2d
    # Acquisition quantization is not texture or evidence of extra planes.
    # Apply this floor only to the new operation; old recipes replay unchanged.
    calibration = (metadata or {}).get('calibration', {})
    noise_floor = 0.
    if calibration.get('dtype') and 'slope' in calibration:
        dtype = np.dtype(calibration['dtype'])
        if dtype.kind == 'f':
            noise_floor = float(np.finfo(dtype).eps * np.nanmax(abs(array - calibration.get('intercept', 0.))))
        elif dtype.kind in 'iu':
            noise_floor = abs(float(calibration['slope'])) / 2
    try:
        _, detector = auto_2d(array, mask, metadata, axis, line_correction, noise_floor=noise_floor)
    except ValueError as exc:
        reason = str(exc).split('. ')[0].replace('Automatic 2D material fit failed: ', '')
        raise ValueError(f'Auto preparation could not choose a reliable reference plane: {reason}. '
                         'No correction was applied. Align rows/columns if needed, then choose three points on one plane.') from exc
    corrected = array.copy()
    line = detector['line_correction']
    if line['enabled']:
        offsets = np.array(line['offsets'])
        corrected -= offsets[:, None] if line['axis'] == 'rows' else offsets[None, :]
    assignment = np.frombuffer(base64.b64decode(detector['assignment_uint8_base64']), dtype=np.uint8).reshape(array.shape)
    rows, cols = array.shape
    radius = 2
    yy, xx = np.mgrid[:rows, :cols]
    xx, yy = (xx + .5) / cols, (yy + .5) / rows
    floor = np.finfo(float).eps * max(1., float(np.nanmax(abs(array)))) * 4096
    tolerance = max(3 * detector['texture_sigma'], floor)
    # Largest usable plane first. Pure local patches avoid edges and particles.
    order = sorted(range(detector['plane_count']), key=lambda k: detector['planes'][k]['reference_pixel_count'], reverse=True)
    for plane in order:
        support = mask & (assignment == plane)
        fit = np.array(detector['planes'][plane]['coefficients'])
        residual = corrected - fit[0] - fit[1] * xx - fit[2] * yy
        candidates = []
        for row in np.unique(np.linspace(radius, rows - radius - 1, min(24, rows - 2 * radius), dtype=int)):
            for col in np.unique(np.linspace(radius, cols - radius - 1, min(24, cols - 2 * radius), dtype=int)):
                patch = np.s_[row-radius:row+radius+1, col-radius:col+radius+1]
                if support[patch].all() and np.max(abs(residual[patch])) <= tolerance:
                    candidates.append([(col + .5) / cols, (row + .5) / rows])
        if len(candidates) < 3:
            continue
        candidates = np.array(candidates)
        # Farthest pair, then largest triangle: deterministic broad spatial support.
        distance = ((candidates[:, None] - candidates[None, :]) ** 2).sum(axis=2)
        i, j = np.unravel_index(np.argmax(distance), distance.shape)
        a, b = candidates[i], candidates[j]
        area2 = abs((b[0]-a[0]) * (candidates[:, 1]-a[1]) - (b[1]-a[1]) * (candidates[:, 0]-a[0]))
        k = int(np.argmax(area2))
        if area2[k] < .02:
            continue
        points = candidates[[i, j, k]].tolist()
        try:
            result, model = three_point_level(corrected, mask, points, radius)
        except ValueError:
            continue
        # A triangle fits exactly by construction. Verify against the independent
        # many-pixel fit over the full image extent, not only its three vertices.
        corners = np.array([[1, 0, 0], [1, 1, 0], [1, 0, 1], [1, 1, 1]])
        discrepancy = float(np.max(abs(corners @ (np.array(model['coefficients']) - fit))))
        if discrepancy > tolerance:
            continue
        model.update(method='scan_alignment_and_automatic_three_point_plane', origin='AI', claim_status='proposal',
                     reference_plane=plane, plane_count=detector['plane_count'], planes=detector['planes'],
                     line_correction=line, assignment_shape=list(array.shape),
                     assignment_uint8_base64=detector['assignment_uint8_base64'],
                     assignment_encoding=detector['assignment_encoding'],
                     reference_coverage=detector['reference_coverage'],
                     residual_rms=float(np.sqrt(np.mean(result[support] ** 2))),
                     selection_checks={'triangle_double_area': float(area2[k]), 'minimum_double_area': .02,
                                       'corner_discrepancy': discrepancy, 'maximum_corner_discrepancy': tolerance,
                                       'clean_candidate_count': len(candidates)},
                     detector={'algorithm_version': detector['algorithm_version'], 'quantization_floor': noise_floor, 'gates': detector['gates'],
                               'attempts': detector['attempts'], 'texture_sigma': detector['texture_sigma']},
                     warnings=[detector['warnings'][0],
                               'The selected supported plane defines the reference tilt. Other terrace tilts and height differences remain; this is not an identified substrate.',
                               *detector['warnings'][2:],
                               'Three clean patch means on one inferred plane define the leveling reference; review the numbered points.'])
        return result, model
    raise ValueError('Auto preparation could not choose three reliable, well-spaced points on one plane. '
                     'No correction was applied. Align rows/columns if needed, then choose three points on one plane.')
