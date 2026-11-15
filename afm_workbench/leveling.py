"""Reference selection for leveling and alignment recipes.

Numerical background fitting is provided by the real Gwyddion C backend.
"""
from __future__ import annotations

import numpy as np


def recipe_reference(array, region_mask, explicit_mask=None, masking="include"):
    """A rectangle alone acts as the mask; with a raster it restricts the ROI."""
    if masking not in {"include", "exclude", "ignore"}:
        raise ValueError("Masking must be include, exclude or ignore.")
    if explicit_mask is None:
        selected = region_mask if masking == "include" else ~region_mask
        if masking == "ignore":
            selected = np.ones(array.shape, dtype=bool)
    else:
        supplied = np.asarray(explicit_mask)
        if supplied.shape != array.shape or supplied.dtype.kind not in "bufi" or not np.isin(supplied, [0, 1]).all():
            raise ValueError("A recipe mask must match the full-resolution image and contain only booleans or 0/1.")
        selected = supplied.astype(bool) if masking == "include" else ~supplied.astype(bool)
        if masking == "ignore":
            selected = np.ones(array.shape, dtype=bool)
        selected &= region_mask
    selected &= np.isfinite(array)
    if not selected.any():
        raise ValueError("The selected reference contains no valid pixel centres.")
    return selected
