"""Publish the combined Windows/Mac application release that lab members download.

App attachments receive version-free names, so
``https://github.com/<repo>/releases/latest/download/<name>`` always serves the
newest published release. Notes start with plain download and first-start steps
from ``release/notes-template.md``; the technical record goes in a collapsed section.

Without ``--publish`` the release is created as a draft for review. ``--publish``
makes it public and marks it GitHub's Latest release; the notes still state its
experimental status. Existing release assets are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

try:
    from .release_macos import version
except ImportError:  # Direct script execution.
    from release_macos import version

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'release/notes-template.md'
WINDOWS_ASSET = 'AFM-Workbench-Windows.exe'
MAC_ASSET = 'AFM-Workbench-Mac.app.tar.gz'
APP_BUNDLE = 'AFM Workbench.app'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def megabytes(size):
    return f'{size / 1e6:.1f} MB'


def check_mac_archive(path):
    """The Mac download must contain exactly one app bundle and nothing else."""
    with tarfile.open(path) as archive:
        tops = {name.split('/', 1)[0] for name in archive.getnames() if name not in {'', '.'}}
    if tops != {APP_BUNDLE}:
        raise ValueError(f'Mac archive must contain only {APP_BUNDLE!r}; found {sorted(tops)}')


def stage_apps(windows, mac, stage):
    """Copy the two apps to version-free public names inside ``stage``."""
    if Path(windows).suffix.lower() != '.exe':
        raise ValueError('The Windows app must be an .exe file.')
    check_mac_archive(mac)
    staged = {WINDOWS_ASSET: Path(stage) / WINDOWS_ASSET, MAC_ASSET: Path(stage) / MAC_ASSET}
    shutil.copy2(windows, staged[WINDOWS_ASSET])
    shutil.copy2(mac, staged[MAC_ASSET])
    return staged


def render_notes(repo, tag, apps, details):
    """``apps`` maps the public asset names to local files."""
    checksums = '\n'.join(f'{sha256(path)}  {name}' for name, path in sorted(apps.items()))
    template = TEMPLATE.read_text(encoding='utf-8')
    values = {'repo': repo, 'tag': tag, 'details': details.strip() or 'No additional build record supplied.',
              'checksums': checksums,
              'windows_size': megabytes(Path(apps[WINDOWS_ASSET]).stat().st_size),
              'mac_size': megabytes(Path(apps[MAC_ASSET]).stat().st_size)}
    unknown = sorted(set(re.findall(r'\{([a-z_]+)\}', template)) - set(values))
    if unknown:
        raise ValueError(f'Unknown template fields: {unknown}')
    # One pass, so braces inside inserted details are never treated as fields.
    return re.sub(r'\{([a-z_]+)\}', lambda match: values[match.group(1)], template)


def title(app_version):
    return f'AFM Workbench {app_version} (experimental)'


def gh_commands(tag, app_version, notes_file, files, exists, publish):
    """Return the gh invocations. Uploads never pass --clobber."""
    state = ['--draft=false', '--prerelease=false', '--latest'] if publish else []
    if exists:
        return [['gh', 'release', 'upload', tag, *map(str, files)],
                ['gh', 'release', 'edit', tag, '--title', title(app_version),
                 '--notes-file', str(notes_file), *state]]
    create_state = ['--latest'] if publish else ['--draft']
    return [['gh', 'release', 'create', tag, '--verify-tag', '--title', title(app_version),
             '--notes-file', str(notes_file), *create_state, *map(str, files)]]


def repository():
    return json.loads(subprocess.check_output(
        ['gh', 'repo', 'view', '--json', 'nameWithOwner'], cwd=ROOT, text=True))['nameWithOwner']


def release_exists(tag):
    return subprocess.run(['gh', 'release', 'view', tag], cwd=ROOT,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tag', required=True, help='vX.Y.Z matching the application version')
    parser.add_argument('--windows', required=True, type=Path, help='Accepted Windows .exe')
    parser.add_argument('--mac', required=True, type=Path, help='Accepted Mac .tar.gz containing only the .app')
    parser.add_argument('--details', type=Path, help='Markdown technical record (checks, revisions, limitations)')
    parser.add_argument('--developer-file', type=Path, action='append', default=[],
                        help='Source archive, build manifest or records to attach unchanged; repeatable')
    parser.add_argument('--repo', help='owner/name; defaults to the gh repository of this checkout')
    parser.add_argument('--publish', action='store_true', help='Make the release public and mark it Latest')
    parser.add_argument('--notes-only', type=Path, metavar='FILE', help='Write the rendered notes and stop')
    parser.add_argument('--dry-run', action='store_true', help='Print gh commands without running them')
    args = parser.parse_args(argv)
    app_version = version()
    if args.tag != 'v' + app_version:
        raise SystemExit(f'Tag {args.tag} does not match application version {app_version}.')
    repo = args.repo or repository()
    details = args.details.read_text(encoding='utf-8') if args.details else ''
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        apps = stage_apps(args.windows, args.mac, stage)
        notes = render_notes(repo, args.tag, apps, details)
        if args.notes_only:
            args.notes_only.write_text(notes, encoding='utf-8')
            return 0
        notes_file = stage / 'release-notes.md'
        notes_file.write_text(notes, encoding='utf-8')
        files = [*apps.values(), *args.developer_file]
        exists = False if args.dry_run else release_exists(args.tag)
        for command in gh_commands(args.tag, app_version, notes_file, files, exists, args.publish):
            if args.dry_run:
                print(' '.join(command))
            else:
                subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
