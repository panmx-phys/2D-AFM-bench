"""Full-resolution mask editing and display-only range calculations.

Raster mask coordinates match scientific pixel centres in the stored array.
These functions never change calibrated pixel values.
"""
from __future__ import annotations

import math
import numpy as np

from .science import _mask


DEFAULT_DISPLAY = {'palette': 'amber', 'mode': 'full', 'clip_percent': 0.,
                   'minimum': None, 'maximum': None}


def display_settings(settings):
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_DISPLAY):
        raise ValueError('Display settings require palette, mode, clip_percent, minimum and maximum only.')
    result = {**DEFAULT_DISPLAY, **settings}
    if result['palette'] not in {'amber', 'viridis', 'gray'}:
        raise ValueError('Unknown color map.')
    if result['mode'] not in {'full', 'percentile', 'manual'}:
        raise ValueError('Display mode must be full, percentile or manual.')
    clip = result['clip_percent']
    if isinstance(clip, bool) or not isinstance(clip, (int, float)) or not math.isfinite(clip) or not 0 <= clip <= 10:
        raise ValueError('Display clipping must be between 0 and 10 percent per tail.')
    for key in ('minimum', 'maximum'):
        value = result[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError('Color limits must be finite numbers.')
    if result['mode'] == 'manual' and (result['minimum'] is None or result['maximum'] is None or result['minimum'] >= result['maximum']):
        raise ValueError('The minimum color limit must be less than the maximum.')
    return result


def range_info(array, mode='full', clip_percent=2, roi=None):
    if mode not in {'full', 'percentile', 'roi'}:
        raise ValueError('Range mode must be full, percentile or roi.')
    if isinstance(clip_percent, bool) or not isinstance(clip_percent, (int, float)) or not math.isfinite(clip_percent) or not 0 <= clip_percent <= 10:
        raise ValueError('Display clipping must be between 0 and 10 percent per tail.')
    if mode == 'roi' and roi is None:
        raise ValueError('Select a region before using its color range.')
    values = array[_mask(array.shape, roi if mode == 'roi' else None) & np.isfinite(array)]
    if values.size == 0:
        raise ValueError('The color-range reference has no valid pixel centres.')
    clip = clip_percent if mode == 'percentile' else 0
    lower, upper = np.percentile(values, [clip, 100-clip])
    data_lower, data_upper = float(values.min()), float(values.max())
    # A constant image still needs a nonzero interval for a color bar and sliders.
    if lower == upper:
        padding = max(abs(float(lower))*1e-6, 1e-9)
        lower, upper = lower-padding, upper+padding
    counts, edges = np.histogram(array[np.isfinite(array)], bins=64)
    return {'minimum': float(lower), 'maximum': float(upper), 'data_minimum': data_lower,
            'data_maximum': data_upper, 'count': int(values.size), 'mode': mode,
            'clip_percent': clip, 'roi': roi if mode == 'roi' else None,
            'histogram': {'counts': counts.tolist(), 'edges': edges.tolist()},
            'reference': 'full-resolution calibrated values; display only'}


def edit_raster(mask, action, *, roi=None, points=None, radius=None, mode='add', lower=None, upper=None, array=None):
    if mode not in {'add', 'remove', 'replace'}:
        raise ValueError('Mask edit mode must be add, remove or replace.')
    if action == 'clear':
        return np.zeros(mask.shape, dtype=bool)
    if action == 'invert':
        return ~mask
    if action == 'rectangle':
        if roi is None:
            raise ValueError('A rectangle mask requires a region.')
        selected = _mask(mask.shape, roi)
    elif action == 'threshold':
        if array is None:
            raise ValueError('Threshold masking requires numerical image data.')
        for value in (lower, upper):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Mask thresholds must be finite numbers.')
        if lower is None and upper is None:
            raise ValueError('Enter at least one threshold limit.')
        if lower is not None and upper is not None and lower > upper:
            raise ValueError('The lower threshold must not exceed the upper threshold.')
        selected = np.isfinite(array)
        if lower is not None:
            selected &= array >= lower
        if upper is not None:
            selected &= array <= upper
    elif action == 'brush':
        if not isinstance(points, list) or not 1 <= len(points) <= 10000:
            raise ValueError('A brush stroke requires 1–10,000 normalized points.')
        try:
            path = np.asarray(points, dtype=float)
        except (ValueError, TypeError) as exc:
            raise ValueError('Brush points must contain normalized x/y coordinates.') from exc
        if path.shape != (len(points), 2) or not np.isfinite(path).all() or (path < 0).any() or (path > 1).any():
            raise ValueError('Brush points must be finite x/y coordinates between 0 and 1.')
        if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius) or not .5 <= radius <= max(512, *mask.shape):
            raise ValueError('Brush radius must be between half a pixel and the larger of 512 pixels or the image dimensions.')
        path *= [mask.shape[1], mask.shape[0]]
        selected = np.zeros(mask.shape, dtype=bool)
        # Distance to each segment fills fast strokes without gaps. Limit each
        # operation to its bounding box rather than allocating image-sized grids.
        for a, b in zip(path, np.vstack((path[1:], path[-1:]))):
            x0, y0 = np.maximum(0, np.floor(np.minimum(a, b)-radius).astype(int))
            x1, y1 = np.minimum([mask.shape[1], mask.shape[0]], np.ceil(np.maximum(a, b)+radius).astype(int))
            yy, xx = np.mgrid[y0:y1, x0:x1]
            dx, dy = b-a
            norm = dx*dx+dy*dy
            t = np.clip(((xx+.5-a[0])*dx+(yy+.5-a[1])*dy)/norm, 0, 1) if norm else 0
            selected[y0:y1, x0:x1] |= (xx+.5-a[0]-t*dx)**2+(yy+.5-a[1]-t*dy)**2 <= radius*radius
    else:
        raise ValueError('Unknown mask edit action.')
    if mode == 'replace':
        return selected
    return mask | selected if mode == 'add' else mask & ~selected
