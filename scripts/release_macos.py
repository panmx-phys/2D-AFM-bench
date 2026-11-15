#!/usr/bin/env python3
"""Build a pinned Apple Silicon candidate; --tag requires a clean tagged commit.

Without --tag, build a clearly marked local snapshot of staged/working files.
Does not push tags, sign with Developer ID, notarize, or publish a release.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

try:
    from .collect_native_sources import acquire, decompress_zstd
    from .source_release import deterministic_archive
except ImportError:
    from collect_native_sources import acquire, decompress_zstd
    from source_release import deterministic_archive

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.test-artifacts/release-macos'
APP = ROOT / 'dist/AFM Workbench.app'
BUNDLE = APP / 'Contents/MacOS/AFM Workbench'
CONFIG = ROOT / 'release/macos-arm64.json'
LOCKS = [ROOT / 'release/macos-bootstrap.lock', ROOT / 'release/macos-arm64.lock']
NATIVE = ROOT / 'native/dependencies-macos-arm64.json'


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, **kwargs)


def output(*args):
    return subprocess.check_output([str(arg) for arg in args], cwd=ROOT, text=True).strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    tree = ast.parse((ROOT / 'afm_workbench/__init__.py').read_text())
    runtime = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    if runtime != project or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', project):
        raise RuntimeError('Release requires matching X.Y.Z versions in pyproject.toml and __init__.py.')
    return project


def validate_tag(tag, app_version, revision, tagged_revision, dirty):
    if tag != 'v' + app_version:
        raise RuntimeError(f'Tag must exactly match v{app_version}.')
    if tagged_revision != revision:
        raise RuntimeError('Tag does not point to the checked-out commit.')
    if dirty:
        raise RuntimeError('Tagged release requires a clean checkout, including untracked source.')


def preflight(tag):
    config = json.loads(CONFIG.read_text())
    if sys.platform != 'darwin' or platform.machine() != config['machine']:
        raise RuntimeError('This release recipe requires native macOS arm64; Intel/Windows are not supported.')
    app_version = version()
    revision = output('git', 'rev-parse', 'HEAD')
    dirty = bool(output('git', 'status', '--porcelain', '--untracked-files=all'))
    if tag:
        validate_tag(tag, app_version, revision, output('git', 'rev-parse', tag + '^{commit}'), dirty)
    # Local snapshots still must include newly written source in corresponding sources.
    untracked = output('git', 'ls-files', '--others', '--exclude-standard')
    if untracked:
        raise RuntimeError('Stage new source files before building: ' + untracked)
    epoch = int(output('git', 'show', '-s', '--format=%ct', 'HEAD'))
    os.environ.update(SOURCE_DATE_EPOCH=str(epoch), PYTHONHASHSEED=config['python_hash_seed'],
                      MACOSX_DEPLOYMENT_TARGET=config['deployment_target'], TZ='UTC',
                      CC='/usr/bin/clang', CFLAGS=config['native_cflags'], CPPFLAGS='', LDFLAGS='',
                      PYTHONNOUSERSITE='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_NO_CACHE_DIR='1',
                      PYINSTALLER_CONFIG_DIR=str(WORK / 'pyinstaller-cache'),
                      AFM_RUNTIME_NOTICES_DIR=str(WORK / 'python-runtime-notices'))
    return config, app_version, revision, dirty, epoch


def extract_package(archive, prefix, scratch):
    """Unpack checksum-verified conda payloads; never execute package scripts."""
    with zipfile.ZipFile(archive) as container:
        members = [name for name in container.namelist()
                   if name.startswith('pkg-') and name.endswith('.tar.zst')]
        if len(members) != 1:
            raise RuntimeError('Expected one conda payload: ' + str(archive))
        compressed = scratch / 'payload.tar.zst'
        compressed.write_bytes(container.read(members[0]))
    payload = scratch / 'payload.tar'
    decompress_zstd(compressed, payload)
    with tarfile.open(payload) as tar:
        tar.extractall(prefix, filter='data')


def native_build(offline):
    """Run in the locked venv. Rebuild from fresh source and package extraction."""
    cache = WORK / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    prefix = WORK / 'dependencies'
    build = WORK / 'native-build'
    staging = WORK / 'native-output'
    for path in (prefix, build, staging):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir()
    records = json.loads(NATIVE.read_text())
    with tempfile.TemporaryDirectory(dir=WORK) as scratch:
        for spec in [*records['packages'], records['glib_development_header']]:
            archive = acquire(spec, cache, not offline)
            extract_package(archive, prefix, Path(scratch))
    # libglib contains public headers; the glib package supplies glibconfig.h.
    configs = list(prefix.rglob('glibconfig.h'))
    if len(configs) != 1 or not (prefix / 'include/glib-2.0/glib.h').is_file():
        raise RuntimeError('Pinned GLib packages are missing development headers.')
    # Conda Mach-O IDs refer to their original build prefix. The native bundler
    # resolves those references by filename against this extracted prefix.
    sources = build / 'sources'
    sources.mkdir()
    try:
        from .build_gwyddion import SOURCES
    except ImportError:
        from build_gwyddion import SOURCES
    for spec in SOURCES.values():
        shutil.copy2(acquire(spec, cache, not offline), sources / spec['filename'])
    command = [sys.executable, 'scripts/build_gwyddion.py', '--build-dir', build,
               '--output', staging, '--glib-prefix', prefix, '--glib-config-dir', configs[0].parent,
               '--build-fftw', '--dependency-manifest', NATIVE, '--dependency-cache', cache]
    if not offline:
        command.append('--download')
    run(*command)
    target = ROOT / 'afm_workbench/_native'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(staging, target)


def collect_python_notices(config, offline):
    import zstandard
    archive = acquire(config['python_build_metadata'], WORK / 'downloads', not offline)
    destination = WORK / 'python-runtime-notices'
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    with archive.open('rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader:
        with tarfile.open(fileobj=reader, mode='r|') as tar:
            for member in tar:
                if not member.isfile():
                    continue
                if member.name == 'python/PYTHON.json' or member.name.startswith('python/licenses/'):
                    relative = Path(member.name).relative_to('python')
                    if '..' in relative.parts:
                        raise RuntimeError('Unsafe Python metadata path.')
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
    if not (destination / 'licenses/LICENSE.cpython.txt').is_file():
        raise RuntimeError('Portable Python archive did not contain its runtime notices.')
    (destination / 'distribution.json').write_text(json.dumps({
        key: config[key] for key in ('python', 'python_distribution', 'python_build_metadata')}, indent=2) + '\n')


def bootstrap(config, offline):
    downloads = WORK / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    archive = acquire(config['python_distribution'], downloads, not offline)
    runtime = WORK / 'interpreter'
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(runtime, filter='data')
    interpreter = runtime / 'python/bin/python3.12'
    if output(interpreter, '--version') != 'Python ' + config['python']:
        raise RuntimeError('Portable interpreter does not match the release configuration.')
    environment = WORK / 'venv'
    if environment.exists():
        shutil.rmtree(environment)
    run(interpreter, '-m', 'venv', environment)
    python = environment / 'bin/python'
    # The wheel cache is optional. pip verifies hashes even when using it.
    cache = WORK / 'python-downloads'
    cache.mkdir(parents=True, exist_ok=True)
    for lock in LOCKS:
        common = ['--require-hashes', '--no-deps', '--no-build-isolation', '-r', lock]
        if not offline:
            run(python, '-m', 'pip', 'download', '--dest', cache, *common)
        run(python, '-m', 'pip', 'install', '--no-index', '--find-links', cache, *common)
    run(python, '-m', 'pip', 'check')
    return python


def inspect_bundle(app):
    """Reject host-library leakage; inspect the actual arm64 deployment floor."""
    magic = {bytes.fromhex(value) for value in ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe',
                                              'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
    minimum = (0, 0, 0)
    count = 0
    for path in sorted(app.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in magic:
                continue
        count += 1
        run('lipo', '-verify_arch', 'arm64', path, stdout=subprocess.DEVNULL)
        load = output('otool', '-arch', 'arm64', '-l', path)
        versions = re.findall(r'\bminos (\d+(?:\.\d+){0,2})', load)
        versions += re.findall(r'cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+(?:\.\d+){0,2})', load)
        for value in versions:
            parts = tuple(map(int, value.split('.')))
            minimum = max(minimum, (*parts, *(0 for _ in range(3 - len(parts)))))
        for line in output('otool', '-arch', 'arm64', '-L', path).splitlines()[1:]:
            ref = line.strip().split(' (', 1)[0]
            if ref.startswith('/') and not ref.startswith(('/usr/lib/', '/System/Library/')):
                raise RuntimeError(f'External library in {path.name}: {ref}')
    if not count:
        raise RuntimeError('No Mach-O binaries found in the application.')
    return {'mach_o_files': count, 'minimum_macos': '.'.join(map(str, minimum))}


def summarize_report(report):
    # Keep release manifests portable; local reports retain paths and timing.
    return {'results': [{k: v for k, v in result.items()
                         if k in ('id', 'kind', 'status', 'tests', 'failures', 'errors', 'skipped')}
                        for result in report['results']],
            'deferred': report['deferred'], 'inactive': report['inactive']}


def package(config, app_version, revision, dirty, epoch, tag, python, reports, inspection):
    label = tag or f'v{app_version}-snapshot'
    destination = ROOT / 'dist/release'
    with tempfile.TemporaryDirectory(dir=ROOT / 'dist') as temporary:
        stage = Path(temporary)
        stem = f'AFM-Workbench-{label}-macos-arm64'
        application = stage / (stem + '.tar.gz')
        deterministic_archive(application, [(APP, APP.name), *[
            (p, APP.name + '/' + p.relative_to(APP).as_posix()) for p in APP.rglob('*')]], epoch)
        source = stage / f'AFM-Workbench-{label}-source.tar.gz'
        shutil.copy2(ROOT / 'dist/AFM-Workbench-source.tar.gz', source)
        inventory = json.loads(output(python, '-m', 'pip', 'list', '--format=json'))
        manifest = {
            'schema': 'afm-workbench.release.v1', 'version': app_version, 'tag': tag,
            'revision': revision, 'dirty': dirty, 'source_date_epoch': epoch,
            'target': config, 'python': output(python, '--version'),
            'macos': platform.mac_ver()[0], 'compiler': output('/usr/bin/clang', '--version').splitlines()[0],
            'sdk': output('xcrun', '--show-sdk-version'),
            'runner_image': os.environ.get('ImageVersion'),
            'python_distributions': inventory,
            'input_sha256': {p.relative_to(ROOT).as_posix(): sha256(p) for p in [CONFIG, *LOCKS, NATIVE]},
            'native_manifest_sha256': sha256(ROOT / 'afm_workbench/_native/build-manifest.json'),
            'bundle_inspection': inspection,
            'assets': {p.name: sha256(p) for p in (application, source)},
            'checks': reports,
            'signing': 'ad-hoc; not Developer ID signed or notarized',
            'reproducibility': 'Pinned dependencies and normalized archives; binary identity requires the same Python distribution, compiler, SDK and build paths.',
            'deferred': ['browser and native GUI workflows', 'clean Mac installation',
                         'Developer ID signing and notarization', 'Intel Mac and Windows'],
        }
        (stage / 'build-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        (stage / 'release-notes.md').write_text(
            f'AFM Workbench {label} — Apple Silicon Mac candidate\n\n'
            f"Binary deployment floor: macOS {inspection['minimum_macos']}, arm64 only; "
            'this is not a clean-Mac compatibility test. Ad-hoc signed; not Developer ID signed or notarized. '
            'Keep this release as a draft until installation and desktop acceptance checks are complete.\n\n'
            'The build ran the full active Python suite and a runtime smoke against the packaged application. '
            'Browser/native GUI workflows and six legacy browser scripts are not certified by this workflow. '
            'Intel Mac and Windows binaries are not supplied.\n\n'
            'Download the application archive and matching corresponding-source archive. '
            'The automatically generated GitHub source archives omit native dependency sources. '
            'Verify downloads with `shasum -a 256 -c SHA256SUMS`.\n\n'
            f'Source commit: {revision}\n')
        (stage / 'SHA256SUMS').write_text(''.join(
            f'{sha256(p)}  {p.name}\n' for p in sorted(stage.iterdir())))
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(stage, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Exact vX.Y.Z tag at HEAD; requires a clean checkout')
    parser.add_argument('--offline', action='store_true', help='Use only previously verified download caches')
    parser.add_argument('--native-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    config, app_version, revision, dirty, epoch = preflight(args.tag)
    WORK.mkdir(parents=True, exist_ok=True)
    if args.native_only:
        collect_python_notices(config, args.offline)
        native_build(args.offline)
        return
    # Never leave a previous release looking like the output of a failed attempt.
    if (ROOT / 'dist/release').exists():
        shutil.rmtree(ROOT / 'dist/release')
    python = bootstrap(config, args.offline)
    run(python, __file__, '--native-only', *(['--offline'] if args.offline else []))
    run(python, 'scripts/build.py')
    reports = []
    for selection in (['--full', '--kind', 'unit'], ['--check', 'runtime', '--bundle', BUNDLE]):
        run(python, 'scripts/test.py', *selection)
        latest = max((ROOT / '.test-artifacts/runs').glob('*/report.json'), key=lambda p: p.stat().st_mtime_ns)
        reports.append(summarize_report(json.loads(latest.read_text())))
    run('codesign', '--verify', '--deep', '--strict', APP)
    inspection = inspect_bundle(APP)
    minimum = tuple(map(int, inspection['minimum_macos'].split('.')))
    target = tuple(map(int, config['deployment_target'].split('.'))) + (0,)
    if args.tag and minimum > target:
        raise RuntimeError(f'Bundle requires macOS {minimum}; exceeds the locked deployment target. '
                           'Use a Python distribution built for the release target.')
    # Ensure tagged source has not changed while the build was running.
    if args.tag:
        preflight(args.tag)
    print('Release candidate: ' + str(package(config, app_version, revision, dirty, epoch,
                                             args.tag, python, reports, inspection)), flush=True)


if __name__ == '__main__':
    main()
