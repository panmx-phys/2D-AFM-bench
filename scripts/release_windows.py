"""Build/test an unsigned Windows x64 candidate with pinned native/Python inputs.

Use CPython 3.12 x64 and the hash-locked release/windows-x64.lock in a venv.
No system compiler, MSYS2 installation, or system GLib/FFTW is required.
This script does not create tags, upload assets, or publish releases.
"""
from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

try:
    from .build_gwyddion import SOURCES
    from .collect_native_sources import acquire, decompress_zstd
    from .release_macos import version, sha256, summarize_report
except ImportError:
    from build_gwyddion import SOURCES
    from collect_native_sources import acquire, decompress_zstd
    from release_macos import version, sha256, summarize_report

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'.test-artifacts/windows'
TOOLCHAIN = ROOT/'release/windows-x64-toolchain.json'
NATIVE = ROOT/'native/dependencies-windows-x64.json'
LOCK = ROOT/'release/windows-x64.lock'
APP = ROOT/'dist/AFM Workbench'
BUNDLE = APP/'AFM Workbench.exe'


def output(*args):
    return subprocess.check_output([str(a) for a in args], cwd=ROOT, text=True).strip()


def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def remove_generated(path):
    """Restrict recursive cleanup to known generated directories in this checkout."""
    path = path.resolve()
    allowed = [WORK.resolve(), (ROOT/'dist').resolve(), (ROOT/'afm_workbench/_native').resolve()]
    if not any(path == root or root in path.parents for root in allowed) or path == WORK.resolve():
        raise RuntimeError(f'Refusing cleanup outside generated directories: {path}')
    if path.exists():
        shutil.rmtree(path)


def native_build(offline=False):
    cache = WORK/'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    prefix = WORK/'toolchain'
    remove_generated(prefix)
    prefix.mkdir()
    for spec in json.loads(TOOLCHAIN.read_text())['packages']:
        archive = acquire(spec, cache, not offline)
        payload = WORK/'payload.tar'
        decompress_zstd(archive, payload)
        with tarfile.open(payload) as tar:
            # Package hooks/scripts and unrelated roots are never installed or executed.
            members = [m for m in tar if m.name.startswith('ucrt64/')]
            tar.extractall(prefix, members=members, filter='data')
        payload.unlink()
    compiler = prefix/'ucrt64/bin/gcc.exe'
    os.environ['PATH'] = os.pathsep.join([str(compiler.parent), str(Path(sys.executable).parent), os.environ['PATH']])
    build = WORK/'native-build'
    remove_generated(build)
    (build/'sources').mkdir(parents=True)
    for spec in SOURCES.values():
        source = acquire(spec, cache, not offline)
        shutil.copy2(source, build/'sources'/source.name)
    remove_generated(ROOT/'afm_workbench/_native')
    run(sys.executable, 'scripts/build_gwyddion.py', '--build-fftw',
        '--build-dir', build,
        '--glib-prefix', prefix/'ucrt64', '--cc', compiler,
        '--objdump', compiler.with_name('objdump.exe'),
        '--dependency-manifest', NATIVE, '--dependency-cache', cache,
        *([] if offline else ['--download']))
    return output(compiler, '--version').splitlines()[0]


def deterministic_zip(destination, folder, epoch):
    stamp = time.gmtime(max(315532800, epoch))[:6]
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(folder.rglob('*')):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise RuntimeError('Windows ZIP must not depend on symlink privileges.')
            info = zipfile.ZipInfo(folder.name+'/'+path.relative_to(folder).as_posix(), stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def inspect_bundle(folder):
    """Check native PE architecture and dependency closure without host PATH."""
    import pefile
    system = Path(os.environ['SystemRoot'])/'System32'
    binaries = [p for p in folder.rglob('*') if p.suffix.lower() in {'.exe', '.dll', '.pyd'}]
    names = {p.name.casefold() for p in binaries}
    native = folder/'_internal/afm_workbench/_native'
    records = {}
    for path in binaries:
        pe = pefile.PE(str(path), fast_load=True)
        try:
            # .NET AnyCPU assemblies can have an I386 header; native code must be x64.
            managed = bool(pe.OPTIONAL_HEADER.DATA_DIRECTORY[14].VirtualAddress)
            if not managed and pe.FILE_HEADER.Machine != 0x8664:
                raise RuntimeError(f'Non-x64 native binary: {path.name}')
            pe.parse_data_directories(directories=[1, 13])
            dependencies = [entry.dll.decode() for attr in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT')
                            for entry in getattr(pe, attr, [])]
            if path.parent == native:
                for name in dependencies:
                    if name.casefold() not in names and not name.lower().startswith(('api-ms-win-', 'ext-ms-win-')) and not (system/name).is_file():
                        raise RuntimeError(f'Unresolved native dependency {name} in {path.name}')
                records[path.name] = dependencies
        finally:
            pe.close()
    if not (native/'afm_gwyddion.dll').is_file() or not binaries:
        raise RuntimeError('Missing packaged scientific backend.')
    return {'pe_files': len(binaries), 'native_dll_imports': records}


def package(label, revision, dirty, epoch, compiler, reports, inspection):
    destination = ROOT/'dist/release-windows'
    with tempfile.TemporaryDirectory(dir=ROOT/'dist') as temporary:
        stage = Path(temporary)
        application = stage/f'AFM-Workbench-{label}-windows-x64.zip'
        deterministic_zip(application, APP, epoch)
        source = stage/f'AFM-Workbench-{label}-windows-source.tar.gz'
        shutil.copy2(ROOT/'dist/AFM-Workbench-source.tar.gz', source)
        manifest = {
            'schema': 'afm-workbench.release.v1', 'version': version(), 'label': label,
            'revision': revision, 'dirty': dirty, 'source_date_epoch': epoch,
            'target': 'Windows x64', 'build_host': platform.platform(),
            'python': sys.version, 'compiler': compiler, 'signing': 'unsigned',
            'python_distributions': json.loads(output(sys.executable, '-m', 'pip', 'list', '--format=json')),
            'input_sha256': {p.relative_to(ROOT).as_posix(): sha256(p) for p in (TOOLCHAIN, NATIVE, LOCK, ROOT/'release/windows-bootstrap.lock')},
            'native_manifest_sha256': sha256(ROOT/'afm_workbench/_native/build-manifest.json'),
            'assets': {p.name: sha256(p) for p in (application, source)},
            'checks': reports, 'bundle_inspection': inspection,
            'requirements': ['Windows 10/11 x64', 'Microsoft Edge WebView2 Runtime', '.NET Framework 4.8'],
            'remaining_acceptance': ['packaged desktop visual startup', 'clean-machine installation', 'Authenticode signing', 'physical File Explorer folder drop'],
            'reproducibility': 'Pinned Python packages and native packages/sources; Python interpreter and Windows SDK/runtime are host-supplied and recorded. Byte-identical binaries across hosts are not promised.'}
        (stage/'build-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        (stage/'release-notes.md').write_text(
            f'# AFM Workbench {label} - experimental Windows x64 candidate\n\n'
            'Extract the entire ZIP, then open `AFM Workbench/AFM Workbench.exe`. '
            'Keep the `_internal` folder next to the executable. No Python or compiler installation is needed. '
            'Requires Windows 10/11 x64, Microsoft Edge WebView2 Runtime and .NET Framework 4.8.\n\n'
            'This build is unsigned. Windows may display a SmartScreen warning. '
            'Packaged desktop visual startup, clean-machine installation and physical File Explorer folder drops remain unverified. '
            'Keep the candidate as a draft pending those acceptance checks.\n\n'
            'The build manifest records exactly which Python, packaged runtime, browser and desktop checks ran. '
            'Six legacy browser checks remain inactive. Synthetic tests do not establish validation for every experimental dataset.\n\n'
            'The matching source archive includes the native dependency sources, recipes and patches; '
            "GitHub's automatic source ZIP does not replace it. `SHA256SUMS` covers every release asset; "
            'use PowerShell `Get-FileHash -Algorithm SHA256` to verify downloads.\n\n'
            f'Source commit: `{revision}`. Dirty checkout: `{dirty}`.\n', encoding='utf-8')
        # The upload job verifies on Linux; CRLF would become part of each filename.
        (stage/'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in sorted(stage.iterdir())), encoding='utf-8', newline='\n')
        remove_generated(destination)
        shutil.copytree(stage, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--tag', help='Exact windows-vX.Y.Z tag at HEAD; requires a clean checkout')
    parser.add_argument('--acceptance', action='store_true', help='Run all active checks, including browser/native GUI; requires Playwright')
    parser.add_argument('--browser', help='Chromium executable for acceptance checks')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'} or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Use CPython 3.12 on native Windows x64.')
    app_version = version()
    for line in LOCK.read_text().splitlines():
        if line and not line.startswith('#'):
            name, required = line.split(' --hash=', 1)[0].split('==')
            if metadata.version(name) != required:
                raise RuntimeError(f'Install the hash-locked release dependencies: {name}=={required} required.')
    revision = output('git', 'rev-parse', 'HEAD')
    dirty = bool(output('git', 'status', '--porcelain', '--untracked-files=all'))
    if output('git', 'ls-files', '--others', '--exclude-standard'):
        raise RuntimeError('Stage all new release source files before building.')
    if args.tag and (args.tag != 'windows-v'+app_version or dirty or output('git', 'rev-parse', args.tag+'^{commit}') != revision):
        raise RuntimeError('Windows release requires the matching tag at HEAD and a clean checkout.')
    epoch = int(output('git', 'show', '-s', '--format=%ct', 'HEAD'))
    os.environ.update(PYTHONUTF8='1', PYTHONHASHSEED='0', SOURCE_DATE_EPOCH=str(epoch),
                      PYINSTALLER_CONFIG_DIR=str(WORK/'pyinstaller-cache'))
    remove_generated(ROOT/'dist/release-windows')
    compiler = native_build(args.offline)
    run(sys.executable, 'scripts/build.py')
    selections = ([['--full', '--bundle', BUNDLE, *(['--browser', args.browser] if args.browser else [])]]
                  if args.acceptance else [['--full', '--kind', 'unit'], ['--check', 'runtime', '--bundle', BUNDLE]])
    reports = []
    for selection in selections:
        run(sys.executable, 'scripts/test.py', *selection)
        latest = max((ROOT/'.test-artifacts/runs').glob('*/report.json'), key=lambda p:p.stat().st_mtime_ns)
        reports.append(summarize_report(json.loads(latest.read_text())))
    inspection = inspect_bundle(APP)
    if args.tag and output('git', 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('Release source changed during the build.')
    label = args.tag or f'v{app_version}-snapshot'
    print('Windows candidate: '+str(package(label, revision, dirty, epoch, compiler, reports, inspection)))


if __name__ == '__main__':
    main()
