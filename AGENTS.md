# AFM Workbench Project Instructions

Start at `index.md`, then read the relevant parts of `design.md`.

The user authorized implementation and independent product decisions on 2026-11-09. Build an intuitive product for a busy PI browsing and analyzing data. The confirmed platform target is Mac and Windows desktop, with a shared database later. The software is intended for a standalone public GitHub repository.

One imported folder is one AFM session. Present all images in that folder together; acquisition numbers, channels and forward/backward direction are subdivisions within the session, never separate sessions. Sample assignment is optional. Prioritize fast visual browsing, clear provenance and reversible analysis.

Use a compact, neutral utility interface. Avoid promotional copy, decorative dashboard summaries, bright accent colors and unnecessary motion. Z height is the primary AFM view: default to one forward Z-height image per acquisition, with its corresponding error signal and other channels alongside. Match signals by acquisition, recorded footprint and direction. Keep other channels, backward scans and provenance accessible; label missing-height fallbacks explicitly.

Implementation uses a Python scientific core, SQLite catalog, a local HTML/CSS/JavaScript interface, and a pywebview desktop shell. A loopback-only browser mode supports development. Keep front-end assets local and the application usable offline. Do not claim packaging or scientific validation on platforms that have not been tested.

Keep the repository self-contained. Use portable relative links and configurable data locations. Documentation, tests and build instructions must work from a fresh checkout. Include only synthetic or explicitly redistributable example data and source code with compatible licensing.

Keep original AFM files immutable. Record calibration, units, channel, orientation, trace/retrace, masks, reference surfaces and processing history explicitly. Distinguish display contrast from numerical transformations. GUI and MCP operations must use the same scientific implementation.

The application's database owns sample identifiers and optional sample metadata, AFM acquisitions, analysis recipes, measurements and exports. Scans may be analyzed without assigning a sample. Any future external integrations must be optional adapters.

Retain evidence origin and claim status for research claims. AI suggestions and fit/model interpretations are proposals or inferences until qualified; fit agreement alone does not establish a physical mechanism. Cite public technical sources and keep algorithm, parameter, calibration and data provenance reproducible.

Validate importers and numerical operations using synthetic ground truth and redistributable reference fixtures. Do not treat comments claiming past validation as a completed validation run for this application.

Use [the test catalog and focused workflow](docs/testing.md). Start with `.venv/bin/python scripts/test.py --plan`, then run the affected checks; do not rerun the entire suite for every change. The runner audits `tests/catalog.json`, follows local Python dependencies and maps UI workflows. Register new checks there. Report deferred, legacy, skipped and failed checks accurately; a prior pass is not evidence for changed code. Use full checks for releases or broad changes. CI runs affected Python suites on pull requests and all Python suites on pushes/manual runs.

After every completed change, rebuild/recompile the desktop application with `.venv/bin/python scripts/build.py` (or the equivalent virtual-environment Python on Windows), run the relevant checks against the rebuilt output, and report the build result. Do not leave the user testing an older bundle. Stage new source files before building so the corresponding-source archive includes them.
