# Validation record

Use the [test catalog and focused workflow](testing.md) to choose current checks. The dated records below are historical evidence, not a requirement to rerun every check after each edit. Six preview-era browser scripts are cataloged as legacy; their older passes do not describe the current direct-save interface.

## Test catalog and focused runner, 2026-11-14

Executed locally on macOS arm64. This change consolidates test selection and reporting; it does not change scientific algorithms or product behavior.

- Catalog audit accounts for 14 Python test modules, seven active runtime/browser/desktop smoke scripts, six legacy browser scripts and one manual reference generator. The six legacy entries were identified by source inspection of removed preview-control assertions; they were not rerun or reported as passing.
- A one-time full Python baseline executed 140 tests: 139 passed and one HTTP test was skipped because the sandbox prohibited loopback binding. The runner reported that suite as **incomplete** with a nonzero exit. A focused `--check service --check runtime` rerun with loopback access passed all 14 service tests and the new source-runtime check. After extending the selector regression coverage, `--check test-runner` passed all 13 runner tests. Together these runs cover the current 141 Python tests; no scientific suite was rerun merely because catalog documentation changed.
- Runner regression checks cover complete/unique inventory, imports and shared fixtures, native C dependency propagation, unrelated-test exclusion, unknown/new/deleted source fallbacks, legacy patterns that must not conceal new code, staged/unstaged/untracked paths and rename sides in a nested repository, deferred kinds, missing dependencies, nonzero exits, timeouts, skips and empty suites. The final change plan selected only `test-runner` and `runtime`.
- The new runtime smoke passed against the rebuilt Mac executable in an isolated synthetic workspace. It checked every declared frontend asset, token enforcement, native Gwyddion plane correction, saved recipe/history, unchanged raw pixels and undo. This is packaged HTTP/assets/scientific-runtime coverage, not a packaged desktop-window or native-renderer acceptance run.
- New source files were staged before rebuilding, and their bytes were checked against `dist/AFM-Workbench-source.tar.gz`. PyInstaller compilation completed using a project-local cache. The synchronized folder reattached Finder metadata and prevented the build script's in-place ad-hoc signing; a clean copy under `/private/tmp` passed ad-hoc signing and strict signature verification. The refreshed distributable is `dist/AFM-Workbench-macOS.zip`. This is not Developer ID signing or notarization.
- Git whitespace checks passed. CI configuration was updated but no remote workflow was run here. Browser/native GUI workflows and Windows packaging were not revalidated for this tooling change. Per-run logs and JSON reports remain in ignored `.test-artifacts/runs/`.

## Characterization workflow, 2026-11-11

Executed locally on macOS; these are software checks, not validation of a physical substrate assignment. No Windows package or desktop WebKit validation was performed for this change.

- `python -m unittest discover -s tests -v`: **111 passed**, no skips, with loopback binding permitted. Eight new characterization tests cover three-plane height preservation, retained particles and local texture, column alignment, exclusion masks, deterministic replay, plane-only preservation of relative terrace slope, unknown-axis failure, manual patch means, NaNs, invalid/collinear points, curvature and excess-plane rejection, GUI-service/MCP parity, temporary display-range queries, export provenance, and atomic failed saves.
- `scripts/characterization-smoke.cjs`: passed automatic preview on opening unprocessed height, three visible points, rectangular image/overlay agreement, full-resolution ROI contrast during a preview, unchanged numerical statistics and saved display, mask snapshots, 900 × 650 layout, save/reopen without stacked automatic operations, persistent failure notification, manual three-point fallback, opt-out, and discard while a contrast request is in flight. It generates synthetic TIFFs and uses the real local HTTP service.
- Existing `scripts/inspector-smoke.cjs`, `scripts/processing-smoke.cjs`, and `scripts/masking-display-smoke.cjs` passed with automatic opening disabled to exercise their explicit-operation workflows. The dedicated characterization test covers the new default. JavaScript syntax and Git whitespace checks passed. Generated preview/manual-fallback screenshots were visually inspected; artifacts remain local and excluded from source releases.
- Rebuilt the local Mac application and passed `scripts/characterization-smoke.cjs` again through its packaged executable and bundled libraries in loopback-browser mode, with a separate synthetic catalog. The synchronized project directory regenerated bundle Finder metadata, invalidating the signature of the loose `dist` app. A copy staged outside synchronization passed ad-hoc signature verification and was archived as `dist/AFM-Workbench-macOS.zip`; use that archive for the updated local app. This is not Developer ID signing, notarization, native WebKit acceptance, or Windows validation.
- A read-only convenience trial used the first six local forward Z-height fixtures in filename order. **Two returned proposals; four requested manual input** (three failed full-reference plane-support gates, one exceeded three candidate planes). These private fixtures are not shipped or required by the tests, and have no independently labeled reference planes. This measures behavior on those inputs only; acceptance is not scientific ground truth and this is not an accuracy estimate.

The new selection remains conservative: it requires the existing detector's broad 1–3-plane support as well as a reliable triangle. A locally flat patch can still be rejected when other parts of the selected reference are poorly explained. Conversely, a passing plane may represent the wrong physical reference. The visible points, original comparison, retained provenance, discard/undo, and explicit manual fallback remain necessary. Scan-line offsets can also remove real variation shared across a line; this ambiguity is separate from point selection.

## Editable masks and color limits, 2026-11-10

Executed on the local Mac with the native Gwyddion backend and disposable synthetic workspaces:

- **103 backend tests passed, no skips**, including the existing HTTP/MCP checks. The eight added tests cover full-resolution rectangle/brush geometry and erase, persistent undo/redo and branching, fixed mask snapshots in recipes and measurements, masked step statistics and empty references, threshold/range calculations beyond display sampling, display/thumbnail/export persistence without numerical mutation, rejected edits remaining atomic, constant images, preview ranges and the shared MCP service. Output is retained locally in ignored `.test-artifacts/masking-all-tests.log`.
- `scripts/masking-display-smoke.cjs` passed against the source server in headless Chrome: rectangle/brush drawing, erase, invert, threshold, undo/redo, include/exclude/ignore modes, masked statistics/profile/area/step measurements, empty selection without whole-image fallback, processing mask snapshots, save/reload and unchanged original arrays. A single marked source pixel remained visible when reducing a 1024 × 1024 mask to a 512 × 512 overlay.
- The same browser run checked finite numeric limits, keyboard-adjustable lower/upper sliders, auto/full/selected-area ranges, rejection of inverted bounds, fixed manual limits across Original/Result, per-image persistence and unchanged numerical arrays/statistics/profile values. Independent comparison used each image's saved limits and palette; shared comparison used one palette/range without changing statistics.
- PNG figure download produced a 1100 × 1240 image. The exported image was visually inspected for the mask overlay, scale, color limits and processing/mask labels. Color controls and mask overlays were also inspected at 1280 × 900 and 900 × 650. A capture immediately after resizing initially showed stale compositor content; after waiting for the resized frames, the compact view showed one application tree, a fully visible image and no horizontal overflow. Screenshots and the run log are in ignored `.test-artifacts/`.
- The existing Gwyddion browser workflow passed after integration, retaining the correction/profile controls and saved-recipe behavior.
- Rebuilt the Mac application and reran the complete masking/display browser script against its packaged executable and bundled native libraries, using a separate synthetic catalog. All checks passed, including PNG export and per-image/shared comparison; output is retained in `.test-artifacts/masking-packaged-smoke.log`. The build generated the corresponding-source bundle and passed its final local ad-hoc signature check.

These are synthetic numerical and browser checks, not instrument calibration, native WebKit/file-dialog acceptance or Windows validation. Mask visibility on a reduced display is deliberately conservative; scientific selections remain at their original resolution.

## Native Gwyddion backend, 2026-11-10

Executed on the local Mac using Python 3.12 and the project's NumPy environment:

- **95 backend tests passed, no skips**, including HTTP and MCP, immutable inputs, legacy replay, native invocation checks, missing-library failure without fallback, masks/NaNs, SI conversion, zero references, detected polynomial-factorization failure, save/reopen and source/version provenance. Output is retained locally in ignored `.test-artifacts/gwyddion-native-tests.log`.
- Built the real Gwyddion 2.71 libraries: 26 `libgwyddion` and 48 `libprocess` upstream source files plus the production adapter, without GTK or OpenMP. Loaded the resulting 11-dylib closure from a fresh temporary directory in a fresh process with no `DYLD_*` environment: version 2.71, ABI 1, initialization successful. Dependency references resolve to sibling libraries or Apple system libraries.
- Compiled and executed selected unchanged **Gwyddion 2.71 C routines** using the [reference harness](../scripts/check_gwyddion.py). The [committed synthetic fixtures](../tests/fixtures/gwyddion-2.71.json) cover nine alignment choices, six masked cases, Matching evaluated in SI units, two plane fits, moments/median and four profiles. Regenerating the fixture produced an identical JSON file. Source-file and archive hashes are recorded.
- Production C results agree with the recorded upstream arrays within declared test tolerances (alignment `rtol=2e-13`, `atol=5e-13`; profiles/statistics `1e-13`; plane `1e-12`). Native surface polynomial fitting additionally has analytical ground-truth tests for both degree modes, masks and reconstructed backgrounds.
- `scripts/gwyddion-smoke.cjs` passed against the native-backed service: all nine method choices, row/column axes, metadata-required auto behavior, degree/trim controls, plane/polynomial/reference controls, preview isolation, save/reopen/undo, immutable raw data, live profile width/interpolation, expanded statistics and a 900 × 650 layout. Screenshots were inspected. The existing processing smoke also passed, including automatic-terrace fitting/fallback and manual reference leveling.
- Collected the exact upstream source archives, dependency recipes/patches and original notices used by the Mac build; the corresponding-source archive generated successfully. Generated libraries and source bundles are excluded from Git; reproducible build/collection scripts and pins are committed.
- Rebuilt the approximately 62 MB arm64 Mac application and generated its approximately 35 MB corresponding-source archive. The build's final local ad-hoc signature verification passed. The workspace file provider subsequently reattached Finder metadata, causing a later signature check to fail; removing that generated metadata restores verification. Launched the packaged executable with a separate synthetic catalog and reran the Gwyddion browser workflow successfully against its bundled native libraries. This checks the packaged loopback runtime in Chrome, not a new native WebKit/file-dialog acceptance run. Inspected the source archive for required adapter/application/license/fixture files and absence of experimental TIFFs, catalogs and native binaries.

The production runtime uses real Gwyddion objects and libraries; the separate fixture generator's simplified object adapter is test-only. This evidence is **not a complete Gwyddion GUI comparison**, experimental calibration or Windows validation. See the [compatibility audit](gwyddion-compatibility.md) for preserved source quirks, finite-data safeguards, import orientation differences, custom analysis methods and legacy replay.

Run date: 2026-11-09, America/Los_Angeles. Evidence origin: executed local checks, not historical comments. Claim status: implementation validation within the limits below.

## Executed successfully

| Check | Evidence |
| --- | --- |
| Importer, numerical core, catalog, HTTP and MCP adapter tests | `python -m unittest discover -s tests -v`: **32 passed**, no skips, on the local Mac with Python 3.12.14, NumPy 2.3.5, Pillow 13.0.0. The HTTP test ran with loopback binding permitted. |
| Browser workflow | `scripts/ui-smoke.cjs` passed against a separate synthetic workspace in Chromium. Verified folder grouping, positioned map, direction filter, comparison, contrast invariance, unsaved preview isolation, correction apply, full-resolution profile, undo, CSV download, notes persistence after reload, and a 1000 × 760 window without horizontal overflow. No browser console errors. |
| Height-first UI refinement | The expanded browser smoke run passed 23 workflow checks on 2026-11-09. Synthetic metadata fixtures verify exact Z-height priority, matching error direction and footprint, missing-height fallbacks, and access to all channels. Searches and stars expose matching backward images; clicking the active channel preserves previews and profiles. At 900 × 650, the full height canvas retains its physical aspect ratio and the inspector scrolls within the window. The Mac bundle was rebuilt and its local ad-hoc signature verified after the UI changes; this revision's visual checks used Chromium. |
| Private local Park session | 16 TIFFs imported into one session. Eight forward and eight filename-labeled backward images. Original file SHA-256 hashes unchanged. Two acquisition footprints, eight images per footprint. |
| Spatial coordinates | Both acquisitions have 20 × 20 µm extents. Centers are (0, 0) and (20, 0) µm, giving metadata footprint coverage x = −10…30 µm, y = −10…10 µm. Offset-as-center semantics were checked against Park's manufacturer documentation in [formats](formats.md). |
| Anisotropic pixel sampling | Local images are 1024 × 512 or 1024 × 256 pixels but 20 × 20 µm physically. The browser displayed calibrated square footprints and a square analysis canvas; pixel counts remain explicitly shown. |
| Persistence and provenance | Tests reopen the SQLite workspace, recover notes/stars/review/recipes, replay and undo, preserve measurement provenance, export full-resolution numerical CSV, and distinguish display settings from numeric operations. |
| Mac application build | `python scripts/build.py` produced a roughly 50 MB arm64 `dist/AFM Workbench.app`. Local ad-hoc codesign verification passed. |
| Native app | The built app launched using the system WebKit renderer, imported the 16 TIFFs into its normal application workspace, and displayed the contact sheet and two-footprint sample map. The native map was visually inspected. |

Local screenshots and test outputs are saved under ignored `.test-artifacts/`. They include private experimental images and must not be committed or redistributed without permission. Private files are not a requirement for the automated test suite. Tests generate their own TIFFs and numerical surfaces.

## Post-processing revision, 2026-11-09

Executed after the capped terrace fitting and scan-direction-aware alignment changes:

- **41 tests passed, no skips**, including the loopback HTTP integration test. New synthetic ground truth covers one/two/three tilted terraces, no dominant terrace, noise, NaNs, float32 quantization, preserved height offsets, six-terrace/curved/nonparallel rejection, manual reference support, recipe replay, immutability and metadata axis selection across swap/angle/trace combinations. GUI service and MCP preview results match.
- The existing `scripts/ui-smoke.cjs` passed all 23 workflow checks in local headless Chrome with the revised manual controls.
- `scripts/processing-smoke.cjs` passed automatic three-plane preview, fitted-plane/assignment inspection, preview isolation, save/reopen, undo, automatic row selection from imported metadata, rejection without catalog changes, and manual ROI leveling after rejection. It generates only synthetic TIFFs. Run against a disposable loopback workspace with installed Python dependencies and Playwright; set `AFM_PYTHON` and `AFM_PLAYWRIGHT_MODULE` if using an existing environment.
- Synthetic screenshots `terrace-fit.png` and `manual-level-fallback.png` were visually inspected. Processing controls remain in the scrollable inspector; numerical images retain their physical aspect ratio.

The new fit gates are heuristics tested on synthetic cases, not established instrument validation. Real swapped-axis files, nonparallel-terrace automatic correction, Windows execution, and a rebuilt native bundle for this revision have not been validated. Previous native-build evidence above predates this processing revision.

## Real-sample processing check, 2026-11-09

A separate ignored test catalog imported all 16 private local TIFFs as one session. Four Z-height images (two acquisitions, forward and filename-labeled backward) were tested at full resolution through the application service. No algorithm or acceptance thresholds were changed for this check.

- Automatic 1–3-plane fitting accepted **0/4** raw height images and **0/4** after scan-line alignment. All candidate residuals exceeded the current noise-based gate. Rejected previews left the active analysis unchanged; rejected saves added no run or active-recipe change.
- Metadata-directed alignment executed on all four height images and resolved to stored rows. This confirms code execution and axis selection, not that every removed offset is an acquisition artifact.
- Visual-reference manual plane leveling after row alignment passed preview, save, reopen and undo on all four. Reference rectangles were proposed by AI visual inspection and are retained in the private report; they are not verified substrate identifications or validated physical measurements.
- Headless Chrome exercised rejection, visible manual fallback, row-axis selection, drawn-reference manual preview and restoration on both forward height images, with no JavaScript exceptions. Screenshots were inspected.
- All 16 original TIFF SHA-256 checksums remained unchanged. Private reports, arrays and comparisons are confined to ignored `.test-artifacts/real-processing/`; no real data were added to public fixtures.

**Outcome:** the manual fallback functions on this dataset, but automatic processing has not succeeded on it. The bounded fit search sometimes returns a worse three-plane candidate than its two-plane candidate, showing initialization sensitivity. These observations do not establish the actual number of layers, prove that the sample cannot be described by three planes, or justify relaxing acceptance thresholds without further validation.

## AFM-aware automatic mode v2, 2026-11-09

- **50 backend tests passed with no skips**, including HTTP and MCP. Additional synthetic tests cover one to three tilted terraces, preserved 1.2 nm steps under row drift/noise, retained particle amplitude and within-line texture, guarded full-width steps, nonparallel terrace tilt differences, disconnected islands sharing a plane, transpose/axis equivalence, NaNs, masks and exact replay. Six-terrace and fast-axis-curvature fixtures reject without input modification. Legacy v1 recipes remain on the unchanged v1 implementation.
- The private real session was rerun in an isolated catalog: **3/4 height images accepted**, including both forward scans; one backward scan retained an ambiguous full-line jump and exceeded the three-plane limit. The fallback remained active. Accepted fitting support covered 91.6–97.4% of reference pixels. These are quality-gate outcomes, not physical validation of the corrected topography or identified layer counts.
- Accepted real runs passed preview isolation, save/reopen and undo. All 16 original TIFF hashes remained unchanged. Private comparison images, masks and reports are under ignored `.test-artifacts/auto-v2/`.
- The existing 23-check browser smoke suite passed. The updated processing smoke suite also passed against the rebuilt Mac bundle, including the scan-correction off switch, fitted-background inspection, save/reopen, undo and manual ROI fallback. Real-data automatic preview and ambiguous backward-scan fallback passed in the packaged runtime through headless Chrome. Screenshots were visually inspected.
- The Mac bundle was rebuilt and its local ad-hoc signature verified. These revision checks exercise the packaged loopback runtime and Chrome; they do not claim a new native WebKit or Windows acceptance run.
- Line background removal remains physically ambiguous for slow-axis curvature and small/nonuniform full-line features. The GUI exposes an off switch; none of these tests establishes that every removed component in the real data is instrumental.

## Sample-map overlap revision, 2026-11-09

- `scripts/map-smoke.cjs` passed 14 groups of checks in local headless Chrome against both the source server and rebuilt Mac bundle. Synthetic metadata covers nested and coincident acquisitions, rotated containment and boundaries, empty-space rejection, Focus/All images/Outlines, selected-layer ordering, one map label, channel opening, keyboard activation, filtered selection identity, missing positions and explicit height fallbacks. Zoomed hit testing passed at 1440 × 1000, 900 × 650 and 700 × 850, including SVG letterboxing. Selected channel controls remain inside the scrollable acquisition list. Metadata and saved recipes remained unchanged.
- The existing `scripts/ui-smoke.cjs` passed all 23 workflow checks. All **50 backend tests passed, no skips**, including loopback HTTP checks.
- A separate existing private test catalog displayed 13 positioned footprints from the expanded session. Clicking a shared area within Scan 009 offered all three footprints containing that point; selecting Scan 009 brought its image forward. Browser scan metadata and recipes remained unchanged. Local screenshots of Focus and the overlap chooser were inspected and remain under ignored `.test-artifacts/map-overlap/`.
- The Mac bundle was rebuilt and launched in loopback mode. Local ad-hoc signature verification passed after removing Finder metadata from the generated bundle; the file provider can reattach that metadata in this workspace. These checks used Chrome, not a new native WebKit or Windows acceptance run.

These are interface and geometric-selection checks. They do not establish image registration, stage positioning accuracy, or physical agreement between overlapping measurements. No blending, coordinate adjustment or numerical processing was added.

## Inspector workflow refinement, 2026-11-10

The following checks were executed against the revised interface using synthetic data and local Chrome. These are interaction/layout checks, not a user study or new scientific validation.

- The backend suite ran 103 tests: 102 passed and the loopback HTTP test was initially skipped by the execution sandbox. The nine service tests were then rerun with loopback access; all nine, including HTTP, passed.
- `scripts/ui-smoke.cjs` passed its 23 workflow checks. `scripts/masking-display-smoke.cjs`, `scripts/gwyddion-smoke.cjs` and `scripts/processing-smoke.cjs` also passed after their navigation was updated for the task tabs. Existing assertions cover immutable originals, saved-mask snapshots, display invariance, profile/area measurements, correction preview/save/undo and rejected-fit manual fallback.
- `scripts/inspector-smoke.cjs` passed task-tab keyboard navigation without changing acquisition, exact untouched numeric endpoint retention, keyboard range adjustment, mask tool settings, ROI/profile preservation across tabs, fit-reference versus measurement scope, disclosure/scroll retention and preview decisions reachable at 900 × 650. Leaving a drawing tool preserves the completed profile.
- Focused display checks covered distinct numeric fields for 1000 versus 1000.000000001, large negative offsets, full-precision stored values, repeated keyboard adjustments retaining focus and click access from a focused numeric field. The compact contrast section measured about 298 px tall at the tested desktop width.
- Screenshots of View, Prepare, Measure, Record and the compact preview were inspected. The image retains its physical aspect ratio; the active inspector panel scrolls independently. Navigation and preview decisions stay outside that scrolling area. No browser JavaScript exceptions were recorded in the passing suites.
- The Mac bundle was rebuilt and the final inspector suite passed against its loopback runtime, including repeated keyboard range adjustment and the saved preview-reference label. Local ad-hoc signature verification passed during the build after removing generated Finder metadata. As in earlier builds, this workspace's file provider can reattach that metadata afterward. These checks use Chrome, not native WebKit.

The [design rationale](interface-design.md) distinguishes community reports from our design inferences. Improved characterization speed has not been measured. Windows and native WebKit rendering of this revision have not been tested.

## Ease-of-use rework, 2026-11-12

Interface review and rework (`origin: AI; claim_status: decision`, within the 2026-11-09 implementation authorization). Executed checks, not a user study:

- The backend suite ran 112 tests, all passing, including a new check that leveled browse thumbnails leave the stored recipe, statistics and data unchanged, never re-level a processed image and skip non-height channels.
- On a copy of the local Park session, display-only line + plane thumbnails took about 20–40 ms per height image. The Scan 002 forward thumbnail changed from a slow-axis gradient to visible particles and terraces. Synthetic data without a recorded scan axis falls back to plane-only leveling.
- In the browser pane (Chromium, 1440 × 900 and 1100 × 700): the contact-sheet toggle, Forward/Backward header button and **B**, **K** to keep and **X** to discard a preview, blocked-tool feedback during a preview, line profile after keeping, the pending step in Record, and the collapsed **More corrections** group were exercised without JavaScript errors or horizontal page scroll.
- The Playwright smoke scripts were not rerun (Node is not installed in this environment); their selectors for the removed View-tab links and the renamed corrections disclosure may need updating.

Native WebKit, Windows and the packaged app were not tested for this revision.

## Direct corrections without preview, 2026-11-12

At the user's request (`origin: human; claim_status: decision`), the Keep result / Discard preview step was removed. Corrections, including automatic leveling on opening an unprocessed height image, are saved to the recipe when applied; undo removes the last step and originals stay immutable.

- The backend suite ran 112 tests, all passing (no backend change).
- In the browser pane on a copy of the local session: opening Scan 003 forward saved `auto_characterize` with no decision bar and offered Undo; Profile was available immediately; **Subtract reference plane** saved a second step; a real ⌘Z and the message's **Undo** each removed the last step.
- The Playwright smoke scripts still drive **Keep result** / **Discard** and must be rewritten for direct apply before they can pass. They were not run (no Node in this environment).

## Scan-line method strip, 2026-11-12

Requested by the user (`origin: human; claim_status: decision`): scan-line alignment moved to the top of Prepare as direction and method buttons that apply on click. Each recipe holds one scan-line slot. A method replaces any earlier explicit alignment in place; with Auto level present, it disables Auto level's terrace-aware line correction and is inserted before it. Undo restores the previous recipe.

- Browser pane, on a copy of the local session's Scan 003 forward (saved Auto level): Median, Columns, Undo, Off and Terrace produced the expected recipes. Median of differences and Median kept Auto level. Mean, Matching, Modus, Polynomial and Trimmed mean made Auto level's plane gate reject the result (5–6 candidate planes, or no 1–3 plane model). The app then kept the chosen method, removed Auto level and showed the three-point notice. ⌘Z restored Auto level.
- The backend suite passed (no backend change). Playwright smoke scripts were not run.

The plane-gate rejections are recorded as observed on one image; they do not rank alignment methods.

## Interpretation and remaining verification

- Synthetic fixtures establish known numerical and file-layout behavior. They do not prove absolute instrument calibration accuracy or constitute independent Gwyddion validation.
- All eight files named Backward have a Forward header flag. Filename labels are used for browsing; the original flag and conflict warning are retained. Array orientation and trace/retrace registration are not silently inferred from those names.
- The spatial overview uses scanner-relative metadata and recorded scan extents. Stage motion, drift, stitching, blending and image registration are not validated or performed.
- MCP protocol and shared-core behavior were tested through local JSON-RPC requests. A separately configured external MCP client has not been tested.
- Windows installation, native rendering, file dialogs and the Windows bundle have not been executed here. Native build instructions describe the remaining Windows gate; the revised CI matrix builds/tests Mac and Linux. No remote workflow run is claimed.
- Mac native startup and rendering are verified; a complete native file-picker/export-dialog acceptance pass and signed/notarized public distribution remain release work. The local ad-hoc signature is not a Developer ID signature.
- Multi-user shared storage and arbitrary import formats are outside this implementation. Performance has been exercised on this 16-image session, not a large institutional collection.

## Folder management and background imports — 2026-11-13

Executed on macOS arm64 using generated Park TIFF fixtures (`origin: AI`; `claim_status: verified` for these software checks):

- The full Python suite passed 116 tests, including HTTP token/origin checks. New tests cover updating while decoding is deliberately paused: bootstrap, image access, thumbnails and folder listing stay responsive. Cancellation completes the current file, preserves saved recipes and resumes without duplicate imports; a second concurrent background import is rejected.
- Archive/restore and reconnect retain session/scan IDs, names, notes and saved arrays. Reconnect records former folder locations and retains each image's original import path. A source already assigned to another session is rejected. Migration from the previous catalog schema retains existing scans.
- `scripts/folders-smoke.cjs` passed the browser workflow for initial import, unchanged-file skipping, added/changed files, preservation of an earlier recipe, per-file errors, unavailable-source errors, reconnect, rename/notes, archive/restore and persistence. It uses generated fixtures and a disposable catalog.

The Mac application and corresponding-source archive were rebuilt. Local ad-hoc signing and verification passed after adding a final bundle-root Finder-metadata cleanup to `scripts/build.py`. The complete folder browser workflow also passed against the packaged executable and bundled native libraries, using a separate synthetic catalog; see `.test-artifacts/folders-build.log` and `.test-artifacts/folders-packaged-smoke.log`. The folder view was inspected at 900 × 650 without horizontal overflow. These are Chrome checks of the packaged loopback runtime, not native WebKit/file-dialog acceptance tests.

The code inspection identified a catalog-wide lock spanning all import I/O/decoding and a list retaining every new array until the final transaction. The revised importer prepares and commits files incrementally outside that long lock. This is evidence for the tested blocking path, not a reproduction of the user's particular folder or a guarantee about stalled network-storage calls. Cancellation waits for the current file operation. Native file-dialog behavior and Windows execution were not tested in this revision.

## Folder drag-and-drop, 2026-11-13

Executed software checks on macOS arm64 (`origin: AI`; `claim_status: verified` for the checks listed here):

- All 121 Python tests passed, including loopback HTTP checks and five new desktop-drop tests covering directory validation, missing native paths, quoted Unicode paths, multiple items, and ignored text/internal drags. JavaScript syntax checking passed.
- `scripts/folder-drop-smoke.py` passed against the rebuilt executable's loopback runtime and bundled frontend, using a disposable catalog and generated Park TIFF fixtures. A native WebKit window registered the production desktop bridge and dispatched synthetic DOM drop events with a supplied pywebview native-path cache. The visible drop target, quoted Unicode path, background import of three images, repeat import with three unchanged files, file/multiple-folder rejection, and three-image contact sheet passed.
- The Mac desktop bundle launched and rendered its empty library. The bundle and corresponding-source archive were rebuilt; ad-hoc signing and verification passed. Logs are in `.test-artifacts/folder-drop-build.log`, `.test-artifacts/folder-drop-tests.log` and `.test-artifacts/folder-drop-native-smoke.log`.

Native full-path delivery uses the documented [pywebview DOM drop handler](https://pywebview.flowrl.com/examples/drag_drop). The automated bridge check supplies the path cache normally populated by the operating system. A cross-window Finder drag was attempted through computer automation but did not produce a confirmed import; the OS drag gesture remains unverified. Windows/File Explorer execution has not been tested. Browser development mode retains path-based import and explains that folder drops require the desktop app. No scientific processing changed.

## Processing performance, 2026-11-13

Executed software checks on macOS arm64 (`origin: AI`; `claim_status: verified` for these checks). Profiling the previous service showed one processing action evaluating the same recipe three times: for saving, for the returned image, and for contrast. A 512 × 512 auto-characterization response contained about 6 MB of JSON, with repeated Python traversal of its numerical pixels. The revised service reuses exact results and transfers display samples losslessly as float64 bytes; the scientific algorithms and full-resolution analysis remain unchanged.

The same native WebKit workflow was run against the previous source revision and the optimized source runtime, each using a separate disposable catalog. The generated Park TIFF contains a tilted two-terrace surface with deterministic noise, 512 × 512 pixels. Timings below are single local observations, including HTTP, decoding, rendering and two animation frames. They are not median/tail estimates, instrument-data validation, or guarantees for larger images.

| Action | Before (ms) | Optimized source (ms) |
| --- | ---: | ---: |
| Open image | 202 | 72 |
| First auto level | 567 | 179 |
| Append plane correction | 568 | 67 |
| Undo | 557 | 50 |
| Append another auto level | 930 | 182 |
| Replace line method | 539 | 167 |
| Rectangle contrast | 163 | 22 |
| Line profile | 140 | 29 |
| Show original | 175 | 50 |
| Plane correction with saved mask | 999 | 236 |
| Repeat thumbnail | 136 | 1 |

- All 128 Python tests passed, including loopback HTTP security tests. The seven added tests cover replay reuse, exact prefix equivalence, edited earlier steps, eviction/restart, independent returned histories, read-only cached arrays, fixed mask snapshots, thumbnail invalidation, failed-recipe atomicity, bounded LRU eviction, and exact float64/NaN transport with the original JSON contract retained.
- `scripts/performance-smoke.py` passed in native WebKit against the optimized source runtime. It exercises direct apply, undo, line replacement, exact ROI contrast, profile measurement, unchanged originals, mask snapshots, rejected fits, thumbnail reuse, and RGBA agreement with the existing interpolation across all palettes. Logs: `.test-artifacts/performance-baseline-webkit.json`, `.test-artifacts/performance-source-webkit.json`, and `.test-artifacts/performance-full-tests.log`.
- The Mac bundle and corresponding-source archive rebuilt successfully; local ad-hoc signing and verification passed. The source archive contains the staged new files and matches the implementation, and bundled JavaScript matches the source. The same native script passed with `--expect-compact` against the rebuilt executable's `--browser` endpoint: first auto level 195 ms, appended plane 67 ms, undo 50 ms, rectangle contrast 36 ms, and masked plane 246 ms. The server and assets came from the bundle while the test window used native WebKit. Logs: `.test-artifacts/performance-build.log` and `.test-artifacts/performance-packaged-webkit.json`.

No Windows performance measurement was run. Large catalogs and very large arrays remain unbenchmarked. Cache memory has fixed bounds; a cold or evicted expensive recipe still requires computation.


## Canvas interaction, 2026-11-14

The user requested restoration of contrast-region selection and refinement of canvas mouse interaction (`origin: human; claim_status: decision`). The following are executed software checks on synthetic data on macOS arm64, not measured usability improvements or instrument validation.

- All **128 Python tests passed, with no skips**, including loopback HTTP security and delivery of every script/style asset declared by the production page. Changed JavaScript parsed in the system JavaScriptCore engine; Git whitespace checks passed.
- `scripts/canvas-smoke.py` passed **16 check groups in native WebKit** against both source and the rebuilt application's loopback runtime. It checks discoverable selection, exact full-resolution ROI limits, retention through tools/tabs/corrections/undo, moving and resizing, tiny/flat drag rejection, Escape/cancel/blur/lost-capture recovery, rapid consecutive requests, failed-request rollback, anchored zoom, Space/middle/Pan navigation, Original panning, normalized coordinates under zoom, and Clear without changing limits or original pixels. Production pointer routes for profile, area, two-region step and masks passed, including mask inclusion/exclusion and temporary-pan selection retention. A generated 64 × 64 Park TIFF with an 8 × 4 µm footprint verifies physical aspect and image/mask/selection alignment. The 900 × 650 window check passed without horizontal page overflow. Log: `.test-artifacts/canvas-packaged-webkit.json`.
- The same native test dispatches DOM events and emulates pointer capture because synthetic pointers are not registered with the OS. A separate computer-use check visibly drew a contrast rectangle through ordinary pointer input. Physical trackpad/pinch hardware and Windows execution were not tested.
- `scripts/performance-smoke.py --expect-compact` passed against the rebuilt executable and its bundled native libraries in a native WebKit test window: direct corrections, undo, line replacement, ROI contrast, profile, unchanged originals, fixed mask snapshots, rejected-fit atomicity, thumbnail reuse and canvas color interpolation. Log: `.test-artifacts/canvas-packaged-processing.json`.
- The Mac bundle and corresponding-source archive were rebuilt with the new files staged. PyInstaller's default cache is outside the writable workspace, so the local build used `PYINSTALLER_CONFIG_DIR=.test-artifacts/pyinstaller-cache`. The synchronized workspace reattached Finder metadata during signing; clearing the generated bundle root's Finder metadata and repeating local ad-hoc signing/strict verification succeeded. No quarantine or security attributes were removed. Build log: `.test-artifacts/canvas-build.log`.

See the [design rationale](interface-design.md#canvas-interaction-revision-2026-11-14) for the documented Figma/Photoshop interaction references. The contrast outline lasts while its image remains open; reopening restores saved numeric limits without restoring the temporary outline. These checks do not establish improved characterization speed, Windows compatibility, Developer ID signing or notarization.


## Canvas fluidity, 2026-11-14

Executed software checks on macOS arm64 (`origin: AI; claim_status: verified` for the recorded runs), following the user's performance/fluidity request (`origin: human; claim_status: decision`). The baseline used the unchanged previous Mac bundle (source revision `43de1b2`); the optimized source used the same native WebKit benchmark and synthetic 1024 × 1024 Park TIFF, displayed at the normal 512 × 512 resolution. Each of seven phases dispatches 240 DOM events in 20 animation-frame bursts. Pointer capture is emulated. Measurements include instrumented JavaScript handlers and scheduled callbacks, not physical-device latency, compositor/GPU work or instrument validation. P95 values describe this bounded local run, not production latency guarantees.

| Measure | Previous bundle | Optimized source |
| --- | ---: | ---: |
| Live contrast: p95 JavaScript work per 12-event burst | 32 ms | 3 ms |
| Live contrast: p95 observed frame interval | 34 ms | 19 ms |
| Live contrast: pixel writes for 240 events | 240 | 20 |
| Live contrast: DOM mutations | 3940 | 280 |
| Pan: instrumented geometry/style queries | 240 / 480 | 0 / 0 |
| Contrast draft: full-overlay child replacements | 479 | 0 |
| Image canvas retained across tool changes | No | Yes |

The implementation separates fitted layout measurement from viewport transforms, coalesces presentation at animation-frame cadence and reuses image/draft/pixel-buffer objects. Every accepted brush sample is still recorded for the saved full-resolution mask. Zero instrumented geometry/style queries in measured input phases means no explicit `getBoundingClientRect` or `getComputedStyle` calls in those phases; it does not claim the browser performs zero internal layout work.

- `scripts/fluidity-smoke.py --expect-coalesced` passed all **15 checks** against source: latest hover sample; release flushing; every wheel/pinch delta and fixed zoom anchor; exact ROI limits; complete brush-path coverage; final live/saved slider values; pending-frame cancellation and Fit; immediate slider release; stationary contrast/brush previews through static refresh; clean cancel; stale-hover prevention; Set before a slider frame; preserving typed numeric precision; immutable numerical arrays/recipes; bounded visual work and retained canvas. Logs: `.test-artifacts/fluidity-baseline-webkit.json` and `.test-artifacts/fluidity-source-webkit.json`.
- `scripts/canvas-smoke.py` passed its **16 native WebKit check groups** against the optimized source, including corrections/undo, mask inclusion/exclusion, profile/area/step pointer routes, physical rectangular calibration and 900 × 650 layout. Log: `.test-artifacts/fluidity-canvas-source.json`.
- All **128 Python tests passed, no skips**, including loopback HTTP checks. Changed JavaScript parsed in the system JavaScriptCore engine and Git whitespace checks passed. Log: `.test-artifacts/fluidity-tests.log`.

- The rebuilt Mac runtime passed all **15 fluidity checks**, **16 canvas check groups**, and the existing native processing workflow (`--expect-compact`), including correction/undo, mask snapshots and exact palette interpolation. The packaged fluidity run recorded p95 live-contrast work of **4 ms**, p95 observed frame intervals of **19 ms**, and **20 pixel writes** for 240 input events. Logs: `.test-artifacts/fluidity-packaged-webkit.json`, `.test-artifacts/fluidity-packaged-canvas.json` and `.test-artifacts/fluidity-packaged-processing.json`. An initial packaged canvas run timed out without returning a result; adding timeout-progress diagnostics and rerunning passed all groups. The timeout's cause was not established.
- `.venv/bin/python scripts/build.py` succeeded with `PYINSTALLER_CONFIG_DIR=.test-artifacts/pyinstaller-cache`, producing the Mac bundle and corresponding-source archive. All changed source files and bundled frontend assets were compared byte-for-byte. The refreshed `dist/AFM-Workbench-macOS.zip` was staged outside the synchronized folder, extracted, checked against source and passed strict ad-hoc signature verification. Only generated Finder/resource metadata was cleared; quarantine and security attributes were retained. Logs: `.test-artifacts/fluidity-build.log` and `.test-artifacts/fluidity-packaging.log`.

See [architecture](architecture.md#canvas-fluidity) for implementation and reproduction commands. No Windows run or physical trackpad measurement is claimed. Large-catalog browsing and larger display buffers have not been profiled by this test.

## Collapsible processing UI, 2026-11-14

Executed software checks on macOS arm64 (AI-recorded local runs, claim status: verified) after the user's request to hide on-canvas processing elements with a small arrow on the right.

- Rebuilt the Mac application and corresponding-source archive using `PYINSTALLER_CONFIG_DIR=.test-artifacts/pyinstaller-cache .venv/bin/python scripts/build.py`; the build's local ad-hoc signature verification passed. Log: `.test-artifacts/hide-controls-build.log`.
- `scripts/canvas-smoke.py` passed 20 check groups in native WebKit against the rebuilt application's loopback runtime and a disposable synthetic catalog. New assertions cover the compact rightmost arrow, inspector/toolbar/measurement-panel collapse, hidden mask and all SVG guides, unchanged contrast and mask settings, preserved profile/area/step/leveling selections, blocked drawing while hidden, retained zoom and pan, restoration by tool/tab shortcuts, and the visibility preference after an actual page reload. Current-view PNG mask pixels disappear and return with the toggle without changing saved mask visibility. Existing canvas, correction/undo, physical-aspect and immutable-pixel checks also passed. Log: `.test-artifacts/hide-controls-packaged-canvas.json`.
- A separate computer-use check visibly confirmed the arrow and collapsed canvas in the rebuilt runtime. A 900 × 650 native window retained access to the arrow without horizontal page overflow.

The native regression dispatches synthetic DOM events and emulates pointer capture. These checks establish UI behavior on this Mac; they do not establish physical-device input behavior or Windows compatibility. The toggle changes display visibility, not numerical processing or saved mask participation.

## Publication readiness, 2026-11-14

Executed local software checks on macOS arm64 (`origin: AI`; `claim_status: verified` for the recorded checks). This review concerns source publication and the local Mac build, not scientific validation of experimental samples or acceptance on other platforms.

- Audited tracked Workbench source for credential patterns, private machine paths, experimental data, catalogs and native binaries; none were found in that targeted scan. All relative Markdown file targets resolved. This project is nested in a larger repository: the [publication workflow](publishing.md) requires exporting only its source tree into a separate repository, without the enclosing history.
- Corrected current README, scientific-workflow documentation and two UI messages that still described removed Keep/Discard controls. Raised the setuptools build requirement to `77.0.3` for the declared SPDX license string.
- Added dependency-notice collection from PyInstaller's actual module/binary inventory. The rebuilt bundle contains verified notice files for **15 Python distributions**, the Python runtime notice and the legacy Workbench MIT grant. Installed versions and notice hashes are recorded in `licenses/python/manifest.json`; incomplete wheel notices use version-specific upstream files with recorded URLs and checksums. Missing notices stop packaging. This is an inventory check, not blanket legal clearance for future distributions.
- The full Python selection ran **141 tests**. Its HTTP security test was initially skipped because sandbox policy prevented loopback binding; the service suite was then rerun with loopback access and all 14 tests passed. Four new packaging checks and the 13 runner checks passed after the packaging changes. Thus **145 distinct current Python tests passed**, with no remaining skipped test. Reports: `.test-artifacts/runs/20261115T000527.092527Z/report.json`, `20261115T000600.234028Z/report.json`, and `20261115T000752.755898Z/report.json` under the same runs directory.
- All **seven active integration checks** passed against the rebuilt executable: `runtime`, `map-ui`, `folders-ui`, `canvas`, `fluidity`, `processing-latency`, and `folder-drop-ui`. Each used a disposable synthetic catalog. Browser checks used local Chromium; native checks used development pywebview/WebKit against bundled service/assets. Report: `.test-artifacts/runs/20261115T000818.807341Z/report.json`. The separate packaged desktop executable also opened its native window and synthetic contact sheet successfully, observed through computer use; its disposable process was then stopped.
- Exported tracked source, built a wheel offline, installed it into an isolated temporary environment, and passed the HTTP/native synthetic runtime smoke with isolated Python imports. All nine frontend assets were present. This check reused local NumPy/Pillow distributions and copied the current native library closure; it did **not** perform a fresh native compile or download dependency packages. Evidence copied to `.test-artifacts/publication-install/`.
- `.venv/bin/python scripts/build.py` succeeded with `PYINSTALLER_CONFIG_DIR=.test-artifacts/pyinstaller-config`; local ad-hoc signing and strict verification passed. Bundled frontend files matched source byte-for-byte, and every collected notice matched its manifest hash. The corresponding-source archive included the new tracked files, had normalized owner IDs/names in every tar header, and contained no private-data or local-environment paths. Log: `.test-artifacts/publication-build.log`.

The 22 active catalog checks were covered across the runs above. The six legacy browser scripts remain excluded for their documented obsolete preview assertions; full contact-sheet/channel/comparison/export and inspector/method-matrix browser coverage is still incomplete. The reference generator is a maintenance task and was not run. CI is configured for Mac/Linux Python checks but was not executed on GitHub during this review. No Windows build, clean-machine installation, Developer ID signing, notarization, physical trackpad test or new experimental-data validation is claimed. Source publication and binary-release requirements are distinguished in [publishing](publishing.md).
