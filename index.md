---
type: project-index
created: 2026-11-09
updated: 2026-11-14
status: implementation
origin: AI
claim_status: proposal
---

# AFM Workbench

AFM Workbench is a standalone local application for AFM analysis, intended for a public GitHub repository. It combines a graphical desktop interface, agent access through MCP, and a searchable session library. Start with the [README](README.md) for installation and the daily workflow.

## Confirmed Direction

`origin: human`; `claim_status: decision`; source: project-creation discussion, 2026-11-09.

- The initial design-first phase was superseded by the user's explicit authorization to build and make independent product decisions on 2026-11-09.
- Develop a self-contained public GitHub project with portable documentation and its own data model.
- Support Mac and Windows desktop first, with a shared database later.
- Prioritize height maps, flattening, profiles, step heights and roughness, plus vertical/horizontal line alignment, leveling and quick contrast adjustment.

- One folder is one AFM session; all its images must be presented together (`origin: human; claim_status: decision`).
- Use the TIFF position/offset metadata to build a spatial overview of the sample (`origin: human; claim_status: decision`).
- Keep the interface compact and neutral, with Z height as the primary image. Default to one forward Z-height image per acquisition with its matching error signal and other channels alongside; keep metadata and other directions accessible without a dashboard banner (`origin: human; claim_status: decision`; UI refinement request, 2026-11-09).

Post-processing decision (user, 2026-11-09): offer 2D-material automatic leveling with at most three fitted terrace planes; if fitting fails, leave data unchanged and direct the user to manual reference-area leveling. Line alignment follows recorded scan direction. See [numerical methods](docs/science.md) for the reference-plane and scan-background assumptions and fit gates.

Implementation choices: Park SmartScan TIFF first; row/column offset alignment; optional external agents through MCP; Python/pywebview desktop shell and local HTML interface. See [implemented architecture](docs/architecture.md) for scope and [validation status](docs/validation.md) for evidence.

Gwyddion backend, 2026-11-10: the user approved direct C routines and GPL distribution. Current explicit-method corrections, statistics and profiles call the real Gwyddion 2.71 scientific libraries through a local C ABI. All eight row/column alignment methods plus mean, plane/polynomial backgrounds, zero references, masks, expanded statistics and width-averaged profiles share this native backend. Existing methodless recipes retain their original numerical behavior. See the [native build](native/README.md) and [compatibility audit](docs/gwyddion-compatibility.md) for evidence, API choices and deliberate differences. Custom terrace processing and two-region step measurement are separately identified.

Mask and color controls, 2026-11-10: editable rectangle/brush/value-threshold masks, add/erase, invert, clear and mask undo/redo persist with each image. Include/exclude/ignore choices apply to corrections and analysis; saved results retain fixed mask snapshots. Full-resolution histogram, numeric color limits, percentile and selected-area ranges are separate display settings. See the [workflow](README.md#masks-and-color-limits) and [selection/display conventions](docs/science.md#editable-masks-and-display-state).

Inspector refinement, 2026-11-10: View, Prepare, Measure and Record tabs replace the long control stack. Compact histogram/range controls, direct mask tools, persistent preview decisions, explicit fit-reference scope and keyboard access support the characterization workflow. Exact display limits and scientific operations are preserved. The [design rationale](docs/interface-design.md) traces the choices to established imaging/productivity interfaces and qualitative community feedback; executed checks are recorded in [validation](docs/validation.md#inspector-workflow-refinement-2026-11-10).

Sample-map overlap handling, implemented 2026-11-09: Focus, All images and Outlines views; selection from every acquisition under a clicked point; a single selected-scan label; and a scrollable acquisition list with channel access. Positions remain fixed. See the [workflow](README.md#a-pis-quick-pass) and [executed overlap checks](docs/validation.md#sample-map-overlap-revision-2026-11-09).

## Current State

Publication review, 2026-11-14: corrected stale preview instructions, raised the build-tool minimum for SPDX metadata, included exact Python dependency notices in the Mac bundle, and removed local account identifiers from source-archive headers. All 145 current Python tests and seven rebuilt-runtime/browser/native-window checks passed across the recorded runs; an isolated source-wheel installation and packaged desktop startup also passed. Six legacy browser scripts remain excluded, and Windows/signing/notarization remain release gates. See [executed evidence](docs/validation.md#publication-readiness-2026-11-14) and [standalone publication instructions](docs/publishing.md). GitHub publication has not been performed.

Focused test workflow, 2026-11-14 (user request): [one executable catalog](tests/catalog.json) inventories Python, browser, native-renderer and reference-generation checks. The [runner and guide](docs/testing.md) select affected checks from local Git changes, retain per-run reports and identify six legacy browser scripts that still expect removed preview controls. CI uses focused Python suites on pull requests and full Python suites on pushes/manual runs. See [executed checks](docs/validation.md#test-catalog-and-focused-runner-2026-11-14); test selection does not establish scientific or platform validation.

Collapsible image controls, 2026-11-14 (user request): a small arrow at the right of the image header toggles the processing toolbar, inspector and all on-image analysis overlays together, giving the image more space. Mask settings, selections and contrast remain intact; hidden guides cannot be edited, while zoom and pan remain usable. The local preference survives rerenders and reopening; drawing-tool and tab shortcuts reveal the controls. See [workflow](README.md#a-pis-quick-pass) and [executed checks](docs/validation.md#collapsible-processing-ui-2026-11-14).

Canvas fluidity, 2026-11-14 (`origin: human; claim_status: decision` for the performance request): profiled high-frequency hover, pan/zoom, selection/brush drawing and live contrast in native WebKit. Fitted geometry is cached, visual updates are limited to the latest state per animation frame, and canvas/SVG/pixel buffers are retained. Release flushes final endpoints; every accepted scientific brush sample remains recorded. See [implementation](docs/architecture.md#canvas-fluidity) and [measurements and checks](docs/validation.md#canvas-fluidity-2026-11-14).

Canvas interaction, 2026-11-14 (`origin: human; claim_status: decision` for the contrast-selection fix and mouse-interaction request): restored discoverable contrast-region controls and retained outlines through corrections, undo and tool/tab changes; added direct move/resize, safe cancellation, ordered contrast requests, pointer-centered zoom, temporary Space/middle pan, a Pan tool and Fit controls. Explicit fitted dimensions keep the canvas usable in native WebKit and preserve recorded physical aspect. Selections and navigation remain display state. See [workflow](README.md#masks-and-color-limits), [design references](docs/interface-design.md#canvas-interaction-revision-2026-11-14) and [executed checks](docs/validation.md#canvas-interaction-2026-11-14).

Processing performance, 2026-11-13 (`origin: human; claim_status: decision` for the optimization request): removed repeat recipe evaluation between save, display and contrast; added bounded full-resolution result/prefix and thumbnail caches, lossless compact display transport, and direct canvas-buffer rendering. Source-runtime native WebKit checks on a synthetic 512 × 512 scan measured plane correction at 67 ms versus 568 ms before, and undo at 50 ms versus 557 ms. These are local measurements, not latency guarantees. See [architecture](docs/architecture.md#processing-responsiveness) and [executed checks](docs/validation.md#processing-performance-2026-11-13).

Channel ribbon removal, 2026-11-13 (`origin: human; claim_status: decision`): removed the thumbnail ribbon above the detail canvas. The existing header dropdown retains channel and direction switching.

Folder drag-and-drop, 2026-11-13 (`origin: human; claim_status: decision` for the request): the desktop window accepts one session folder anywhere in the interface and uses the existing background importer, progress and cancellation. Drops of individual files or multiple folders show a corrective message. See [workflow](README.md#run) and [executed checks](docs/validation.md#folder-drag-and-drop-2026-11-13).

Folder management and responsive imports, 2026-11-13 (`origin: human; claim_status: decision` for the requested folder controls, freeze fix and rebuild requirement): implemented a Folders library with update, rename/notes, source reconnection and reversible archive/restore. Imports process one file at a time in the background, with progress, cancellation, unchanged-file skipping and preserved earlier versions. See [folder workflow](README.md#manage-session-folders) and [validation](docs/validation.md#folder-management-and-background-imports-2026-11-13). [AGENTS.md](AGENTS.md) now requires rebuilding the desktop app after completed changes.

Characterization workflow, 2026-11-11: the user requested Z-height opening, optional masked row/column alignment, three-point leveling, outline contrast, then rectangle contrast for a terrace or particle, with notification when reference selection fails (`origin: human`; `claim_status: decision`). Implemented automatic unsaved previews for unprocessed height images, three visible reference patches on one inferred plane, a manual three-point fallback, and immediate full-resolution ROI contrast. Masks, originals and saved recipes remain reproducible; previews and their contrast can be discarded. See [methods and selection gates](docs/science.md#automatic-characterization-and-three-point-leveling), [workflow](README.md#a-pis-quick-pass), and [executed checks](docs/validation.md#characterization-workflow-2026-11-11). Automatic plane membership is a proposal and still needs inspection.

Ease-of-use rework, 2026-11-12 (`origin: AI; claim_status: decision`): display-only leveled thumbnails on the contact sheet, a forward/backward header switch, a shorter Prepare tab led by Auto level and 3-point level with advanced corrections grouped, and explicit preview-blocking feedback with K/X keyboard decisions. See [executed checks](docs/validation.md#ease-of-use-rework-2026-11-12).

Direct corrections, 2026-11-12 (`origin: human; claim_status: decision`): the preview Keep/Discard step was removed. Corrections save when applied and are undone with ⌘/Ctrl Z, Record or the confirmation message. See [executed checks](docs/validation.md#direct-corrections-without-preview-2026-11-12).

## Design and Working Instructions

- [Design proposal](design.md#product-and-first-release) — interaction model, scientific pipeline, database, MCP, validation and open choices.
- [Project instructions](AGENTS.md) — implementation scope and scientific constraints.

## Public Project Scope

- The application manages its own samples, acquisitions, analysis recipes and results.
- Documentation, development instructions and tests must work from a fresh repository checkout.
- Examples and test fixtures use synthetic or explicitly redistributable data. The combined application uses [GPL-2.0-or-later](LICENSE), following the user's 2026-11-10 decision to use Gwyddion C as its primary scientific backend. Earlier original code retains its MIT grant.

## Setup State

Application source, local desktop launch and build recipes are in this repository. Experimental files remain private and excluded from bundles. GitHub publication, signed distribution and shared database deployment have not been performed.
