"""Package tracked Workbench source and the native dependency source bundle.

Run after staging/committing the release source. No workspace, experimental
files, ignored build cache, credentials or native binaries enter this archive.
The build's dependency source manifest must describe the binaries distributed.
"""
from pathlib import Path
import argparse
import json
import hashlib
import gzip
import os
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def public_tar_metadata(member):
    """Avoid exposing the build machine's account names and numeric identities."""
    member.uid = member.gid = 0
    member.uname = member.gname = ''
    for key in ('uid', 'gid', 'uname', 'gname'):
        member.pax_headers.pop(key, None)
    return member


def deterministic_archive(destination, entries, epoch):
    """Stable order, owner, modes and timestamps; retain bundle symlinks."""
    with Path(destination).open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for path, name in sorted(entries, key=lambda item: item[1]):
                    member = public_tar_metadata(archive.gettarinfo(path, arcname=name))
                    member.mtime = epoch
                    member.pax_headers = {}
                    member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                    if member.issym():
                        member.mode = 0o777
                    if member.isfile():
                        with Path(path).open('rb') as content:
                            archive.addfile(member, content)
                    else:
                        archive.addfile(member)


def create_source_release(destination, native_sources=None):
    sources = Path(native_sources or ROOT/'afm_workbench/_native/sources').resolve()
    required = ['gwyddion-2.71.tar.xz', 'fftw-3.3.10.tar.gz', 'dependency-source-manifest.json', 'native-build-manifest.json']
    missing = [name for name in required if not (sources/name).is_file()]
    if missing:
        raise RuntimeError('Native corresponding-source collection is incomplete: ' + ', '.join(missing)
                           + '. See native/README.md before distributing binaries.')
    native_manifest = json.loads((sources/'native-build-manifest.json').read_text())
    for spec in native_manifest['upstream_sources'].values():
        archive = sources/spec['filename']
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
            raise RuntimeError('Native source archive is missing or mismatched: ' + spec['filename'])
    with tarfile.open(sources/'gwyddion-2.71.tar.xz') as upstream:
        for filename, expected in native_manifest['upstream_file_sha256'].items():
            content = upstream.extractfile('gwyddion-2.71/'+filename)
            if content is None or hashlib.sha256(content.read()).hexdigest() != expected:
                raise RuntimeError('Bundle the actual modified native source before distribution: ' + filename)
        linematch = upstream.extractfile('gwyddion-2.71/modules/process/linematch.c')
        if linematch is None or hashlib.sha256(linematch.read()).hexdigest() != native_manifest['linematch_sha256']:
            raise RuntimeError('Native module-helper sources do not match the corresponding-source archive.')
    manifest = json.loads((sources/'dependency-source-manifest.json').read_text())
    for package in manifest['packages']:
        for item in package['sources']:
            filename = item.get('filename') or item['url'].rsplit('/', 1)[-1]
            if not (sources/filename).is_file():
                raise RuntimeError('Missing dependency source: ' + filename)
            if hashlib.sha256((sources/filename).read_bytes()).hexdigest() != item['sha256']:
                raise RuntimeError('Dependency source checksum mismatch: ' + filename)
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z', '--', '.']).decode().split('\0')
    files = [ROOT/name for name in tracked if name and (ROOT/name).is_file()]
    for essential in ('native/afm_gwyddion.c', 'native/afm_gwyddion.h', 'scripts/build_gwyddion.py',
                      'afm_workbench/native_backend.py', 'LICENSE'):
        if ROOT/essential not in files:
            raise RuntimeError('Stage release source before packaging: ' + essential)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH') or subprocess.check_output(
        ['git', '-C', str(ROOT), 'show', '-s', '--format=%ct', 'HEAD'], text=True).strip())
    entries = [(path, 'AFM-Workbench/'+path.relative_to(ROOT).as_posix()) for path in files]
    entries += [(path, 'AFM-Workbench/native-corresponding-source/'+path.relative_to(sources).as_posix())
                for path in sources.rglob('*')]
    deterministic_archive(destination, entries, epoch)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--native-sources', type=Path)
    args = parser.parse_args()
    print(create_source_release(args.output, args.native_sources))
