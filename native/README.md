# Native Gwyddion scientific backend

The desktop service calls a small C ABI adapter linked to the **real Gwyddion 2.71 scientific libraries**. The build compiles every upstream source file listed in `libgwyddion/Makefile.am` and `libprocess/Makefile.am`. It does not use the testing harness's substitute object definitions.

The build uses GLib/GObject/GThread and FFTW3. GTK and the Gwyddion application are not linked. OpenMP and native-language translation are disabled. A generated feature configuration probes the compiler's math-library support; upstream fallback implementations handle unavailable functions. Upstream source files are not modified. Three non-public Align Rows implementations are extracted unchanged from `modules/process/linematch.c`, with its copyright/license header, and compiled against actual Gwyddion objects.

The combined distribution uses GPL-2.0-or-later. Preserve upstream and dependency notices. Build manifests record source-file hashes, compiler, architecture, generated configuration, native binary hashes and source-archive pins.

## Development build

Install this repository's Python dependencies first. A C99 compiler, GLib development headers/libraries, FFTW3 development headers/libraries and `pkg-config` are needed. No system-wide Gwyddion installation is required.

On macOS, one dependency route is Homebrew:

```sh
brew install glib fftw pkg-config
python scripts/build_gwyddion.py --download
python scripts/test.py --group native --kind unit
```

Alternatively, supply dependency prefixes explicitly:

```sh
python scripts/build_gwyddion.py --download \
  --glib-prefix /path/to/glib-prefix \
  --fftw-prefix /path/to/fftw-prefix
```

A prefix must provide headers and linkable libraries. If GLib's generated `glibconfig.h` is outside its usual `lib/glib-2.0/include`, add `--glib-config-dir /path/to/config-directory`. Use a generated header from the same GLib build and target architecture.

To build the pinned FFTW release locally instead of requiring its development package:

```sh
python scripts/build_gwyddion.py --download --build-fftw
```

`--build-fftw` requires a POSIX shell and `make`. It installs FFTW only below the selected build directory. `--download` downloads only missing archives and checks their pinned SHA-256 hashes. Without it, put the archives named below in `.test-artifacts/native/sources` before building. `--source /path/to/gwyddion-2.71` permits an existing source tree; its version and source-file hashes are recorded.

On Debian/Ubuntu, the development dependency setup is:

```sh
sudo apt-get install build-essential pkg-config libglib2.0-dev libfftw3-dev
python scripts/build_gwyddion.py --download
python scripts/test.py --group native --kind unit
```

The Linux command is a development/CI recipe; a standalone Linux dependency bundle has not been validated here. Standard system GLib dependencies remain supplied by the host on Linux.

On Windows, use a consistent MinGW-w64 toolchain and matching GLib/FFTW development packages. MSVC and MinGW objects must not be mixed. The script has a DLL build path, but dependency-DLL staging and the Windows application have **not been executed or validated**. Windows packaging should remain a manual gate until a fresh Windows build passes native numerical and desktop checks. Python's existing interpreter does not need to be built with MinGW: the bridge exposes an ordinary C ABI and owns no Python objects.

## Outputs and loading

The default build directory is `.test-artifacts/native`; `--build-dir` changes it. The default output is `afm_workbench/_native`; `--output` changes it. Generated binaries are local build artifacts, not source files to commit.

macOS output contains `libafm_gwyddion.dylib`, `libgwyddion2.dylib`, `libgwyprocess2.dylib` and their non-system dylib dependency closure. Every dependency reference is relocated to `@loader_path`; copied libraries are ad-hoc signed for local execution. This is not Developer ID signing or notarization. Linux uses `libafm_gwyddion.so` and local `$ORIGIN` references for the Gwyddion libraries. Windows targets `afm_gwyddion.dll`.

Run `--libraries-only` to build the upstream libraries before compiling the adapter. The Python service's native backend must load the bridge from its configured/application path; failure to load is an actionable error, not an unrecorded numerical fallback.

## Source bundles and notices

`--source-bundle DIRECTORY` chooses the corresponding-source destination; the default is `OUTPUT/sources`. Source archives present in the verified build cache are copied there alongside the adapter/build source and generated native build manifest. The original Gwyddion and FFTW licenses are copied into `OUTPUT/licenses`. These directories must accompany a binary distribution, together with the full Workbench source and its license.

Pinned scientific sources:

| Source | Archive SHA-256 |
| --- | --- |
| [Gwyddion 2.71](https://downloads.sourceforge.net/project/gwyddion/gwyddion/2.71/gwyddion-2.71.tar.xz) | `2df721befccbe4d5ee2ba564b32e69341f8ce1de637e2045838a09a2d46b5dba` |
| [FFTW 3.3.10](https://www.fftw.org/fftw-3.3.10.tar.gz) | `56c932549852cddcfafdab3820b0200c7742675be92179e59e6215b340e26467` |

The executed development build used the exact Mac arm64 packages in [dependencies-macos-arm64.json](dependencies-macos-arm64.json). This manifest also records their upstream source archives. To collect their corresponding sources, original package recipes and patches, and original license notices:

```sh
python scripts/collect_native_sources.py \
  --manifest native/dependencies-macos-arm64.json --download
```

This requires `zstd`; use `--zstd /path/to/zstd` if needed. The collector extracts metadata only and never runs downloaded recipe scripts. Every package and source archive is checksum-verified. It includes GLib, gettext/libintl, libiconv, libffi, PCRE2 and the exact SLJIT source revision used by that PCRE2 package.

The same collection can run as part of the build:

```sh
python scripts/build_gwyddion.py --download --build-fftw \
  --dependency-manifest native/dependencies-macos-arm64.json
```

Only use that manifest with the dependency packages it names. For a Homebrew, Linux or different Windows distribution, collect the corresponding source, patches, build recipes and notices for the dependency binaries actually distributed. Do not label those different binaries with the Mac development manifest. The application packaging script checks for the source bundle; creating binaries alone is not a public-release claim.

## Executed evidence

On the development Mac arm64, the library-only build compiled 26 `libgwyddion` and 48 `libprocess` C files, linked the adapter and loaded it through `ctypes`; the actual upstream version query returned `2.71`. The resulting dependency closure contains no GTK library. The project native tests compare processing, statistics and profiles against recorded upstream outputs and synthetic ground truth. See [validation](../docs/validation.md) for test-run results and platform limitations.
