#!/usr/bin/env python3
"""Collect pinned dependency source archives, original recipes, patches and notices.

The manifest must describe the packages actually used for the native build.
This script extracts package metadata only; it never executes downloaded code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile


def decompress_zstd(source, destination, zstd='zstd'):
    # Release environments use the hash-locked Python wheel, without Homebrew.
    try:
        import zstandard
    except ImportError:
        subprocess.run([zstd, '-d', '-f', str(source), '-o', str(destination)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        with source.open('rb') as compressed, destination.open('wb') as output:
            zstandard.ZstdDecompressor().copy_stream(compressed, output)


def acquire(spec, cache, download):
    name=spec.get('filename') or spec['url'].rsplit('/',1)[-1]
    target=cache/name
    if not target.exists():
        if not download:
            raise RuntimeError(f'Missing {target}; copy the pinned file or pass --download.')
        partial = target.with_name(target.name + '.partial')
        with urllib.request.urlopen(spec['url'],timeout=120) as response,partial.open('wb') as stream:
            shutil.copyfileobj(response,stream)
        if hashlib.sha256(partial.read_bytes()).hexdigest() != spec['sha256']:
            raise RuntimeError(f'Checksum mismatch: {partial}')
        partial.replace(target)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=spec['sha256']:
        raise RuntimeError(f'Checksum mismatch: {target}')
    return target


def collect(manifest, cache, source_bundle, licenses, zstd='zstd', download=False):
    records=json.loads(manifest.read_text())
    for folder in (cache,source_bundle,licenses):folder.mkdir(parents=True,exist_ok=True)
    for package in records['packages']:
        archive=acquire(package,cache,download)
        name=package['name']
        metadata=cache/(name+'-metadata');metadata.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as container:
            member=next(m for m in container.namelist() if m.startswith('info-') and m.endswith('.tar.zst'))
            compressed=metadata/Path(member).name;compressed.write_bytes(container.read(member))
        unpacked=metadata/'metadata.tar'
        decompress_zstd(compressed, unpacked, zstd)
        with tarfile.open(unpacked) as tar:tar.extractall(metadata,filter='data')
        recipe=metadata/'info/recipe'
        if not recipe.is_dir():raise RuntimeError(f'No source recipe in {archive}')
        shutil.copytree(recipe,source_bundle/'dependency-recipes'/name,dirs_exist_ok=True)
        if (metadata/'info/licenses').is_dir():
            shutil.copytree(metadata/'info/licenses',licenses/name,dirs_exist_ok=True)
        for item in package['sources']:
            source=acquire(item,cache,download)
            shutil.copy2(source,source_bundle/source.name)
            # Include original notices; the entire unmodified source archive is also retained.
            with tarfile.open(source) as tar:
                for member in tar:
                    path=Path(member.name)
                    if not member.isfile() or '..' in path.parts or path.is_absolute():continue
                    if path.name.upper().startswith(('COPYING','COPYRIGHT','LICENSE','LICENCE','NOTICE')) or 'LICENSES' in path.parts:
                        target=licenses/name/Path(*path.parts[1:])
                        target.parent.mkdir(parents=True,exist_ok=True)
                        content=tar.extractfile(member)
                        if content:target.write_bytes(content.read())
    shutil.copy2(manifest,source_bundle/'dependency-source-manifest.json')
    print(f'Collected sources, recipes, patches and notices for {len(records["packages"])} dependency packages.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('.test-artifacts/native/dependency-packages'))
    p.add_argument('--source-bundle',type=Path,default=Path('afm_workbench/_native/sources'))
    p.add_argument('--licenses',type=Path,default=Path('afm_workbench/_native/licenses'))
    p.add_argument('--zstd',default='zstd')
    p.add_argument('--download',action='store_true')
    a=p.parse_args();collect(a.manifest,a.cache,a.source_bundle,a.licenses,a.zstd,a.download)


if __name__=='__main__':main()
