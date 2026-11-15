# Gwyddion compatibility audit

Audit date: 2026-11-10. The primary scientific backend is **Gwyddion 2.71 C**, following the user's decision to use native routines and GPL distribution. Python calls a narrow ABI linked to the real `libgwyprocess2` and `libgwyddion2` libraries. This document separates source inspection, executed numerical comparisons and deliberate Workbench differences. It covers every processing and measurement operation currently exposed by this backend; it does not claim to expose every Gwyddion module.

## Evidence and reproducibility

The [official 2.71 release archive](https://downloads.sourceforge.net/project/gwyddion/gwyddion/2.71/gwyddion-2.71.tar.xz) used for inspection has SHA-256:

```text
2df721befccbe4d5ee2ba564b32e69341f8ce1de637e2045838a09a2d46b5dba
```

[native_backend.py](../afm_workbench/native_backend.py) calls the production [C adapter](../native/afm_gwyddion.c), using real Gwyddion objects and libraries. Modus, Matching and row Facet Tilt use upstream module helpers included at build time; the other operations use public scientific-library APIs. The native build pins and hashes its source, disables OpenMP, and bundles its runtime dependency closure. Missing/incompatible native libraries fail explicitly. Engine and adapter versions appear in operation history and measurement/export provenance. See [build and source-distribution instructions](../native/README.md).

[check_gwyddion.py](../scripts/check_gwyddion.py) is a separate validation harness. It extracts selected numerical function definitions unchanged, compiles them with a small standalone object/API adapter, and runs synthetic inputs. Its simplified objects are never used in production. The earlier parallel NumPy alignment/polynomial implementations have been removed; Python retains validation, provenance, invalid-data handling, custom terrace processing and legacy recipe replay.

The generated [reference fixture](../tests/fixtures/gwyddion-2.71.json) records hashes of every upstream source file used. It contains all eight Align Rows methods plus the mean alias, six masked alignment cases, Matching with nanometre-to-metre conversion, masked and unmasked Plane Level, population moments, and four nearest/linear profiles with widths one and three. The input arrays are synthetic and redistributable.

To regenerate, unpack the official archive outside this repository and run:

```sh
python scripts/check_gwyddion.py /path/to/gwyddion-2.71 tests/fixtures/gwyddion-2.71.json
python -m unittest discover -s tests -v
```

Regeneration requires NumPy and a C99 compiler (`cc`). Ordinary tests consume the saved JSON and require the built native backend, but no separate Gwyddion application installation or compiler at test time. The reference harness was executed on the development Mac. It exercises actual upstream calculation functions, **not a complete Gwyddion application, its GUI, or a Windows build**. Its adapter replaces object allocation, unit objects, cache bookkeeping and simple array access; nearest/linear are the only profile interpolators it permits. Polynomial surface fitting additionally has independent analytical tests, rather than an executed upstream surface-polynomial fixture.

## Coverage of the backend

| Workbench behavior | Reference and comparison | Result or deliberate distinction |
| --- | --- | --- |
| `plane`, `method: "gwyddion"` | `modules/process/level.c`; `libprocess/level.c`; masked and unmasked C fixtures | Same least-squares slopes and Gwyddion's index-coordinate pivot. Plane Level does not force zero mean. |
| `polynomial` | `gwy_data_field_fit_poly` and `gwy_data_field_subtract_poly`; analytical ground truth | Independent horizontal/vertical degrees or limited total degree, 0–11. Native normal-equation fit and monomial coefficients; Python validates reference geometry before the call. |
| `align_rows`, `align_columns`, `align_scan` with explicit `method` | `modules/process/linematch.c`; `libprocess/correct.c`; `libgwyddion/gwymath-rank.c`; executed C fixtures | All eight methods and mean alias, both axes; details below. |
| `zero_mean` | Gwyddion Zero Mean Value, `modules/process/level.c` | Subtract the selected arithmetic mean, including masked references. |
| `zero_min` | Gwyddion Fix Zero, `modules/process/level.c` | Subtract the selected minimum, including masked references. |
| `zero_max` | Gwyddion Zero Maximum Value, `modules/process/level.c` | Subtract the selected maximum, including masked references. |
| `terrace_plane` | Reviewed against Facet Level and terrace-model concepts | Workbench's capped 1–3 parallel-plane fit. It is **not** Gwyddion Facet Level or Flatten Base. Its fitted grouping remains a proposal. |
| `auto_2d` | Reviewed against line correction, Facet Level and Flatten Base | Workbench's independently fitted terrace planes, jump protection, support masks and fit gates. It is **not** a Gwyddion-equivalent automatic pipeline. |
| `statistics`, area measurements | `libprocess/stats.c`; `gwymath-rank.c`; executed moments fixture | Mean, population Sa/Sq/variance, skewness, excess kurtosis, upper-middle median, extrema, Sp/Sv/Sz. No implicit leveling. |
| `profile` | `modules/tools/profile.c`; `libprocess/datafield.c`; executed profile fixtures | Gwyddion tool sample-count convention, continuous pixel-centre coordinates, nearest/linear interpolation and transverse width averaging. Explicit legacy sample-count mode remains. |
| `step_height` | Compared with Gwyddion's graph-fitting and terrace-analysis concepts | Signed mean(B) minus mean(A), not a fitted step model. Explicitly reports `gwyddion_equivalent: false`. |
| Park TIFF import | `modules/file/psia.c`; source inspection plus existing synthetic TIFF tests | Calibration formula matches for accepted variants. Stored orientation is intentionally retained, unlike Gwyddion's vertical flip. See below. |
| Preview, saved recipes, undo, measurements, CSV | Service path inspection and service regression tests | GUI and MCP call the same numerical core. Preview works on a copy; saved recipes replay from immutable calibrated data; measurements and CSV use full resolution. |
| Thumbnail, display contrast, comparison and PNG | Service/front-end inspection; existing tests | Display-only sampling and colors. These are not Gwyddion display-rendering replicas and cannot be used as numerical reference arrays. |
| JSON/session export, catalog and metadata | Service path inspection | Workbench provenance/catalog behavior, not a Gwyddion file format implementation. Session JSON does not embed original files or pixel arrays. |

The definitions of leveling and polynomial fit modes are documented in the [Gwyddion leveling guide](https://gwyddion.net/documentation/user-guide-en/leveling-and-background.html). The moment and order statistics follow the [Gwyddion statistical analysis guide](https://gwyddion.net/documentation/user-guide-en/statistical-analysis.html).

## Align Rows and vertical alignment

Gwyddion's default Align Rows method is Median; polynomial degree defaults to 1 and trim fraction to 0.05 **from each tail**. Vertical alignment applies the same operation after transposing the image and mask. Workbench exposes these choices under the same shared scientific API. `align_scan` resolves rows/columns from recorded orientation or an explicit override. A recorded scan angle does not itself rotate the stored array. The [Gwyddion scan-line guide](https://gwyddion.net/documentation/user-guide-en/scan-line-defects.html) describes the intended uses of the methods.

| Method identifier | Numerical convention |
| --- | --- |
| `median` | Upper-middle order statistic, including even sample counts. Subtract each line's median minus the arithmetic mean of line medians. This differs from NumPy's ordinary even-count median and the old Workbench median-of-medians datum. |
| `mean` | Arithmetic line means with their average removed from the shifts; equivalent to polynomial degree zero. |
| `polynomial` | Degree 0–5. Degrees above zero fit each line independently and retain the original image mean. This can remove real features varying along a line. |
| `median_difference` | Upper median of differences between matching pixels on adjacent lines; cumulative offsets are detrended by a least-squares straight line. Thus the overall linear trend across lines is retained. |
| `trimmed_mean` | Sort each line, round `fraction × count` to the nearest integer with half upward, discard that many values at each end, and average. Near half trimming, use the upper median. |
| `trimmed_difference` | Apply the same trimmed estimator to adjacent-line differences, then remove the affine trend from cumulative offsets. |
| `modus` | Find the narrowest interval with approximately √N sorted values, then average its central portion; fewer than nine selected values use the upper median. |
| `matching` | Upstream slope-difference weighting, including its unit-dependent exponent. Calibrated values are interpreted in base SI units for the weights. Identical slopes can leave a constant line offset unchanged, as in upstream 2.71. |
| `facet_tilt` | Iteratively remove each line's weighted prevalent slope, up to 30 iterations; retain line offsets. Convergence uses calibrated lateral/vertical lengths. |

On the saved unmasked synthetic fixture, all nine method outputs agreed with the executed upstream C functions to a maximum absolute discrepancy below `3e-14` in the fixture's value units. The regression tolerance is slightly larger to allow floating-point solver and platform differences. This is evidence for the tested arrays and settings, not proof for every input or physical surface.

### Deliberate numerical safeguards

- NaNs remain invalid and are excluded from references. Finite placeholders are used only inside the C input buffer (to avoid `0*NaN`), and the original invalid positions are restored. Profile samples with invalid positive-weight support remain `null`. Matching also excludes the preceding interval endpoint of invalid pixels, preventing placeholder values from entering native derivative weights. Gwyddion's raw numerical arrays do not provide this same NaN contract.
- For difference methods, a boolean inclusion mask means shared selected pixels. The Gwyddion 2.71 include branch in `gwy_data_field_find_row_shifts_trimmed_diff` requires mask values **greater than one**, which excludes ordinary binary-mask pixels. Workbench does not reproduce that condition.
- Lines with insufficient polynomial fit support are left unchanged and reported. Upstream 2.71 can add the global mean to such lines after a zero-coefficient fallback.
- Exactly flat facet rows terminate before the upstream `0/0` case. Other nonfinite native outputs fail atomically, leaving input unchanged; no alternative algorithm is silently substituted.
- Underconstrained plane/surface-polynomial fits are rejected. An all-zero native polynomial result whose reference moments cannot justify a zero fit is also rejected, catching upstream normal-matrix factorization failures. High degrees can be numerically ill-conditioned.

## Datum, masks and existing recipes

Gwyddion Plane Level subtracts the fitted slopes about `(width/2, height/2)` in zero-based pixel-index coordinates. That is half a pixel beyond the mean index on each axis; it changes the image mean by half the sum of the per-pixel slopes. The old Workbench plane operation instead subtracts the full fitted plane, including its intercept. New `method: "gwyddion"` explicitly selects the former. Use `zero_mean` separately when a zero-mean datum is wanted.

Recipes lacking an explicit plane/alignment method, and old methodless `zero_mean`, keep their former numerical behavior. New UI operations specify their selected method. History records the resolved method, parameters, reference, offsets or coefficients, scientific version, and before/after statistics. Native method provenance identifies Gwyddion 2.71 and adapter ABI 1. Custom terrace algorithms retain their own versions.

Recipe masks are full-resolution binary arrays. Inclusion uses the selected pixels; exclusion uses their complement; ignore uses all finite pixels. A supplied ROI restricts a raster mask. For the older ROI-only correction interface, the rectangle itself is the reference mask, so exclusion selects its exterior. Analysis ROIs restrict the measured area. Pixel-centre coordinates and the retained stored orientation apply consistently.

HTTP and MCP requests share a 32 MiB limit, large enough for a 2048 × 2048 binary mask. Matching recognizes SI prefixes on common length, electrical, force and frequency units. Unknown units retain their native numerical scale and emit a warning that SI equivalence is not established.

## Analysis and import distinctions

The statistical median uses the upper central ranked value, not the average of the two central values. Kurtosis is **excess** kurtosis; adding 3 gives the non-excess convention. Constant input returns zero skewness and zero excess kurtosis, following the upstream routine. Roughness is relative to the selected mean, with population rather than sample normalization.

Profiles retain physical distance coordinates for every requested sample. Workbench returns `null` at fully excluded or invalid locations, while Gwyddion omits fully excluded positions from the returned point list. Width averaging follows the upstream dense transverse sampling, not an integer set of parallel one-pixel lines. No fitted-step result or measurement uncertainty is inferred from a profile or two-area height difference.

For accepted Park v1/v2 numeric payloads, both readers apply `gain × (scale × raw + offset)` and the unit conversion. Gwyddion then reverses the row order (`invert(TRUE, FALSE, FALSE)`); Workbench retains the stored order and records this in metadata. To compare imported arrays, reverse one reader's rows and convert its units before comparing heights or profile locations. This source audit did not run the Gwyddion file-import GUI. Workbench also rejects missing units and zero calibration scale, whereas upstream can supply defaults. No existing imported pixels or source files were rewritten by this compatibility update.

## Scope limits

Gwyddion-only modules such as surface Facet Level, Flatten Base, rotated leveling, revolving-arc/sphere backgrounds, filters, scar correction, FFT/PSD/ACF, grain analysis, correlation-length estimation, surface-area metrics and graph-model fitting are not implemented by this backend and are not aliases for the custom automatic operations. In particular, `auto_2d` remains a recorded fit proposal with its own assumptions and rejection gates. Matching a model or matching Gwyddion's arithmetic does not establish a physical mechanism, instrument calibration or experimental uncertainty.
