"""Deterministic numerical operations shared by the GUI and MCP adapter.

Values stay in the input channel's calibrated units. Coordinates are fractions
of the scan footprint; pixel centres are ((column+.5)/width, (row+.5)/height).
NaNs denote invalid pixels, never zeros. No operation modifies its input.
"""

from __future__ import annotations

import base64
import copy
import math
from typing import Any

import numpy as np


ALGORITHM_VERSION = "3.0.0"
COORDINATE_FRAME = "normalized_scan_footprint_pixel_centres"


def _array(data: Any) -> np.ndarray:
    array = np.asarray(data, dtype=np.float64)
    if array.ndim != 2 or min(array.shape) == 0:
        raise ValueError("A non-empty two-dimensional numerical image is required.")
    if np.isinf(array).any():
        raise ValueError("Infinite image values are unsupported; mark invalid pixels as NaN.")
    if not np.isfinite(array).any():
        raise ValueError("The image has no valid pixels.")
    return array


def _region(roi: dict | None) -> dict | None:
    if roi is None:
        return None
    if not isinstance(roi, dict) or set(roi) != {"x0", "y0", "x1", "y1"}:
        raise ValueError("A region requires x0, y0, x1 and y1 only.")
    try:
        result = {key: float(roi[key]) for key in ("x0", "y0", "x1", "y1")}
    except (TypeError, ValueError) as exc:
        raise ValueError("Region coordinates must be numbers between 0 and 1.") from exc
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in result.values()):
        raise ValueError("Region coordinates must be finite numbers between 0 and 1.")
    if result["x0"] >= result["x1"] or result["y0"] >= result["y1"]:
        raise ValueError("The region must have positive width and height.")
    return result


def _mask(shape: tuple[int, int], roi: dict | None) -> np.ndarray:
    region = _region(roi)
    if region is None:
        return np.ones(shape, dtype=bool)
    rows, columns = shape
    x = (np.arange(columns) + 0.5) / columns
    y = (np.arange(rows) + 0.5) / rows
    return ((y[:, None] >= region["y0"]) & (y[:, None] < region["y1"]) &
            (x[None, :] >= region["x0"]) & (x[None, :] < region["x1"]))


def _selection(array: np.ndarray, roi: dict | None) -> np.ndarray:
    mask = _mask(array.shape, roi) & np.isfinite(array)
    if not mask.any():
        raise ValueError("The selected region contains no valid pixel centres.")
    return mask


def _analysis_mask(array: np.ndarray, mask: Any, masking: str) -> np.ndarray:
    """Validate an optional Gwyddion-style mask without changing input data."""
    if masking not in {"include", "exclude", "ignore"}:
        raise ValueError("Masking must be include, exclude or ignore.")
    if mask is None:
        return np.ones(array.shape, dtype=bool)
    try:
        weights = np.asarray(mask, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("A mask must be a numerical matrix matching the image.") from exc
    if (weights.shape != array.shape or not np.isfinite(weights).all()
            or (weights < 0).any() or (weights > 1).any()):
        raise ValueError("A mask must match the image and contain finite values from 0 to 1.")
    if masking == "ignore":
        return np.ones(array.shape, dtype=bool)
    return weights > 0 if masking == "include" else weights <= 0


def statistics(data: Any, roi: dict | None = None, mask: Any = None,
               masking: str = "include") -> dict:
    """Gwyddion 2.71 population moments and order statistics, without leveling.

    The median is the upper middle order statistic for an even pixel count.
    Excess kurtosis is zero for a Gaussian; Gwyddion returns zero skewness
    and excess kurtosis for constant data. NaNs are excluded (a Workbench
    extension). ROI and optional include/exclude masks are intersected.
    """
    array = _array(data)
    selected = _mask(array.shape, roi) & _analysis_mask(array, mask, masking) & np.isfinite(array)
    if not selected.any():
        raise ValueError("The selected region contains no valid pixel centres.")
    from .native_backend import statistics_values
    return statistics_values(array[selected])


def scan_line_axis(metadata: dict | None, requested: str = "auto") -> tuple[str, str]:
    """Resolve lines in the stored array, independent of trace/retrace and angle."""
    if requested in {"rows", "columns"}:
        return requested, "explicit user override in stored-array coordinates"
    if requested != "auto":
        raise ValueError("Line axis must be auto, rows or columns.")
    meta = metadata or {}
    orientation = meta.get("orientation", {})
    if (meta.get("format") == "Park TIFF" and
            orientation.get("transform_applied") == "none" and
            isinstance(orientation.get("swap_fast_slow"), bool)):
        return ("columns" if orientation["swap_fast_slow"] else "rows",
                "Park TIFF tag 50435 axis-swap flag; untransformed stored array")
    raise ValueError("Scan-line axis is not established. Choose rows or columns explicitly.")


def _robust_difference(values: np.ndarray) -> tuple[float, np.ndarray, float]:
    """Fit a constant to local differences after fixed 4.5-MAD clipping."""
    center = float(np.median(values))
    sigma = float(1.4826 * np.median(np.abs(values - center)))
    tolerance = max(4.5 * sigma, np.finfo(float).eps * max(1., float(np.max(np.abs(values)))) * 128)
    keep = np.abs(values - center) <= tolerance
    return float(values[keep].mean()), keep, tolerance


def _terrace_plane(array: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, dict]:
    """Try 1–3 parallel terrace planes; reject an inadequate automatic fit.

    Local differences initialize tilt and estimate noise. Alternating least
    squares fits shared slopes and distinct terrace intercepts. Only a shared
    plane is subtracted, never the individual terrace intercepts.
    """
    rows, columns = array.shape
    slopes, diagnostics, noise_estimates = [], [], []
    for axis, size in ((1, columns), (0, rows)):
        left = [slice(None), slice(None)]
        right = [slice(None), slice(None)]
        left[axis], right[axis] = slice(None, -1), slice(1, None)
        left, right = tuple(left), tuple(right)
        pairs = mask[left] & mask[right]
        differences = (array[right] - array[left])[pairs]
        if differences.size < 3:
            raise ValueError("2D material leveling needs at least three adjacent reference pairs in each axis. Widen the reference region.")
        slope, keep, threshold = _robust_difference(differences)
        if keep.sum() < 3:
            raise ValueError("Too few within-terrace pairs to fit a plane.")
        accepted = np.zeros(pairs.shape, dtype=bool)
        accepted[pairs] = keep
        slopes.append(slope * size)
        noise_estimates.append(float(1.4826 * np.median(np.abs(differences - np.median(differences))) / np.sqrt(2)))
        diagnostics.append({"axis": "x" if axis == 1 else "y", "candidate_pairs": int(pairs.sum()),
                            "accepted_pairs": int(keep.sum()), "threshold": threshold,
                            "mask_shape": list(pairs.shape),
                            "mask_packbits_base64": base64.b64encode(np.packbits(accepted).tobytes()).decode("ascii")})
    y, x = np.mgrid[:rows, :columns]
    x, y = (x + .5) / columns, (y + .5) / rows
    z, xx, yy = array[mask], x[mask], y[mask]
    numerical_floor = np.finfo(float).eps * max(1., float(np.max(np.abs(z)))) * 512
    # Use the larger directional estimate: quantized data can have an
    # exactly constant increment in one axis despite finite rounding noise.
    noise = max(*noise_estimates, numerical_floor)
    limit = 1.5 * noise
    min_support = max(10, int(np.ceil(z.size * .01)))
    attempts = []
    accepted_fit = None
    # Bounded deterministic initializations, not an unbounded layer search.
    for count in (1, 2, 3):
        best = None
        detrended = z - slopes[0] * xx - slopes[1] * yy
        seeds = [np.quantile(detrended, (np.arange(count) + .5) / count),
                 np.linspace(detrended.min(), detrended.max(), count)]
        for centers in seeds:
            bx, by = slopes
            previous = None
            for iteration in range(30):
                flat = z - bx * xx - by * yy
                labels = np.zeros(z.size, dtype=np.uint8)
                distance = np.abs(flat - centers[0])
                for k in range(1, count):
                    candidate = np.abs(flat - centers[k])
                    closer = candidate < distance
                    labels[closer] = k
                    distance[closer] = candidate[closer]
                groups = [labels == k for k in range(count)]
                if any(int(group.sum()) < min_support for group in groups):
                    break
                # Remove each group's mean before solving the common slopes.
                dx, dy, dz = xx.copy(), yy.copy(), z.copy()
                for group in groups:
                    dx[group] -= xx[group].mean()
                    dy[group] -= yy[group].mean()
                    dz[group] -= z[group].mean()
                design = np.array([[dx @ dx, dx @ dy], [dx @ dy, dy @ dy]])
                if np.linalg.cond(design) > 1e8:
                    break
                bx, by = np.linalg.solve(design, [dx @ dz, dy @ dz])
                centers = np.array([(z[group] - bx * xx[group] - by * yy[group]).mean() for group in groups])
                rms = float(np.sqrt(np.mean((z - bx * xx - by * yy - centers[labels]) ** 2)))
                fit = (rms, float(bx), float(by), centers.copy(), labels.copy(), iteration + 1)
                if best is None or rms < best[0]:
                    best = fit
                if previous is not None and np.array_equal(previous, labels):
                    break
                previous = labels
        attempts.append({"plane_count": count, "residual_rms": best[0] if best else None,
                         "accepted": best is not None and best[0] <= limit})
        if best is not None and best[0] <= limit:
            accepted_fit = best
            break
    if accepted_fit is None:
        raise ValueError("Automatic 2D material fit failed: no adequate model with 1–3 parallel terrace planes. Data is unchanged. Select a flat reference Area, then use Manual corrections → Level a plane.")
    rms, bx, by, centers, labels, iterations = accepted_fit
    tilt = bx * x + by * y
    offset = float(np.median((array - tilt)[mask]))
    assignment = np.full(array.shape, 255, dtype=np.uint8)
    assignment[mask] = labels
    return array - tilt - offset, {
        "method": "capped_parallel_terrace_planes", "fit": "alternating_least_squares",
        "equation": "terrace_intercept + x_coefficient*x_normalized + y_coefficient*y_normalized",
        "coefficients": [offset, bx, by], "plane_count": len(centers), "maximum_planes": 3,
        "planes": [{"coefficients": [float(c), bx, by], "reference_pixel_count": int((labels == k).sum())}
                   for k, c in enumerate(centers)],
        "selection": "smallest adequate plane count", "attempts": attempts,
        "residual_rms": rms, "estimated_noise_sigma": noise, "acceptance_rms_limit": limit,
        "minimum_pixels_per_plane": min_support, "maximum_iterations": 30, "iterations": iterations,
        "assignment_shape": list(array.shape),
        "assignment_uint8_base64": base64.b64encode(assignment.tobytes()).decode("ascii"),
        "assignment_encoding": "row-major uint8; 0–2 plane index, 255 outside reference",
        "pair_rejection_mad_multiplier": 4.5,
        "pairs": diagnostics, "mask_encoding": "row-major numpy.packbits, big bit order",
        "zero_reference": "median of leveled reference pixels; not an identified substrate",
        "claim_status": "proposal", "warnings": [
            "Fits at most three parallel terrace planes. Nonparallel surfaces, extra terraces or curvature may require manual leveling.",
            "Plane groups are fit assignments, not material or atomic-layer identifications. Relative terrace offsets are preserved."],
    }


def _gwyddion_value_scale(unit: str | None) -> tuple[float, str | None]:
    """SI-prefix conversion for Matching's dimensionful numerical weights."""
    if unit is None:
        return 1., "No value unit supplied; numerical values are assumed to use base units."
    unit = unit.strip().replace("μ", "µ")
    bases = {"m", "V", "A", "N", "Hz", "s", "Pa", "W", "J", "C", "F", "T", "Ω", "Ohm", "S"}
    if unit in bases or unit in {"deg", "°", "rad", "1", "", "a.u.", "a.u", "arb."}:
        return 1., None
    prefixes = {"da": 1e1, "Y": 1e24, "Z": 1e21, "E": 1e18, "P": 1e15, "T": 1e12,
                "G": 1e9, "M": 1e6, "k": 1e3, "h": 1e2, "d": 1e-1, "c": 1e-2,
                "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9, "p": 1e-12,
                "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24}
    for prefix, multiplier in prefixes.items():
        if unit.startswith(prefix) and unit[len(prefix):] in bases:
            return multiplier, None
    return 1., f"Unrecognized value unit {unit!r}; Matching uses native numerical units, so SI equivalence is not established."


def apply_recipe(data: Any, operations: list[dict], metadata: dict | None = None) -> tuple[np.ndarray, list[dict]]:
    """Replay an ordered recipe from its immutable input and return its history.

    Explicit methods select the Gwyddion-compatible implementations. Historic
    plane/alignment operations without a method retain their original behavior
    so saved recipes continue to replay. New clients always specify a method.
    """
    result = _array(data).copy()
    if not isinstance(operations, list):
        raise ValueError("A recipe must be a list of operations.")
    if len(operations) > 100:
        raise ValueError("A recipe may contain at most 100 operations.")
    history = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError("Every recipe operation must be an object.")
        common = {"type", "roi", "reference", "mask", "masking"}
        accepted = {
            "plane": {"method"}, "polynomial": {"mode", "degree", "degree_x", "degree_y"},
            "align_rows": {"method", "degree", "trim_fraction"},
            "align_columns": {"method", "degree", "trim_fraction"},
            "align_scan": {"method", "degree", "trim_fraction", "axis"},
            "terrace_plane": set(), "auto_2d": {"axis", "line_correction"},
            "auto_characterize": {"axis", "line_correction"}, "three_point": {"points", "radius"},
            "zero_mean": {"method"}, "zero_min": {"method"}, "zero_max": {"method"},
        }
        kind = operation.get("type")
        if not isinstance(kind, str) or kind not in accepted:
            raise ValueError(f"Unknown scientific operation: {kind!r}.")
        if set(operation) - common - accepted[kind]:
            raise ValueError(f"Unsupported parameter for {kind}.")
        if kind.startswith("align_") and "method" not in operation and ({"degree", "trim_fraction"} & set(operation)):
            raise ValueError("Specify an alignment method when supplying method parameters.")
        if "roi" in operation and "reference" in operation:
            raise ValueError("Specify either roi or reference, not both.")
        if "axis" in operation and kind not in {"align_scan", "auto_2d", "auto_characterize"}:
            raise ValueError("Only scan alignment and 2D auto processing accept an axis parameter.")
        if "line_correction" in operation and (kind not in {"auto_2d", "auto_characterize"} or not isinstance(operation["line_correction"], bool)):
            raise ValueError("line_correction must be a boolean for automatic processing.")
        region = _region(operation.get("roi", operation.get("reference")))
        from .leveling import recipe_reference
        masking = operation.get("masking", "include")
        if masking not in {"include", "exclude", "ignore"}:
            raise ValueError("Masking must be include, exclude or ignore.")
        mask = recipe_reference(result, _mask(result.shape, region), operation.get("mask"),
                                "ignore" if region is None and operation.get("mask") is None else masking)
        before = statistics(result)
        model: dict[str, Any]
        version = "1.0.0"
        resolved = {}
        if kind == "auto_characterize":
            from .characterization import auto_characterize
            result, model = auto_characterize(result, mask, metadata, operation.get("axis", "auto"), operation.get("line_correction", True))
        elif kind == "three_point":
            from .characterization import three_point_level
            resolved = {"points": copy.deepcopy(operation.get("points")), "radius": operation.get("radius", 2)}
            result, model = three_point_level(result, mask, **resolved)
        elif kind == "auto_2d":
            from .auto_processing import auto_2d
            result, model = auto_2d(result, mask, metadata, operation.get("axis", "auto"), operation.get("line_correction", True))
            version = "2.0.0"
        elif kind == "terrace_plane":
            result, model = _terrace_plane(result, mask)
            version = "1.1.0"
        elif kind.startswith("align_") and "method" in operation:
            from .native_backend import align_lines
            line_axis, source = scan_line_axis(metadata, operation.get("axis", "auto")) if kind == "align_scan" else (
                "rows" if kind == "align_rows" else "columns", "explicit stored-array axis")
            method = operation["method"]
            if "degree" in operation and method != "polynomial":
                raise ValueError("degree is only supported by polynomial line alignment.")
            if "trim_fraction" in operation and method not in {"trimmed_mean", "trimmed_difference"}:
                raise ValueError("trim_fraction is only supported by trimmed alignment methods.")
            meta = metadata or {}
            value_scale, scale_warning = _gwyddion_value_scale(meta.get("value_unit"))
            pixel_size = 1.
            if method == "facet_tilt":
                if meta.get("value_unit") not in {"m", "mm", "um", "µm", "nm", "pm"}:
                    raise ValueError("Facet tilt requires a height channel with lateral and vertical length calibration.")
                extent = meta.get("width_um" if line_axis == "rows" else "height_um")
                if not isinstance(extent, (int, float)) or not math.isfinite(extent) or extent <= 0:
                    raise ValueError("Facet tilt requires positive lateral calibration.")
                pixel_size = extent * 1e-6 / value_scale / result.shape[1 if line_axis == "rows" else 0]
            resolved = {"method": method}
            if method == "polynomial":
                resolved["degree"] = operation.get("degree", 1)
            elif method in {"trimmed_mean", "trimmed_difference"}:
                resolved["trim_fraction"] = operation.get("trim_fraction", .05)
            result, model = align_lines(result, mask, axis=line_axis, **resolved,
                                       pixel_size=pixel_size, value_scale=value_scale)
            model.update(axis_source=source, orientation=copy.deepcopy(meta.get("orientation", {})))
            if method == "matching" and scale_warning:
                model["warnings"].append(scale_warning)
            version = "3.0.0"
        elif kind == "polynomial":
            from .native_backend import polynomial_level
            resolved = {key: operation.get(key, default) for key, default in
                        (("mode", "independent"), ("degree", 3), ("degree_x", 3), ("degree_y", 3))}
            if resolved["mode"] == "independent" and "degree" in operation:
                raise ValueError("Use degree_x and degree_y for independent polynomial degrees.")
            if resolved["mode"] == "total" and ({"degree_x", "degree_y"} & set(operation)):
                raise ValueError("Use degree for a limited-total-degree polynomial.")
            result, model = polynomial_level(result, mask, **resolved)
            resolved = {key: value for key, value in resolved.items()
                        if key in ({"mode", "degree"} if resolved["mode"] == "total" else {"mode", "degree_x", "degree_y"})}
            version = "3.0.0"
        elif kind == "plane" and operation.get("method") == "gwyddion":
            from .native_backend import plane_level
            result, model = plane_level(result, mask)
            resolved = {"method": "gwyddion"}
            version = "3.0.0"
        elif kind in {"zero_min", "zero_max"} or (kind == "zero_mean" and "method" in operation):
            from .native_backend import zero_level
            if operation.get("method", "gwyddion") != "gwyddion":
                raise ValueError("Zero reference method must be gwyddion.")
            result, model = zero_level(result, mask, kind.removeprefix("zero_"))
            resolved = {"method": "gwyddion"}
            version = "3.0.0"
        elif kind == "align_scan":
            version = "1.1.0"
            line_axis, source = scan_line_axis(metadata, operation.get("axis", "auto"))
            # Compare overlapping points in adjacent lines: terraces occupying
            # only part of a line do not shift the whole line as line medians do.
            work = result if line_axis == "rows" else result.T
            reference = mask if line_axis == "rows" else mask.T
            pairs = reference[1:] & reference[:-1]
            counts = pairs.sum(axis=1)
            if np.any(counts < 3):
                raise ValueError("Scan-line alignment needs three shared reference pixels in every adjacent line pair. Widen the reference region.")
            differences = np.where(pairs, np.diff(work, axis=0), np.nan)
            increments = np.nanmedian(differences, axis=1)
            offsets = np.r_[0., np.cumsum(increments)]
            offsets -= np.median(offsets)
            work -= offsets[:, None]
            model = {"method": "adjacent_line_median_difference", "axis": line_axis,
                     "axis_source": source, "orientation": copy.deepcopy((metadata or {}).get("orientation", {})),
                     "offsets": offsets.tolist(), "reference_pair_counts": counts.tolist(),
                     "warnings": ["A terrace edge spanning most of a scan line can be removed as an offset. Inspect before keeping; use a continuous reference strip when available."]}
        elif kind == "plane":
            method = operation.get("method", "legacy")
            if method not in {"legacy", "gwyddion"}:
                raise ValueError("Plane method must be gwyddion or legacy.")
            rows, columns = result.shape
            y, x = np.mgrid[:rows, :columns]
            x = (x + 0.5) / columns
            y = (y + 0.5) / rows
            design = np.column_stack((np.ones(mask.sum()), x[mask], y[mask]))
            if len(design) < 3:
                raise ValueError("Plane leveling needs at least three non-collinear reference pixels.")
            coefficients, _, rank, _ = np.linalg.lstsq(design, result[mask], rcond=None)
            if rank < 3:
                raise ValueError("Plane leveling needs a two-dimensional reference region.")
            background = coefficients[0] + coefficients[1] * x + coefficients[2] * y
            result -= background
            model = {
                "equation": "offset + x_coefficient*x_normalized + y_coefficient*y_normalized",
                "coefficients": coefficients.tolist(),
                "fit": "ordinary_least_squares",
            }
        elif kind in {"align_rows", "align_columns"}:
            axis = 1 if kind == "align_rows" else 0
            counts = mask.sum(axis=axis)
            missing = np.flatnonzero(counts < 2).tolist()
            if missing:
                label = "rows" if axis == 1 else "columns"
                shown = ", ".join(str(value + 1) for value in missing[:8])
                suffix = "…" if len(missing) > 8 else ""
                raise ValueError(
                    f"Alignment needs at least two reference pixels in every {label[:-1]}; "
                    f"insufficient {label}: {shown}{suffix}. Widen the reference region.")
            medians = np.nanmedian(np.where(mask, result, np.nan), axis=axis)
            target = float(np.median(medians))
            offsets = medians - target
            result -= offsets[:, None] if axis == 1 else offsets[None, :]
            model = {"method": "median_offset", "axis": "rows" if axis == 1 else "columns",
                     "target_median": target, "offsets": offsets.tolist(),
                     "reference_counts": counts.tolist()}
        else:
            offset = float(result[mask].min() if kind == "zero_min" else result[mask].max() if kind == "zero_max" else result[mask].mean())
            result -= offset
            model = {"offset": offset, "method": {"zero_min": "minimum", "zero_max": "maximum", "zero_mean": "arithmetic_mean"}[kind]}
            if kind != "zero_mean":
                version = "3.0.0"
        history.append({
            "step": index + 1,
            "type": kind,
            "algorithm_version": version,
            "parameters": {"roi": copy.deepcopy(region), **({"axis": operation.get("axis", "auto")} if kind in {"align_scan", "auto_2d", "auto_characterize"} else {}), **({"line_correction": operation.get("line_correction", True)} if kind in {"auto_2d", "auto_characterize"} else {}), **resolved,
                           **{key: copy.deepcopy(operation[key]) for key in ("mask", "masking") if key in operation}},
            "reference": {"mode": masking, "region": copy.deepcopy(region),
                          "coordinate_frame": COORDINATE_FRAME,
                          "valid_pixel_count": int(mask.sum())},
            "invalid_pixels": "NaN excluded from reference and preserved in output",
            "model": model,
            "before": before,
            "after": statistics(result),
        })
    return result, history


def _point(point: Any, name: str) -> np.ndarray:
    try:
        result = np.asarray(point, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain normalized x and y coordinates.") from exc
    if result.shape != (2,) or not np.isfinite(result).all() or (result < 0).any() or (result > 1).any():
        raise ValueError(f"{name} must contain x and y between 0 and 1.")
    return result


def _profile_support_valid(array: np.ndarray, points: np.ndarray,
                           interpolation: str) -> np.ndarray:
    """Check interpolation support only; values are computed by native C."""
    rows, columns = array.shape
    if interpolation == "nearest":
        x = np.clip(np.floor(points[..., 0] * columns).astype(int), 0, columns - 1)
        y = np.clip(np.floor(points[..., 1] * rows).astype(int), 0, rows - 1)
        return np.isfinite(array[y, x])
    x = np.clip(points[..., 0] * columns - 0.5, 0, columns - 1)
    y = np.clip(points[..., 1] * rows - 0.5, 0, rows - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, columns - 1), np.minimum(y0 + 1, rows - 1)
    dx, dy = x - x0, y - y0
    neighbours = np.stack((array[y0, x0], array[y0, x1], array[y1, x0], array[y1, x1]))
    weights = np.stack(((1-dx)*(1-dy), dx*(1-dy), (1-dx)*dy, dx*dy))
    return np.all(np.isfinite(neighbours) | (weights == 0), axis=0)


def profile(data: Any, width_um: float, height_um: float, start: Any, end: Any,
            samples: int | None = None, interpolation: str = "linear",
            averaging_width_pixels: int = 1, sampling: str = "gwyddion",
            mask: Any = None, masking: str = "ignore") -> dict:
    """Extract a profile using Gwyddion 2.71's continuous-coordinate convention.

    Default resolution follows the Profile tool. Linear interpolation, edge
    extension and transverse averaging follow get_profile_mask. Select legacy
    sampling to replay the previous automatic sample count. Invalid or fully
    masked samples are retained as None, preserving their distance coordinates.
    Gwyddion omits fully masked samples and has no equivalent NaN contract.
    """
    array = _array(data)
    try:
        width_um, height_um = float(width_um), float(height_um)
    except (TypeError, ValueError) as exc:
        raise ValueError("Positive lateral calibration in micrometres is required.") from exc
    if not all(math.isfinite(v) and v > 0 for v in (width_um, height_um)):
        raise ValueError("Positive finite lateral calibration in micrometres is required.")
    if interpolation not in {"linear", "bilinear", "nearest", "round"}:
        raise ValueError("Profile interpolation must be linear or nearest.")
    interpolation = "nearest" if interpolation in {"nearest", "round"} else "linear"
    if sampling not in {"gwyddion", "legacy"}:
        raise ValueError("Profile sampling must be gwyddion or legacy.")
    if (isinstance(averaging_width_pixels, bool)
            or not isinstance(averaging_width_pixels, (int, np.integer))
            or not 1 <= averaging_width_pixels <= 128):
        raise ValueError("Profile averaging width must be an integer from 1 to 128 pixels.")
    # Validate even ignored masks, so a saved selection cannot be malformed.
    _analysis_mask(array, mask, masking)
    first, last = _point(start, "Start"), _point(end, "End")
    delta = last - first
    length = float(np.hypot(delta[0] * width_um, delta[1] * height_um))
    if length == 0:
        raise ValueError("A profile needs distinct start and end points.")
    rows, columns = array.shape
    dimensions = np.array([columns, rows])
    pixel_delta = delta * dimensions
    automatic_resolution = samples is None
    if automatic_resolution:
        if sampling == "legacy":
            samples = max(2, int(math.ceil(np.hypot(*pixel_delta))) + 1)
        else:
            endpoint_pixels = np.floor(np.stack((first, last)) * dimensions)
            covered = np.abs(endpoint_pixels[1] - endpoint_pixels[0]) + 1
            samples = max(4, int(math.floor(np.hypot(*covered) + 0.5)))
        samples = min(samples, 65536)
    if isinstance(samples, bool) or not isinstance(samples, (int, np.integer)) or not 2 <= samples <= 65536:
        raise ValueError("Profile sample count must be an integer from 2 to 65536.")
    t = np.linspace(0.0, 1.0, int(samples))
    centre_points = first[None, :] + t[:, None] * delta
    if averaging_width_pixels == 1:
        offsets = np.zeros(1)
    else:
        # Dense symmetric transverse sampling, independent of profile resolution.
        offsets = np.linspace(-averaging_width_pixels / 2, averaging_width_pixels / 2,
                              4 * (averaging_width_pixels - 1) + 1)
    normal = np.array([pixel_delta[1], -pixel_delta[0]]) / np.hypot(*pixel_delta)
    values = np.full(int(samples), np.nan)
    valid = np.zeros(int(samples), dtype=bool)
    contributing = np.zeros(int(samples), dtype=int)
    # Bound temporary memory even at maximum width and requested resolution.
    for begin in range(0, int(samples), 1024):
        end_index = min(begin + 1024, int(samples))
        points = centre_points[begin:end_index, None, :] + offsets[None, :, None] * normal / dimensions
        points = np.clip(points, 0.0, 0.999999)
        finite = _profile_support_valid(array, points, interpolation)
        selected = np.ones(finite.shape, dtype=bool)
        if mask is not None and masking != "ignore":
            weights = np.asarray(mask, dtype=float)
            pixel_indices = np.floor(points * dimensions).astype(int)
            local_mask = weights[pixel_indices[..., 1], pixel_indices[..., 0]]
            # Upstream profile sampling excludes mask values >=1; fractional
            # masks can participate in both modes. Statistics uses <=0 instead.
            selected = local_mask > 0 if masking == "include" else local_mask < 1
        counts = selected.sum(axis=1)
        okay = (counts > 0) & np.all(finite | ~selected, axis=1)
        valid[begin:end_index] = okay
        contributing[begin:end_index] = counts
    from .native_backend import profile_values, describe
    native_mask = None
    if mask is not None and masking != "ignore":
        native_mask = np.asarray(mask) > 0 if masking == "include" else np.asarray(mask) < 1
    distances, native_values = profile_values(array, width_um, height_um, first, last, int(samples),
                                              averaging_width_pixels, interpolation, native_mask)
    indices = np.rint(distances / length * (int(samples)-1)).astype(int)
    values[indices] = native_values
    valid &= np.isfinite(values)
    return {
        "distance_um": (t * length).tolist(),
        "values": [float(value) if okay else None for value, okay in zip(values, valid)],
        "length_um": length,
        "start": first.tolist(), "end": last.tolist(), "samples": int(samples),
        "start_um": (first * [width_um, height_um]).tolist(),
        "end_um": (last * [width_um, height_um]).tolist(),
        "coordinate_frame": COORDINATE_FRAME,
        "interpolation": "bilinear" if interpolation == "linear" else "nearest",
        "border": "nearest_pixel_centre",
        "averaging_width_pixels": int(averaging_width_pixels),
        "transverse_sample_count": int(offsets.size),
        "contributing_transverse_samples": contributing.tolist(),
        "sampling": sampling, "automatic_resolution": automatic_resolution,
        "masking": masking,
        "mask": None if mask is None else np.asarray(mask, dtype=float).tolist(),
        "reference_implementation": "Gwyddion 2.71 Profile tool; continuous coordinates",
        "compatibility_notes": [
            "Invalid and fully masked samples remain None instead of being omitted.",
            "Only linear and nearest interpolation are supported; no calibration-uncertainty fields are fitted."],
        "algorithm_version": "3.0.0", "backend": describe(),
        "invalid_sample_count": int((~valid).sum()),
    }


def step_height(data: Any, region_a: dict, region_b: dict, mask: Any = None, masking: str = "include") -> dict:
    """Signed mean(B) minus mean(A), with descriptive population dispersion.

    No plane is implicitly fitted. Dispersion is not measurement uncertainty.
    """
    array = _array(data)
    first, second = _region(region_a), _region(region_b)
    if first is None or second is None:
        raise ValueError("Select two explicit reference regions for a step measurement.")
    mask_a, mask_b = _selection(array, first), _selection(array, second)
    if (mask_a & mask_b).any():
        raise ValueError("Step reference regions must not share pixel centres.")
    stats_a, stats_b = statistics(array, first, mask, masking), statistics(array, second, mask, masking)
    return {
        "difference": stats_b["mean"] - stats_a["mean"],
        "region_a": {"region": first, **stats_a},
        "region_b": {"region": second, **stats_b},
        "definition": "mean(region_b) - mean(region_a)",
        "reference_surface": "current input; no implicit leveling",
        "dispersion_definition": "Sq in each region is population dispersion, not uncertainty",
        "method": "two_region_mean_difference",
        "gwyddion_equivalent": False,
        "compatibility_notes": "This descriptive ROI comparison is not Gwyddion's fitted step or terrace analysis.",
        "coordinate_frame": COORDINATE_FRAME,
        "algorithm_version": ALGORITHM_VERSION,
    }
