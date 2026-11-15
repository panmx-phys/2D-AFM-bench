"""Versioned AFM background proposal: scan offsets + up to three terrace planes.

Original NumPy implementation. No filtering is applied to the returned heights.
Background membership is a fitting mask, never a material identification.
"""
from __future__ import annotations
import base64
from collections import deque
import numpy as np
VERSION = '2.0.0'

def _mad(values):
    center = np.median(values)
    return float(1.4826 * np.median(np.abs(values - center)))

def _plane_assign(z, x, y, coefficients):
    labels = np.zeros(z.size, dtype=np.uint8)
    c = coefficients[0]
    distance = abs(z - c[0] - c[1] * x - c[2] * y)
    for (k, c) in enumerate(coefficients[1:], 1):
        d = abs(z - c[0] - c[1] * x - c[2] * y)
        closer = d < distance
        (labels[closer], distance[closer]) = (k, d[closer])
    return (labels, distance)

def _roughness(work, mask, floor):
    """Estimate correlated texture in short locally detrended fast-axis segments. This estimator never filters output data; segment width is recorded."""
    width = min(128, max(8, work.shape[1] // 8))
    n = work.shape[1] // width
    z = work[:, :n * width].reshape(-1, width)
    good = mask[:, :n * width].reshape(-1, width).all(axis=1)
    z = z[good]
    if not len(z):
        raise ValueError('Too little continuous reference support for automatic processing. Use manual leveling.')
    t = np.arange(width) - (width - 1) / 2
    residual = z - z.mean(axis=1)[:, None]
    residual -= (residual @ t / (t @ t))[:, None] * t
    return max(_mad(residual.ravel()), floor)

def _line_background(work, mask, floor, texture):
    """Estimate scan offsets while retaining the median linear tilt and unusually strong coherent full-line jumps. Such jumps are physically ambiguous in a single image; smaller or nonuniform features can still bias line correction."""
    pairs = mask[1:] & mask[:-1]
    if np.any(pairs.sum(axis=1) < max(3, int(work.shape[1] * 0.05))):
        raise ValueError('Automatic scan correction needs shared reference pixels on every line. Widen the Area or disable scan correction.')
    diff = np.where(pairs, np.diff(work, axis=0), np.nan)
    increment = np.nanmedian(diff, axis=1)
    padded = np.pad(increment, 4, mode='edge')
    smooth = np.median(np.lib.stride_tricks.sliding_window_view(padded, 9), axis=1)
    innovation = increment - smooth
    jump_limit = max(8 * _mad(innovation), 4 * texture, floor * 32)
    coherence = np.sum(pairs & (abs(diff - increment[:, None]) <= 4 * texture), axis=1) / pairs.sum(axis=1)
    jumps = (abs(innovation) > jump_limit) & (coherence >= 0.95)
    baseline = float(np.median(increment))
    corrected_increment = np.where(jumps, 0.0, increment - baseline)
    offsets = np.r_[0.0, np.cumsum(corrected_increment)]
    offsets -= np.median(offsets)
    return (work - offsets[:, None], {'method': 'adjacent_line_median_with_jump_protection', 'offsets': offsets.tolist(), 'preserved_boundaries': (np.flatnonzero(jumps) + 1).tolist(), 'boundary_index_frame': 'zero-based first line after boundary', 'jump_threshold': jump_limit, 'retained_linear_increment': baseline, 'reference_pair_counts': pairs.sum(axis=1).tolist(), 'assumption': 'smooth height changes common to an entire fast scan line are treated as scan background; real slow-axis curvature can also be removed'})

def _largest_patch(excluded, mask):
    """Bound coherent unexplained support on an at-most-64 by 64 grid. Local particles may be excluded, but an entire large missing terrace must not be hidden in the outlier mask."""
    (rows, cols) = excluded.shape
    (ys, xs) = (np.linspace(0, rows, min(rows, 64) + 1, dtype=int), np.linspace(0, cols, min(cols, 64) + 1, dtype=int))
    counts = np.zeros((len(ys) - 1, len(xs) - 1), dtype=int)
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            region = np.s_[ys[i]:ys[i + 1], xs[j]:xs[j + 1]]
            total = int(mask[region].sum())
            count = int(excluded[region].sum())
            if total and count > total * 0.5:
                counts[i, j] = count
    largest = 0
    for (i, j) in zip(*np.nonzero(counts)):
        if not counts[i, j]:
            continue
        queue = deque([(i, j)])
        area = int(counts[i, j])
        counts[i, j] = 0
        while queue:
            (a, b) = queue.popleft()
            for (u, v) in ((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)):
                if 0 <= u < counts.shape[0] and 0 <= v < counts.shape[1] and counts[u, v]:
                    area += int(counts[u, v])
                    counts[u, v] = 0
                    queue.append((u, v))
        largest = max(largest, area)
    return largest / int(mask.sum())

def _segments(array, mask, texture, slopes):
    """Segment locally connected plateaus on a median grid after provisional tilt removal. The edge threshold allows local plane slopes, while retaining discontinuous terrace boundaries. Medians only guide segmentation; output pixels are not smoothed."""
    (rows, cols) = array.shape
    (y, x) = np.mgrid[:rows, :cols]
    x = (x + 0.5) / cols
    y = (y + 0.5) / rows
    flat = array - slopes[0] * x - slopes[1] * y
    ys = np.linspace(0, rows, min(64, rows) + 1, dtype=int)
    xs = np.linspace(0, cols, min(64, cols) + 1, dtype=int)
    grid = np.full((len(ys) - 1, len(xs) - 1), np.nan)
    size = np.zeros(grid.shape, dtype=int)
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            a = flat[ys[i]:ys[i + 1], xs[j]:xs[j + 1]]
            m = mask[ys[i]:ys[i + 1], xs[j]:xs[j + 1]]
            if m.sum() >= a.size * 0.5:
                grid[i, j] = np.median(a[m])
                size[i, j] = m.sum()
    differences = np.r_[np.diff(grid, axis=0).ravel(), np.diff(grid, axis=1).ravel()]
    differences = abs(differences[np.isfinite(differences)])
    threshold = max(2.5 * texture, 2 * float(np.percentile(differences, 90))) if differences.size else 2.5 * texture
    labels = np.full(grid.shape, -1, dtype=int)
    groups = []
    for (i, j) in zip(*np.where(np.isfinite(grid))):
        if labels[i, j] >= 0:
            continue
        k = len(groups)
        labels[i, j] = k
        q = deque([(i, j)])
        area = 0
        while q:
            (a, b) = q.popleft()
            area += size[a, b]
            for (u, v) in [(a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)]:
                if 0 <= u < grid.shape[0] and 0 <= v < grid.shape[1] and (labels[u, v] < 0) and np.isfinite(grid[u, v]) and (abs(grid[u, v] - grid[a, b]) <= threshold):
                    labels[u, v] = k
                    q.append((u, v))
        groups.append(area)
    full = np.full(array.shape, -1, dtype=int)
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            full[ys[i]:ys[i + 1], xs[j]:xs[j + 1]] = labels[i, j]
    full[~mask] = -1
    return (full, groups)

def auto_2d(array, mask, metadata, axis='auto', line_correction=True, *, noise_floor=0.):
    """Propose scan background and up to three spatially supported terrace planes. Fit independent terrace slopes, merge compatible disconnected regions, and subtract only the largest supported reference tilt globally. Other terrace tilts and offsets remain. Full-resolution support gates apply after sampled fitting."""
    from .science import scan_line_axis, _robust_difference
    if min(array.shape) < 8:
        raise ValueError('Automatic processing needs at least 8 pixels in each direction; use manual leveling.')
    (rows, cols) = array.shape
    floor = max(noise_floor, np.finfo(float).eps * max(1.0, float(np.nanmax(abs(array)))) * 1024)
    if line_correction:
        (resolved, source) = scan_line_axis(metadata, axis)
        work = array if resolved == 'rows' else array.T
        ref = mask if resolved == 'rows' else mask.T
        initial_texture = _roughness(work, ref, floor)
        (leveled, line) = _line_background(work, ref, floor, initial_texture)
        texture = _roughness(leveled, ref, floor)
        corrected = leveled if resolved == 'rows' else leveled.T
        line.update(axis=resolved, axis_source=source, enabled=True)
    else:
        corrected = array.copy()
        texture = max(_roughness(array, mask, floor), _roughness(array.T, mask.T, floor))
        line = {'enabled': False, 'offsets': [], 'preserved_boundaries': []}
    (y, x) = np.mgrid[:rows, :cols]
    x = (x + 0.5) / cols
    y = (y + 0.5) / rows
    slopes = []
    for (a, size) in ((1, cols), (0, rows)):
        sl = [slice(None), slice(None)]
        sr = sl.copy()
        sl[a] = slice(None, -1)
        sr[a] = slice(1, None)
        (sl, sr) = (tuple(sl), tuple(sr))
        pairs = mask[sl] & mask[sr]
        if pairs.sum() < 3:
            raise ValueError('Insufficient adjacent reference pairs. Use manual leveling.')
        slopes.append(_robust_difference((corrected[sr] - corrected[sl])[pairs])[0] * size)
    (z, xx, yy) = (corrected[mask], x[mask], y[mask])
    (components, areas) = _segments(corrected, mask, texture, slopes)
    selected = [i for i in np.argsort(areas)[::-1] if areas[i] >= max(32, int(mask.sum() * 0.01))]
    if not 1 <= len(selected) <= 32:
        raise ValueError('Automatic 2D material fit failed: fragmented or insufficient reference support. Select a reference Area and use Manual corrections → Level a plane.')
    models = []
    for component in selected:
        region = components[mask] == component
        stride = max(1, int(np.ceil(region.sum() / 32768)))
        (zz, xxx, yyy) = (z[region][::stride], xx[region][::stride], yy[region][::stride])
        design = np.column_stack((np.ones(len(zz)), xxx, yyy))
        coefficients = np.array([np.median(zz - slopes[0] * xxx - slopes[1] * yyy), *slopes])
        for iteration in range(30):
            residual = zz - design @ coefficients
            center = float(np.median(residual))
            scale = max(texture, _mad(residual))
            keep = abs(residual - center) <= 4 * scale
            if keep.sum() < 16 or np.linalg.cond(design[keep]) > 100000.0:
                raise ValueError('Automatic fit has insufficient spatial support. Use Manual corrections → Level a plane.')
            fitted = np.linalg.lstsq(design[keep], zz[keep], rcond=None)[0]
            if np.max(abs(fitted - coefficients)) < max(texture * 1e-05, floor):
                coefficients = fitted
                break
            coefficients = fitted
        models.append(coefficients)
    merged = []
    weights = []
    corners = np.array([[1, 0, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]])
    for (fitted, component) in zip(models, selected):
        weight = areas[component]
        compatible = next((k for (k, c) in enumerate(merged) if np.max(abs(corners @ (c - fitted))) <= 4 * texture), None)
        if compatible is None:
            merged.append(fitted.copy())
            weights.append(weight)
        else:
            merged[compatible] = (merged[compatible] * weights[compatible] + fitted * weight) / (weights[compatible] + weight)
            weights[compatible] += weight
    if len(merged) > 3:
        count = len(line['preserved_boundaries'])
        note = f' {count} ambiguous full-line boundaries were preserved.' if count else ''
        raise ValueError(f'Automatic 2D material fit failed: {len(merged)} distinct candidate planes exceed the limit of 3.{note} Select a reference Area and use Manual corrections → Level a plane.')
    models = merged
    coefficients = np.array(models)
    (labels, d) = _plane_assign(z, xx, yy, coefficients)
    support = d <= 4 * texture
    coeff = coefficients[labels]
    residual = z - coeff[:, 0] - coeff[:, 1] * xx - coeff[:, 2] * yy
    excluded = np.zeros(array.shape, dtype=bool)
    excluded[mask] = ~support
    coverage = float(support.mean())
    patch = _largest_patch(excluded, mask)
    spread = 0.0
    normalized_spread = 0.0
    valid_groups = True
    group_checks = []
    for k in range(len(models)):
        group = (labels == k) & support
        if group.sum() < max(16, int(len(z) * 0.005)):
            valid_groups = False
            break
        medians = []
        for a in range(8):
            for b in range(8):
                tile = group & (xx >= a / 8) & (xx < (a + 1) / 8) & (yy >= b / 8) & (yy < (b + 1) / 8)
                if tile.sum() >= 16:
                    medians.append(float(np.median(residual[tile])))
        if len(medians) >= 4:
            span = float(np.ptp(np.percentile(medians, [10, 90])))
            roughness = max(texture, _mad(residual[group]))
            spread = max(spread, span)
            normalized_spread = max(normalized_spread, span / roughness)
            group_checks.append({'plane': k, 'tile_median_span': span, 'robust_roughness_sigma': roughness})
    good = valid_groups and coverage >= 0.9 and (patch <= 0.015) and (normalized_spread <= 3)
    attempts = [{'plane_count': len(models), 'accepted': bool(good), 'reference_coverage': coverage, 'largest_excluded_patch_fraction': patch, 'tile_median_span': spread, 'normalized_tile_span': normalized_spread, 'plane_checks': group_checks}]
    best = {'coefficients': coefficients, 'centers': coefficients[:, 0]}
    stride = max(1, int(np.ceil(max(areas) / 32768)))
    accepted = (best, labels, support, residual) if good else None
    if accepted is None:
        raise ValueError('Automatic 2D material fit failed: no supported 1–3 terrace-plane model. Data is unchanged. Select a reference Area and use Manual corrections → Level a plane.')
    (best, labels, support, residual) = accepted
    reference_plane = int(np.argmax([((labels == k) & support).sum() for k in range(len(best['centers']))]))
    (bx, by) = best['coefficients'][reference_plane, 1:]
    tilt = bx * x + by * y
    offset = float(np.median((corrected - tilt)[mask][support]))
    assignment = np.full(array.shape, 255, dtype=np.uint8)
    assigned = labels.copy()
    assigned[~support] = 255
    assignment[mask] = assigned
    warnings = ['Fit assignments are background references, not material identities. Features excluded from fitting remain in the output.', 'The largest supported plane defines the reference tilt. Other terrace tilts and height differences are retained; the reference is not identified as substrate.']
    if line_correction:
        warnings.append('Scan correction assumes smooth variation shared by a whole fast-scan line is background. Real slow-axis curvature may also be removed; compare Original or turn scan correction off.')
    if line['preserved_boundaries']:
        warnings.append(f"Preserved {len(line['preserved_boundaries'])} abrupt full-line boundaries; they may be physical steps or acquisition jumps.")
    return (corrected - tilt - offset, {'method': 'robust_scan_background_and_terrace_planes', 'algorithm_version': VERSION, 'claim_status': 'proposal', 'plane_count': len(best['centers']), 'maximum_planes': 3, 'coefficients': [offset, float(bx), float(by)], 'reference_plane': reference_plane, 'planes': [{'coefficients': best['coefficients'][k].tolist(), 'reference_pixel_count': int(((labels == k) & support).sum())} for (k, c) in enumerate(best['centers'])], 'line_correction': line, 'attempts': attempts, 'texture_sigma': texture, 'residual_rms': float(np.sqrt(np.mean(residual[support] ** 2))), 'reference_coverage': float(support.mean()), 'excluded_pixel_count': int((~support).sum()), 'gates': {'residual_cutoff_sigma': 4, 'minimum_coverage': 0.9, 'maximum_excluded_patch_fraction': 0.015, 'maximum_tile_median_span_sigma': 3}, 'fit_sampling_stride': stride, 'texture_segment_pixels': min(128, max(8, (cols if not line_correction or resolved == 'rows' else rows) // 8)), 'assignment_shape': list(array.shape), 'assignment_uint8_base64': base64.b64encode(assignment.tobytes()).decode('ascii'), 'assignment_encoding': 'row-major uint8; 0–2 plane index, 255 excluded or outside reference', 'zero_reference': 'median of supported leveled pixels; not an identified substrate', 'warnings': warnings})
