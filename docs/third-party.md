# Dependencies and technical references

The combined application is distributed under GPL-2.0-or-later. Gwyddion's scientific libraries and adapted module routines retain their upstream copyrights and GPL notices. Previously published original Workbench code retains its MIT grant, preserved in [MIT-legacy.txt](../licenses/MIT-legacy.txt); this does not remove the GPL requirements for the combined application.

| Dependency | Purpose | Upstream license / source |
| --- | --- | --- |
| Gwyddion 2.71 | Native scientific processing and analysis | [GPL-2.0-or-later](https://gwyddion.net/documentation/user-guide-en/licensing.html) |
| FFTW 3.3.10 | Gwyddion scientific-library dependency | [GPL](https://www.fftw.org/faq/section1.html#isfftwfree) |
| GLib/GObject/GThread | Gwyddion object/runtime dependency | [LGPL-2.1-or-later](https://gitlab.gnome.org/GNOME/glib) |
| NumPy | Arrays and numerical linear algebra | [BSD-3-Clause](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| Pillow | Thumbnail rendering | [MIT-CMU / HPND](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| pywebview | Native desktop web view | [BSD-3-Clause](https://github.com/r0x0r/pywebview/blob/master/LICENSE) |
| PyInstaller | Build-time application bundling | [GPL with bootloader exception](https://pyinstaller.org/en/stable/license.html) |
| PyObjC (macOS) | Native framework bridge, via pywebview | [MIT](https://github.com/ronaldoussoren/pyobjc/blob/main/LICENSE.txt) |
| Bottle / proxy_tools | pywebview dependencies | [Bottle MIT](https://github.com/bottlepy/bottle/blob/master/LICENSE), [proxy_tools BSD](https://github.com/jtushman/proxy_tools) |

Use the upstream distributions' notices for the exact transitive dependency set installed on each target. No third-party font, icon set, hosted image, cloud service or web CDN is required; icons are original inline SVG and fonts are system fonts.

The [Mac release recipe](publishing.md#reproducible-apple-silicon-mac-candidate)
uses a checksum-pinned [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
CPython archive. Its matching full build archive supplies `PYTHON.json` and the
original dependency licenses (including OpenSSL, SQLite, compression and other
runtime components), bundled under `licenses/python/runtime-build/`. The exact
distribution URLs/hashes are recorded in the release configuration and bundle.

Desktop packaging collects original license/notice files for the Python distributions represented in PyInstaller's resolved module and binary collection, including optional dependencies pulled in by its hooks, plus the Python runtime notice and the earlier Workbench MIT grant. The resulting `licenses/python/manifest.json` records installed versions and notice checksums without local paths. A missing notice stops packaging. [Version-specific upstream copies](../licenses/python-fallbacks/manifest.json) cover releases whose wheels omit their notices; their upstream archive/file URLs and checksums are recorded. In particular, proxy_tools 0.1.0's package metadata says MIT, while its source header and upstream license say BSD; the original BSD notice is preserved. This inventory is packaging evidence, not a claim of legal clearance for every future dependency or platform build.

The executed native Mac build also contains libffi, PCRE2, gettext/libintl and libiconv. Its [pinned dependency manifest](../native/dependencies-macos-arm64.json) and [source collector](../scripts/collect_native_sources.py) preserve original notices, exact source archives, recipes and patches. The local `afm_workbench/_native/licenses` and `sources` outputs accompany packaged binaries. Use the manifests for the binaries actually distributed; the Mac manifest is not a substitute for different Homebrew or Windows dependencies.

Primary technical references:

- [Gwyddion supported formats](https://gwyddion.net/documentation/user-guide-en/file-formats.html)
- [Gwyddion leveling and background](https://gwyddion.net/documentation/user-guide-en/leveling-and-background.html)
- [Gwyddion statistical analysis](https://gwyddion.net/documentation/user-guide-en/statistical-analysis.html)
- [pywebview API](https://pywebview.flowrl.com/api/)
- [pywebview architecture](https://pywebview.flowrl.com/guide/architecture.html)
- [SQLite deployment guidance](https://sqlite.org/whentouse.html)

Importer-specific byte layout and calibration references are recorded in [formats](formats.md). Redistribution rights have not been established for the local experimental TIFFs; those files are ignored and not packaged.

## Gwyddion numerical reference

The [Gwyddion 2.71 source release](https://gwyddion.net/download.php) is GPL-2.0-or-later. The optional `scripts/check_gwyddion.py` validation harness reads a separately supplied release, compiles selected unchanged routines into a temporary library, and records synthetic numerical outputs. This test harness is separate from the production bridge, which uses real Gwyddion objects and libraries. The committed JSON fixtures are generated synthetic numerical results, with source-file hashes and the archive checksum recorded. See the [compatibility audit](gwyddion-compatibility.md).
