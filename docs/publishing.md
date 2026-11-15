# Publishing

## Source repository

Publish only the Workbench source tree. If it lives inside a larger repository,
export this subtree into a new directory and initialize a separate Git repository
there. Pushing the enclosing repository can expose unrelated files and history.
Check `git rev-parse --show-toplevel` before configuring a public remote.

For an existing standalone checkout, a source snapshot can be created with:

```sh
git archive --format=tar.gz --prefix=AFM-Workbench/ \
  --output=AFM-Workbench-github.tar.gz HEAD
```

For a project nested in another repository, run the archive command from the
enclosing repository's root and select the project tree explicitly instead of
`HEAD`, for example `HEAD:relative/path/to/afm-workbench`. Running that tree
selection from the nested directory can produce an empty archive. Run this after
committing the reviewed changes. Git archives include tracked source only and
do not include Git history. Inspect the archive before publishing it.

The new repository root should contain `README.md`, `LICENSE`, `pyproject.toml`,
`afm_workbench/`, `native/`, `scripts/`, `tests/` and `.github/workflows/check.yml`.
Keep `.gitignore`; do not add experimental TIFFs, local catalogs, environments,
test artifacts or generated native binaries. The committed reference fixture
contains generated synthetic results.

From the exported checkout, follow [installation](../README.md#run-from-source), audit the
[test catalog](testing.md), build the native backend, and run the full checks.
CI runs the Python checks on Mac and Linux; browser and desktop checks require
their separately documented dependencies. Preserve failed, skipped and legacy
results in the release record. Source publication does not establish scientific
validation or support on an untested platform.

## Reproducible Apple Silicon Mac candidate

Use the [release recipe](../scripts/release_macos.py) on a native arm64 Mac with
Python 3.12+ for bootstrapping and Apple's Command Line Tools (`cc`, `make`,
`xcrun`, `install_name_tool`, `codesign`). No Homebrew GLib/FFTW, Conda install,
signing credentials or existing native build is needed. The recipe downloads
the [checksum-pinned portable CPython 3.12.16 distribution](../release/macos-arm64.json)
into the checkout; it does not replace system Python.

Stage new source files, then build a local candidate:

```sh
python3 scripts/release_macos.py
```

This produces a `vX.Y.Z-snapshot` and records whether the checkout is dirty.
To reproduce a committed candidate, use a clean checkout of its existing tag:

```sh
git checkout v0.1.0
python3 scripts/release_macos.py --tag v0.1.0
```

Substitute the intended tag. Tagged builds require `vX.Y.Z` to match both
`pyproject.toml` and `afm_workbench/__init__.py`, point at `HEAD`, and have no
tracked or untracked source changes. The bundle uses that application version.
Each invocation recreates its interpreter, virtual environment, native build and
dependency prefix. Download caches live under `.test-artifacts/release-macos/`;
`--offline` reuses them while still verifying hashes and rebuilding. Missing
cached inputs fail the offline build.

The Python [bootstrap](../release/macos-bootstrap.lock) and
[application](../release/macos-arm64.lock) locks pin exact archive hashes,
including PyInstaller hooks. The sole sdist, `proxy_tools`, builds with locked
setuptools/wheel and no isolated dependency resolution. The native manifest
supplies exact GLib/dependency binaries and development headers; Gwyddion and
FFTW compile from verified sources. Matching recipes, patches, sources and
notices accompany the app. Portable Python's complete build metadata and
dependency notices are verified and bundled too.
Native builds use Apple's clang and explicit baseline arm64 flags, including
FFTW, whose configure defaults otherwise tune for the build machine's CPU.

The recipe invokes `scripts/build.py`, runs **all active Python checks**, tests
the rebuilt executable with `runtime`, verifies the ad-hoc signature, and
inspects Mach-O binaries for arm64, deployment floor and absolute non-system
library references. Tagged builds fail if the actual floor exceeds macOS 14.
Inspection does not establish clean-Mac compatibility. GUI/browser acceptance
remains deferred; six legacy browser scripts remain excluded. Failed attempts
do not leave an older `dist/release/` looking like a successful candidate.

Successful outputs under `dist/release/` are:

- `AFM-Workbench-vX.Y.Z-macos-arm64.tar.gz`: the complete `.app`, preserving executable modes and symlinks.
- `AFM-Workbench-vX.Y.Z-source.tar.gz`: matching Workbench and native corresponding sources. GitHub's automatic source archives do **not** replace this asset.
- `build-manifest.json`: commit/dirty flag, input hashes, exact Python distribution/packages, compiler/SDK/runner image, asset hashes and executed/deferred checks.
- `SHA256SUMS` and `release-notes.md`: download verification and candidate limitations.

Verify with `shasum -a 256 -c SHA256SUMS` in the downloaded asset directory.
Archives normalize path order, owners, modes and timestamps; gzip headers omit
the output filename. Builds fix `PYTHONHASHSEED` and use the commit timestamp as
`SOURCE_DATE_EPOCH`, following [PyInstaller's guidance](https://pyinstaller.org/en/stable/advanced-topics.html#creating-a-reproducible-build).
This is a pinned, replayable recipe with deterministic archive serialization.
Byte-identical binaries **across different hosts** are not promised: compiler,
SDK, linker, build paths and hosted-runner image updates can affect output.
Toolchain values are recorded for comparison. Lock updates require fresh full
regression/build checks, a notice audit and a packaged smoke.

## Tag-triggered GitHub release

[The workflow](../.github/workflows/release.yml) runs on pushed `v*` tags and can
be manually dispatched for artifact-only testing. It uses an explicit
`macos-15` arm64 runner and commit-pinned actions. GitHub supplies Python 3.12.10
only as the bootstrap; the recipe provisions the pinned CPython 3.12.16 runtime.
This avoids depending on a macOS interpreter missing from setup-python's
catalog. See [GitHub's runner documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).

After reviewing and committing a version change, a maintainer can trigger it:

```sh
git tag -a v0.1.0 -m "AFM Workbench 0.1.0"
git push origin v0.1.0
```

The build job has read-only repository permission. Only a successful tag build
enables a separate job with `contents: write`; it verifies asset checksums and
creates a **draft** release with the app, corresponding sources, manifest and
checksums. It uses [`gh release create --verify-tag --draft`](https://cli.github.com/manual/gh_release_create)
and `GITHUB_TOKEN`; no personal token is required. It never creates a missing
tag or replaces an existing release's assets. Inspect/delete an incomplete
draft before rerunning a failed upload; never move a released tag. Manual runs
upload Actions artifacts without creating releases. Test reports are retained
even if checks fail.

Keep the candidate as a draft until full [acceptance checks](testing.md) against
its executable, packaged desktop startup, clean-Mac installation, Developer ID
signing and notarization are complete. The workflow does not publish an unsigned
candidate as a finished release or provide Intel Mac/universal2/Windows binaries.
Adding the workflow does not imply that a tag was pushed or a GitHub run executed.

## Authorized experimental prerelease

On 2026-11-14 the user explicitly requested publication of the binary. Version
0.1.0 may therefore be published as an **experimental prerelease** before
Developer ID signing, notarization and clean-Mac installation acceptance.
Run all active checks against the rebuilt executable and record the remaining
limitations prominently in the public notes. Keep the default tag workflow's
draft behavior; publication of this candidate is a deliberate maintainer action.
This exception does not certify a stable release, Intel Mac or Windows support.

## Windows x64 candidate

Use CPython 3.12 x64 on Windows with Git. Create a virtual environment, then
install the exact build prerequisites and application dependencies:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r release/windows-bootstrap.lock
.venv\Scripts\python.exe -m pip install --require-hashes --no-build-isolation -r release/windows-x64.lock
.venv\Scripts\python.exe scripts/release_windows.py
```

Stage new source files before building. The recipe extracts verified MSYS2
UCRT64 packages into `.test-artifacts/windows/toolchain`, compiles FFTW 3.3.10
and Gwyddion 2.71, collects the DLL dependency closure and matching sources and
notices, packages the windowed application, then runs every Python suite and
the packaged runtime smoke. It does not install MSYS2 or modify system Python.
The host CPython distribution is recorded, rather than provisioned by the recipe;
compiler/Python/build-path differences can affect binary bytes.

Outputs are under `dist/release-windows/`: a portable application ZIP, matching
Windows corresponding-source archive, `build-manifest.json`, `SHA256SUMS` and
`release-notes.md`. Extract the whole ZIP and keep `_internal` beside the EXE.
The target is Windows 10/11 x64 with WebView2 Runtime and .NET Framework 4.8.
No Python, compiler, GLib or FFTW installation is needed by the end user.

`--offline` reuses verified native download caches. The already-installed Python
environment must match the locks. `--acceptance` runs all active checks against
the rebuilt executable, including browser and native renderer workflows, and
needs Playwright and an interactive desktop. `--browser PATH` selects Chromium;
`AFM_PLAYWRIGHT_MODULE` can select an existing Playwright installation. A native
renderer smoke uses development pywebview; separately open the packaged EXE to
verify its desktop startup. Six legacy browser checks remain inactive.

The [Windows workflow](../.github/workflows/release-windows.yml) runs manually for
artifact-only builds or on `windows-vX.Y.Z` tags. A tagged build requires the tag
to match the application version, point at HEAD and have a clean checkout. The
separate Windows tag namespace does not trigger or replace the Mac release.
Only successful tagged builds create an experimental **draft** release; existing
assets are never overwritten. Unsigned candidates remain drafts pending clean
machine installation, physical File Explorer drop testing and signing. Creating
the workflow is not evidence that GitHub Actions ran it.

## Other desktop/development builds

Build on the target OS and collect the sources and notices for the exact native
dependencies distributed, following the [native instructions](../native/README.md).
Stage new source files before running `python scripts/build.py`. Distribute the
matching `dist/AFM-Workbench-source.tar.gz` with the application. This archive
includes the native corresponding-source collection and is different from the
small GitHub source snapshot above.

Run the full [release checks](testing.md) against the rebuilt executable and
check the archive contents, bundled notices and signatures. The local Mac build
uses an ad-hoc signature; Developer ID signing, notarization and installation on
a clean Mac remain release gates. Windows candidates remain unsigned until
Authenticode signing is available. See [validation status](validation.md) for the evidence actually
recorded, including current browser coverage gaps.
