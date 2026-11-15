"""Collect notices for the Python distributions actually included by PyInstaller.

Uses installed distribution records, never the network. Missing wheel notices
require a version-specific upstream copy with recorded provenance and checksum.
This inventory does not establish legal clearance for an arbitrary distribution.
"""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import sys
import sysconfig


def distribution_names(entries):
    mapping = metadata.packages_distributions()
    names = {'pyinstaller'}  # Its bootloader and runtime hooks are distributed.
    for name, source, _ in entries:
        parts = Path(source).parts
        if 'site-packages' not in parts:
            continue
        module = parts[parts.index('site-packages') + 1].split('.')[0]
        names.update(mapping.get(module, ()))
    return sorted(names, key=str.casefold)


def collect_notices(entries, root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fallbacks = json.loads((root/'licenses/python-fallbacks/manifest.json').read_text())
    files, records = [], []
    for name in distribution_names(entries):
        dist = metadata.distribution(name)
        notices = [p for p in (dist.files or ())
                   if re.match(r'^(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE)(?:[._-]|$)',
                               p.name, re.IGNORECASE)
                   and p.suffix.lower() in {'', '.txt', '.md', '.rst', '.bsd', '.apache', '.mit'}]
        record = {'name': dist.metadata['Name'], 'version': dist.version, 'notices': []}
        for relative in notices:
            source = Path(dist.locate_file(relative))
            if not source.is_file():
                raise RuntimeError(f'Missing installed notice for {name}: {relative}')
            # Keep source layout for identically named notices without recording local paths.
            safe = Path(*[p for p in relative.parts if p not in ('.', '..')])
            target = Path('licenses/python')/f'{name}-{dist.version}'/safe
            files.append((str(source), str(target.parent)))
            record['notices'].append({'file': target.as_posix(),
                                      'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        if not notices:
            fallback = next((f for f in fallbacks
                             if f['name'].casefold().replace('_', '-') == name.casefold().replace('_', '-')
                             and f['version'] == dist.version), None)
            if fallback is None:
                raise RuntimeError(f'No license notice for {name} {dist.version}; collect its upstream notice before packaging.')
            source = root/'licenses/python-fallbacks'/fallback['file']
            if hashlib.sha256(source.read_bytes()).hexdigest() != fallback['license_sha256']:
                raise RuntimeError(f'Upstream notice checksum mismatch for {name}')
            target = Path('licenses/python')/f'{name}-{dist.version}'/source.name
            files.append((str(source), str(target.parent)))
            record['notices'].append({'file': target.as_posix(), 'sha256': fallback['license_sha256'],
                                      'upstream': fallback})
        records.append(record)
    candidates = [Path(sysconfig.get_path('stdlib'))/'LICENSE.txt',
                  Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'LICENSE']
    python_notice = next((p for p in candidates if p.is_file()), None)
    if python_notice is None:
        raise RuntimeError('Python runtime license notice not found; install the interpreter license before packaging.')
    files.append((str(python_notice), 'licenses/python/runtime'))
    manifest = output/'manifest.json'
    manifest.write_text(json.dumps({'python': sys.version.split()[0],
                                   'python_license_sha256': hashlib.sha256(python_notice.read_bytes()).hexdigest(),
                                   'distributions': records}, indent=2)+'\n')
    files.append((str(manifest), 'licenses/python'))
    return files
