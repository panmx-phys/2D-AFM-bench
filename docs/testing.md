# Test catalog and focused checks

Run from the checkout root with its virtual environment activated. All commands use the standard-library `unittest` runner; pytest is not required. Build the [native backend](../native/README.md) for scientific/service checks. Use `.venv/bin/python` on macOS or `.venv\Scripts\python.exe` on Windows when the environment is not activated.

## Daily workflow

```sh
python scripts/test.py --plan
python scripts/test.py
```

The default compares this project with `HEAD`, including staged, unstaged and untracked files. It works when the checkout is a subdirectory of a larger Git repository, and ignores changes elsewhere. After committing, use `--base HEAD~1` to check the last commit, or supply a branch/base revision to check a larger change. The comparison is directly against that revision, not an implicit merge base. No changes means no tests executed, not a test pass.

Python impact selection follows local imports transitively, including function-local imports and shared fixtures imported from other test modules. UI workflows have explicit path mappings in [tests/catalog.json](../tests/catalog.json). Unknown implementation/configuration paths conservatively select every active check. New or removed check files cause a catalog-audit error until registered or removed from the catalog. Documentation-only edits require no regression suite; the project still requires rebuilding completed changes and checking the bundle.

Selection is a conservative dependency estimate, not proof of complete coverage. Dynamic imports, contracts between languages and novel workflows need human review of the printed plan. Shared scientific code may affect many tests. Use `--full` for releases, broad dependencies/schema changes or uncertain scope; CI runs all Python checks on pushes and manual dispatches as a backstop.

```sh
python scripts/test.py --group display --plan
python scripts/test.py --check masks-display --check canvas
python scripts/test.py --changed --kind unit
python scripts/test.py --full --kind unit
python scripts/test.py --full
```

`--check` accepts catalog IDs, `--group` accepts the groups below, and both can be repeated; overlapping selections run once. `--kind` can also be repeated. A kind filter prints affected checks it leaves **deferred**, so a focused Python pass does not imply that the UI was tested. `--full` includes every active runtime/browser/desktop check and requires their dependencies. `--list` audits and prints all individual files, purposes, statuses and group memberships.

## Catalog

The JSON catalog is the executable inventory. Existing assertions stay in their original files; the runner consolidates selection, setup and reporting. A group is a convenient explicit selection, not a claim that it covers all dependencies of a change. Default impact selection may choose checks from several groups.

| Group | Active check IDs | Coverage |
| --- | --- | --- |
| `import` | `importers` | Park format, calibration, dimensions, units, orientation, validity and malformed files |
| `science` | `science`, `terraces`, `auto-processing`, `characterization` | Numerical truth, preserved features, references, fit rejection and reproducibility |
| `native` | `line-alignment`, `native-backend`, `gwyddion-processing`, `gwyddion-analysis` | Actual Gwyddion C, pinned fixtures, axes, masks, analysis definitions and service parity |
| `service` | `service`, `runtime` | Catalog/import lifecycle, HTTP/MCP, exports, provenance and executable health |
| `display` | `masks-display`, `canvas` | Mask snapshots, contrast invariance, selection/editing, navigation and layout |
| `performance` | `performance`, `fluidity`, `processing-latency` | Cache correctness, transport, per-frame work and local latency measurements |
| `folders` | `desktop-drop`, `folders-ui`, `folder-drop-ui` | Folder lifecycle, reconnect/archive, native path bridge and invalid drops |
| `map` | `map-ui` | Overlapping/rotated footprints, selection, filters and compact layout |
| `tooling` | `test-runner`, `packaging` | Inventory drift, impact rules, Git scope, result accounting, archive privacy and dependency notices |

`runtime` needs only Python's standard library on the client side and exercises the running app's bundled scientific engine. Browser checks need Node, Playwright and Chromium. Install them separately when needed (`npm install --no-save --package-lock=false playwright`, then `npx playwright install chromium`); keep `node_modules/` out of source control. `AFM_PLAYWRIGHT_MODULE` can point to an existing Playwright installation, `--node` selects Node, and `--browser` selects a Chromium executable. The runner supplies `AFM_PYTHON` for synthetic fixture generation.

Desktop checks need `python -m pip install '.[desktop]'` and an interactive desktop session. They use the host's pywebview renderer and synthetic events; they do not verify physical mouse/trackpad input or actual Finder/File Explorer drops. `fluidity` always enables `--expect-coalesced`; `processing-latency` always enables `--expect-compact`. Timing values describe the local run, with no hardware-dependent latency pass threshold.

## Rebuilt application checks

Stage newly added source files before building so the corresponding-source archive includes them. Rebuild after completed changes, then select the relevant workflow against the new executable:

```sh
python scripts/build.py
python scripts/test.py --check canvas --bundle "dist/AFM Workbench.app/Contents/MacOS/AFM Workbench"
```

On Windows, the expected executable path is `dist/AFM Workbench/AFM Workbench.exe`; Windows native build and packaging remain unvalidated. `--bundle` must name the executable, not an `.app` directory. It adds `runtime` automatically, unless a `--kind` filter explicitly defers it. Unit tests always run against source; the report records that distinction. The runner does not rebuild or establish bundle freshness itself.

Each smoke starts a separate server with a fresh temporary catalog, synthetic demo and OS-assigned loopback port, then stops the process and removes the catalog. There is no URL option on the runner, so it never targets an existing lab catalog. Server logs are retained. Individual scripts still accept a URL for manual diagnosis; use a disposable catalog. Native smoke windows are driven by development pywebview even when their HTTP service/assets come from the bundle; this is not a test of the packaged desktop window startup.

## Results and historical checks

Every execution produces `.test-artifacts/runs/<UTC timestamp>/report.json` and per-check logs. The report records Git revision, changed paths, selection reasons, source versus bundle target, environment, duration, failures, skips and deferred/inactive checks. Missing dependencies, failures and timeouts return nonzero. Python skips produce an **incomplete** result and nonzero exit, not a pass. No prior result is used to skip a newly selected check. Reports and screenshots remain local and excluded from source releases.

Six existing browser scripts have a **legacy** status: `ui-smoke.cjs`, `processing-smoke.cjs`, `gwyddion-smoke.cjs`, `masking-display-smoke.cjs`, `inspector-smoke.cjs` and `characterization-smoke.cjs`. Source inspection on 2026-11-14 found assertions for the removed Keep/Discard preview controls. They are retained for migration and listed in affected/full plans, but do not count as active passing checks. Explicitly requesting a legacy ID fails with its catalog explanation. Historical passes in [validation.md](validation.md) describe earlier application states.

Current Python, canvas and performance checks cover many of their scientific and interaction assertions. Remaining browser coverage gaps include the complete contact-sheet/channel/comparison/export path, all inspector keyboard/disclosure behaviors and the full native-method control matrix. The legacy scripts are not claimed to have been replaced completely. Migrate their assertions to current direct-save/undo behavior before reactivating them; do not delete unrelated assertions just to obtain a pass.

`reference-fixtures` is **maintenance**, not a regression check. It compiles selected upstream Gwyddion routines to generate candidate reference JSON. Its explicit command and prerequisites are in the catalog. Generate to a temporary file, inspect the differences and provenance, and deliberately update the committed fixture; routine tests consume the existing fixture without rewriting it. Ad hoc scripts and screenshots under ignored `.test-artifacts/` and private `tests/data/local/` are historical evidence, not the reproducible suite. Third-party dependency tests under `_native/` are not Workbench-owned tests.

## Maintaining the catalog and CI

Add a check entry with a unique ID/path, kind, group, purpose and status. Python imports supply most dependency edges; `dependency_inputs` connects native source/build inputs to their Python wrapper and its consumers. Use `affects` glob patterns for fixtures and cross-language/UI dependencies. Every file matching `tests/test_*.py`, `scripts/*-smoke.py`, `scripts/*-smoke.cjs` or `scripts/check_*.py` must appear exactly once. Run `--check test-runner` and inspect representative plans after changing mappings. Keep coverage limitations explicit.

[CI](../.github/workflows/check.yml) fetches history, builds the native backend on Mac/Linux and runs affected Python suites on pull requests using the PR base SHA. Pushes and manual runs execute all Python suites. Reports are uploaded even on failure. Browser/native GUI and packaged smoke checks are local checks; a successful Python CI job does not certify them or Windows compatibility.
