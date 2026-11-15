# Build on the target operating system. No experimental data are bundled.
from pathlib import Path
import sys
import ast
import os

root = Path(SPECPATH)
native = root / 'afm_workbench' / '_native'
native_binaries = [(str(path), 'afm_workbench/_native') for path in sorted(native.iterdir())
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
if sys.platform == 'win32':
    # pywebview ships loaders for three architectures; this candidate is x64.
    def target_runtime(entry):
        name = entry[0].replace('\\', '/')
        return not any('/' + other + '/' in '/' + name
                       for other in ('win-x86', 'win-arm64'))
    a.binaries = [entry for entry in a.binaries if target_runtime(entry)]
    a.datas = [entry for entry in a.datas if target_runtime(entry)]
# Inspect the resolved collection, including optional packages pulled in by hooks.
sys.path.insert(0, str(root / 'scripts'))
from package_notices import collect_notices
from PyInstaller.building.utils import format_binaries_and_datas
notices = collect_notices([*a.pure, *a.binaries, *a.scripts], root,
                          root / 'build' / 'python-notices')
a.datas += [(dest, source, 'DATA') for dest, source in format_binaries_and_datas(notices)]
if os.environ.get('AFM_RUNTIME_NOTICES_DIR'):
    runtime_notices = Path(os.environ['AFM_RUNTIME_NOTICES_DIR'])
    if not (runtime_notices / 'licenses/LICENSE.cpython.txt').is_file():
        raise RuntimeError('Missing portable Python dependency notices.')
    a.datas += [(dest, source, 'DATA') for dest, source in format_binaries_and_datas(
        [(str(runtime_notices), 'licenses/python/runtime-build')])]
pyz = PYZ(a.pure)
if sys.platform == 'win32':
    # One portable executable; the bootloader expands its runtime to user TEMP.
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AFM Workbench',
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=False, disable_windowed_traceback=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AFM Workbench',
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=False, disable_windowed_traceback=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AFM Workbench')
if sys.platform == 'darwin':
    version = next(ast.literal_eval(node.value) for node in ast.parse(
        (root / 'afm_workbench' / '__init__.py').read_text()).body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__'
                                               for t in node.targets))
    app = BUNDLE(coll, name='AFM Workbench.app', bundle_identifier='org.afmworkbench.desktop',
                 version=version,
                 info_plist={'NSHighResolutionCapable': True, 'CFBundleShortVersionString': version,
                             'CFBundleVersion': version,
                             **({'LSMinimumSystemVersion': os.environ['MACOSX_DEPLOYMENT_TARGET']}
                                if os.environ.get('MACOSX_DEPLOYMENT_TARGET') else {})})
