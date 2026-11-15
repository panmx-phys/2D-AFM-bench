# Build on the target operating system. No experimental data are bundled.
from pathlib import Path
import sys

root = Path(SPECPATH)
native = root / 'afm_workbench' / '_native'
native_binaries = [(str(path), 'afm_workbench/_native') for path in native.iterdir()
                   if path.suffix in {'.dylib', '.so', '.dll'}]
if not any('afm_gwyddion' in path for path, _ in native_binaries):
    raise RuntimeError('Build the native Gwyddion backend before packaging; see native/README.md.')
a = Analysis(
    [str(root / 'scripts' / 'desktop_entry.py')],
    pathex=[str(root)],
    binaries=native_binaries,
    datas=[(str(root / 'afm_workbench' / 'static'), 'afm_workbench/static'),
           (str(native / 'build-manifest.json'), 'afm_workbench/_native'),
           (str(native / 'licenses'), 'afm_workbench/_native/licenses'),
           (str(root / 'LICENSE'), '.'),
           (str(root / 'licenses' / 'MIT-legacy.txt'), 'licenses'),
           (str(root / 'docs' / 'third-party.md'), 'licenses')],
    hiddenimports=['webview'],
    hookspath=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'scipy', 'pandas', 'torch', 'tensorflow', 'IPython', 'pytest'],
    noarchive=False,
)
# Inspect the resolved collection, including optional packages pulled in by hooks.
sys.path.insert(0, str(root / 'scripts'))
from package_notices import collect_notices
from PyInstaller.building.utils import format_binaries_and_datas
notices = collect_notices([*a.pure, *a.binaries, *a.scripts], root,
                          root / 'build' / 'python-notices')
a.datas += [(dest, source, 'DATA') for dest, source in format_binaries_and_datas(notices)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AFM Workbench',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AFM Workbench')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='AFM Workbench.app', bundle_identifier='org.afmworkbench.desktop',
                 info_plist={'NSHighResolutionCapable': True, 'CFBundleShortVersionString': '0.1.0'})
