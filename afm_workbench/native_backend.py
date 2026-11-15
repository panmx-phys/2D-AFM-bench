"""Gwyddion C scientific backend; no numerical fallback on load/fitting errors.

Python owns validation, coordinates, invalid-pixel policy and provenance. The
output arrays and statistical values below are computed by real Gwyddion C
objects through the versioned ABI in native/afm_gwyddion.h.
"""
from __future__ import annotations

import ctypes
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

ADAPTER_VERSION = "1.0.0"
METHODS = {"mean": 0, "median": 1, "median_difference": 2, "modus": 3,
           "matching": 4, "trimmed_mean": 5, "trimmed_difference": 6,
           "facet_tilt": 7, "polynomial": 8}
_DOUBLE = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
_INT = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")


@lru_cache(maxsize=1)
def _library():
    suffix = ".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"
    filename = ("afm_gwyddion" if sys.platform == "win32" else "libafm_gwyddion") + suffix
    path = Path(os.environ.get("AFM_GWY_LIBRARY", str(Path(__file__).parent / "_native" / filename)))
    try:
        if sys.platform == "win32":
            # Keep the handle alive for the lifetime of the loaded DLL.
            _library.dll_directory = os.add_dll_directory(str(path.resolve().parent))
        library = ctypes.CDLL(str(path))
    except (OSError, FileNotFoundError) as exc:
        raise ValueError("Gwyddion native backend is unavailable. Build it with scripts/build_gwyddion.py "
                         "as described in native/README.md, or set AFM_GWY_LIBRARY to the built adapter.") from exc
    library.afm_gwyddion_abi_version.restype = ctypes.c_int
    library.afm_gwyddion_version.restype = ctypes.c_char_p
    if library.afm_gwyddion_abi_version() != 1 or library.afm_gwyddion_version().decode() != "2.71":
        raise ValueError("Unsupported Gwyddion backend: this application requires adapter ABI 1 and Gwyddion 2.71.")
    library.afm_gwyddion_init.restype = ctypes.c_int
    _check(library.afm_gwyddion_init(), "initialization")
    field = [_DOUBLE, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double]
    library.afm_gwyddion_align.argtypes = field + [ctypes.c_int]*3 + [ctypes.c_double, _DOUBLE, _DOUBLE]
    library.afm_gwyddion_plane.argtypes = field + [_DOUBLE, _DOUBLE]
    library.afm_gwyddion_zero.argtypes = field + [ctypes.c_int, _DOUBLE, _DOUBLE]
    library.afm_gwyddion_polynomial.argtypes = field + [ctypes.c_int]*4 + [_DOUBLE, _DOUBLE, _INT, ctypes.POINTER(ctypes.c_int)]
    library.afm_gwyddion_stats.argtypes = field + [_DOUBLE]
    library.afm_gwyddion_profile.argtypes = field + [ctypes.c_double]*4 + [ctypes.c_int]*3 + [_DOUBLE, _DOUBLE, ctypes.POINTER(ctypes.c_int)]
    for name in ("align", "plane", "polynomial", "stats", "profile", "zero"):
        getattr(library, "afm_gwyddion_" + name).restype = ctypes.c_int
    library.workbench_binary_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = path.parent / "build-manifest.json"
    library.workbench_source_sha256 = (json.loads(manifest.read_text()).get("upstream_sources", {}).get("gwyddion", {}).get("sha256")
                                      if manifest.exists() else None)
    return library


def describe():
    library = _library()
    return {"engine": "Gwyddion C", "gwyddion_version": library.afm_gwyddion_version().decode(),
            "adapter_version": ADAPTER_VERSION, "abi_version": library.afm_gwyddion_abi_version(),
            "adapter_sha256": library.workbench_binary_sha256,
            "gwyddion_source_sha256": library.workbench_source_sha256}


def _check(status, operation):
    errors = {1: "invalid native argument", 2: "insufficient independent reference pixels",
              3: "nonfinite native output", 4: "native calculation failed"}
    if status:
        raise ValueError(f"Gwyddion {operation}: {errors.get(status, 'unknown native status')}. Input is unchanged.")


def _inputs(data, reference_mask=None):
    source = np.asarray(data, dtype=np.float64)
    if source.ndim != 2 or min(source.shape) == 0 or np.isinf(source).any() or not np.isfinite(source).any():
        raise ValueError("A nonempty finite/NaN image is required.")
    finite = np.isfinite(source)
    selected = finite.copy()
    if reference_mask is not None:
        reference = np.asarray(reference_mask)
        if reference.shape != source.shape or reference.dtype != bool:
            raise ValueError("Reference must be a boolean array matching the image.")
        selected &= reference
    if not selected.any():
        raise ValueError("The selected reference contains no valid pixels.")
    # Excluded NaNs cannot enter C arithmetic (0*NaN is NaN). Mean filling
    # retains the whole-field mean used by row polynomial leveling; the mask
    # excludes these placeholders from fitting and NaNs are restored afterward.
    prepared = np.ascontiguousarray(np.where(finite, source, np.mean(source[finite])))
    mask = np.ascontiguousarray(selected, dtype=np.float64)
    return source, prepared, finite, selected, mask


def _mask_pointer(mask):
    return None if np.all(mask) else mask.ctypes.data


def statistics_values(values):
    values = np.ascontiguousarray(np.asarray(values, dtype=np.float64).reshape(1, -1))
    if not values.size or not np.isfinite(values).all():
        raise ValueError("Statistics require at least one finite selected value.")
    output = np.empty(9)
    _check(_library().afm_gwyddion_stats(values, None, 1, values.size, float(values.size), 1., output), "statistics")
    mean, sa, sq, skew, kurtosis, median, low, high, count = map(float, output)
    return {"mean": mean, "sa": sa, "sq": sq, "variance": sq*sq,
            "skewness": skew, "excess_kurtosis": kurtosis, "median": median,
            "min": low, "max": high, "sp": high-mean, "sv": mean-low,
            "sz": high-low, "peak_to_valley": high-low, "count": int(count)}


def align_lines(data, reference_mask=None, axis="rows", method="median", degree=1,
                trim_fraction=.05, pixel_size=1., value_scale=1.):
    if not isinstance(axis, str) or axis not in {"rows", "columns"}:
        raise ValueError("Line axis must be rows or columns.")
    if not isinstance(method, str) or method not in METHODS:
        raise ValueError("Unknown line alignment method.")
    if isinstance(degree, bool) or not isinstance(degree, (int, np.integer)) or not 0 <= degree <= 5:
        raise ValueError("Line polynomial degree must be an integer from 0 to 5.")
    if isinstance(trim_fraction, bool) or not isinstance(trim_fraction, (int, float)) or not math.isfinite(trim_fraction) or not 0 <= trim_fraction <= .5:
        raise ValueError("Trim fraction must be from 0 to 0.5.")
    for value in (pixel_size, value_scale):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Pixel size and value scale must be finite positive values.")
    source, prepared, finite, selected, mask = _inputs(data, reference_mask)
    rows, cols = source.shape
    if method == "matching" and not finite.all():
        # Upstream matches intervals using their left endpoint's mask. Suppress
        # the preceding endpoint of every invalid pixel, so its placeholder
        # cannot influence the interval derivative or endpoint weights.
        if axis == "rows":
            selected[:, :-1] &= finite[:, 1:]
        else:
            selected[:-1, :] &= finite[1:, :]
        mask = np.ascontiguousarray(selected, dtype=np.float64)
        if not selected.any():
            raise ValueError("Matching has no valid adjacent reference intervals.")
    prepared = np.ascontiguousarray(prepared * value_scale)
    output, offsets = np.empty_like(prepared), np.empty(rows if axis == "rows" else cols)
    xreal = cols * value_scale * (pixel_size if axis == "rows" else 1.)
    yreal = rows * value_scale * (pixel_size if axis == "columns" else 1.)
    _check(_library().afm_gwyddion_align(prepared, _mask_pointer(mask), rows, cols, xreal, yreal,
                                       int(axis == "columns"), METHODS[method], degree, trim_fraction, output, offsets), "line alignment")
    output /= value_scale
    output[~finite] = np.nan
    counts = selected.sum(axis=1 if axis == "rows" else 0)
    model = {"method": method, "axis": axis, "backend": describe(),
             "offsets": (offsets/value_scale).tolist(), "reference_counts": counts.tolist(),
             "warnings": ["Line corrections can remove genuine topography spanning a line."],
             "value_scale": value_scale, "pixel_size": pixel_size,
             "background_reconstruction": "replay the recorded native method and parameters from immutable input",
             "invalid_pixels": "mean-filled only in C input, excluded from reference; restored as NaN"}
    if method == "polynomial":
        model["degree"] = degree
        skipped = np.flatnonzero(counts <= degree).tolist()
        model["skipped_lines"] = skipped
        if skipped:
            model["warnings"].append("Lines with insufficient polynomial reference support are unchanged.")
    if method.startswith("trimmed"):
        model["trim_fraction"] = trim_fraction
    if method in {"median_difference", "trimmed_difference"}:
        model["mask_policy"] = "binary inclusion represented by the equivalent exclusion mask to avoid upstream include-mask bug"
    if method == "matching" and not finite.all():
        model["mask_policy"] = "reference excludes invalid pixels and their preceding along-line endpoints"
    return output, model


def plane_level(data, reference_mask):
    source, prepared, finite, selected, mask = _inputs(data, reference_mask)
    rows, cols = source.shape
    yy, xx = np.nonzero(selected)
    if len(xx) < 3 or np.linalg.matrix_rank(np.column_stack((np.ones(len(xx)), xx, yy))) != 3:
        raise ValueError("Plane leveling needs at least three non-collinear reference pixels.")
    output, coefficients = np.empty_like(prepared), np.empty(3)
    _check(_library().afm_gwyddion_plane(prepared, _mask_pointer(mask), rows, cols, cols, rows, output, coefficients), "plane level")
    output[~finite] = np.nan
    c, bx, by = coefficients
    return output, {"method": "gwyddion", "backend": describe(), "fit": "ordinary_least_squares",
                    "equation": "offset + x_coefficient*x_normalized + y_coefficient*y_normalized",
                    "coefficients": [float(c-.5*(bx+by)), float(bx*cols), float(by*rows)],
                    "pixel_index_coefficients": coefficients.tolist(),
                    "zero_reference": "Gwyddion Plane Level pivot (width/2,height/2); fitted intercept retained"}


def zero_level(data, reference_mask, mode="mean"):
    if mode not in {"mean", "min", "max"}:
        raise ValueError("Zero reference must be mean, min or max.")
    source, prepared, finite, selected, mask = _inputs(data, reference_mask)
    rows, cols = source.shape
    output, offset = np.empty_like(prepared), np.empty(1)
    _check(_library().afm_gwyddion_zero(prepared, _mask_pointer(mask), rows, cols, cols, rows,
                                       {"mean": 0, "min": 1, "max": 2}[mode], output, offset), "zero reference")
    output[~finite] = np.nan
    return output, {"method": "gwyddion", "statistic": mode, "offset": float(offset[0]), "backend": describe()}


def polynomial_level(data, reference_mask, mode="independent", degree=3, degree_x=3, degree_y=3):
    if mode not in {"independent", "total"}:
        raise ValueError("Polynomial mode must be independent or total.")
    for value in (degree, degree_x, degree_y):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or not 0 <= value <= 11:
            raise ValueError("Polynomial degrees must be integers from 0 to 11.")
    source, prepared, finite, selected, mask = _inputs(data, reference_mask)
    rows, cols = source.shape
    dx, dy = (degree_x, degree_y) if mode == "independent" else (degree, degree)
    terms = [(i, j) for i in range(dx+1) for j in range(dy+1) if mode == "independent" or i+j <= degree]
    if min(rows, cols) < 2 or dx >= cols or dy >= rows or selected.sum() < len(terms):
        raise ValueError("Polynomial fit needs sufficient independent reference coordinates for its degree.")
    if not selected.all():
        # Validate geometry without fitting heights. Once a subset has full
        # rank, adding reference coordinates cannot reduce that rank.
        y, x = np.nonzero(selected)
        vx = np.polynomial.legendre.legvander(np.linspace(-1, 1, cols), dx)
        vy = np.polynomial.legendre.legvander(np.linspace(-1, 1, rows), dy)
        px, py = np.asarray(terms).T
        reduced = np.empty((0, len(terms)))
        rank = 0
        for start in range(0, len(x), 4096):
            design = vx[x[start:start+4096]][:, px] * vy[y[start:start+4096]][:, py]
            reduced = np.linalg.qr(np.vstack((reduced, design)), mode="r")
            rank = np.linalg.matrix_rank(reduced)
            if rank == len(terms):
                break
        if rank != len(terms):
            raise ValueError("Polynomial reference is rank deficient; lower the degree or widen the reference.")
    output, coefficients = np.empty_like(prepared), np.zeros(144)
    powers, nterms = np.zeros(288, dtype=np.int32), ctypes.c_int()
    _check(_library().afm_gwyddion_polynomial(prepared, _mask_pointer(mask), rows, cols, cols, rows,
        int(mode == "total"), degree_x, degree_y, degree, output, coefficients, powers, ctypes.byref(nterms)), "polynomial background")
    output[~finite] = np.nan
    return output, {"method": "polynomial_background", "backend": describe(), "mode": mode,
                    "degree": degree if mode == "total" else None, "degree_x": dx, "degree_y": dy,
                    "basis": "monomial x^i*y^j; x,y span -1 to 1 at first/last pixel centres",
                    "powers": powers[:2*nterms.value].reshape(-1, 2).tolist(),
                    "coefficients": coefficients[:nterms.value].tolist(), "fit": "Gwyddion least squares",
                    "reference_count": int(selected.sum()), "zero_reference": "entire fitted background subtracted"}


def profile_values(data, width_um, height_um, start, end, samples, width=1, interpolation="linear", selected=None):
    """Native finite values; science.profile applies the invalid-support policy."""
    prepared = np.ascontiguousarray(np.where(np.isfinite(data), data, 0.), dtype=np.float64)
    mask = None if selected is None else np.ascontiguousarray(selected, dtype=np.float64)
    distances, values, count = np.empty(samples), np.empty(samples), ctypes.c_int()
    _check(_library().afm_gwyddion_profile(prepared, None if mask is None else _mask_pointer(mask), *prepared.shape,
        width_um, height_um, start[0]*width_um, start[1]*height_um, end[0]*width_um, end[1]*height_um,
        samples, width, int(interpolation == "linear"), distances, values, ctypes.byref(count)), "profile")
    return distances[:count.value], values[:count.value]
