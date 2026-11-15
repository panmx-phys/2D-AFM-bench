"""Public line-alignment API backed by the real Gwyddion C libraries.

Validation, invalid-pixel policy and provenance live in ``native_backend``;
all line corrections and upper-median values are computed by Gwyddion 2.71.
A missing native backend is an error, never a numerical fallback.
"""
from .native_backend import METHODS as _METHOD_IDS, align_lines, statistics_values

METHODS = tuple(_METHOD_IDS)
REFERENCE_VERSION = "Gwyddion 2.71"


def gwy_median(values):
    """Return Gwyddion's upper-middle median through the native backend."""
    return statistics_values(values)["median"]
