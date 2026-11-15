"""Catalog and run focused checks. See docs/testing.md; no third-party runner needed."""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_catalog(root=ROOT):
    catalog = json.loads((root / 'tests/catalog.json').read_text())
    checks = catalog['checks']
    ids = [c['id'] for c in checks]
    paths = [c['path'] for c in checks]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError('Duplicate check ID or path in tests/catalog.json')
    discovered = {p.relative_to(root).as_posix() for pattern in
                  ('tests/test_*.py', 'scripts/*-smoke.py', 'scripts/*-smoke.cjs', 'scripts/check_*.py')
                  for p in root.glob(pattern)}
    if discovered != set(paths):
        raise ValueError(f'Catalog drift: uncataloged={sorted(discovered-set(paths))}; '
                         f'missing={sorted(set(paths)-discovered)}')
    for check in checks:
        if check['kind'] not in {'unit', 'browser', 'desktop', 'runtime', 'reference'}:
            raise ValueError('Unknown kind: ' + check['id'])
        if check['status'] not in {'active', 'legacy', 'maintenance'}:
            raise ValueError('Unknown status: ' + check['id'])
        if not check['groups'] or not check['purpose']:
            raise ValueError('Missing group or purpose: ' + check['id'])
    return catalog


def changed_paths(root=ROOT, base='HEAD'):
    """Include staged, unstaged, untracked, and both sides of renames; stay in this project."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().split('\0')
    paths = git('diff', '--name-only', '--no-renames', '--relative', '-z', base, '--', '.')
    paths += git('ls-files', '--others', '--exclude-standard', '-z', '--', '.')
    return sorted({p for p in paths if p})


def dependency_graph(root=ROOT):
    """Follow local Python imports, including imports inside functions and shared test fixtures."""
    files = [*root.glob('afm_workbench/*.py'), *root.glob('tests/test_*.py'),
             *root.glob('scripts/*.py')]
    modules = {}
    for path in files:
        rel = path.relative_to(root)
        name = '.'.join(rel.with_suffix('').parts)
        if path.name == '__init__.py':
            name = name.removesuffix('.__init__')
        modules[name] = rel.as_posix()
        if rel.parts[0] in {'tests', 'scripts'}:
            modules[path.stem] = rel.as_posix()
    graph = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        package = '.'.join(path.relative_to(root).parts[:-1])
        imports = set()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), filename=rel)):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = '.'.join(package.split('.')[:len(package.split('.'))-node.level+1]) if node.level else ''
                parent = '.'.join(p for p in (prefix, node.module) if p)
                names = [parent, *(parent + '.' + a.name for a in node.names)]
            else:
                continue
            for name in names:
                # Importing a submodule also executes its package __init__.
                for i in range(1, len(name.split('.')) + 1):
                    module = '.'.join(name.split('.')[:i])
                    if module in modules:
                        imports.add(modules[module])
        graph[rel] = imports
    return graph


def dependencies(path, graph):
    visited, pending = set(), [path]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(graph.get(current, ()))
    return visited


def select_changed(catalog, paths, root=ROOT):
    checks = catalog['checks']
    graph = dependency_graph(root)
    scopes = {c['id']: dependencies(c['path'], graph) for c in checks}
    reasons = {}
    for path in paths:
        if any(fnmatchcase(path, p) for p in catalog['no_test_changes']):
            continue
        modules = {rule['module'] for rule in catalog.get('dependency_inputs', [])
                   if any(fnmatchcase(path, p) for p in rule['patterns'])}
        matched = False
        for check in checks:
            if (path in scopes[check['id']] or scopes[check['id']] & modules
                    or any(fnmatchcase(path, p) for p in check.get('affects', []))):
                reasons.setdefault(check['id'], []).append(path)
                # A broad legacy UI pattern must not hide a new, unmapped feature.
                matched |= check['status'] == 'active' or path == check['path']
        if matched:
            continue
        # An unknown implementation/configuration change must not produce a false green.
        for check in checks:
            if check['status'] == 'active':
                reasons.setdefault(check['id'], []).append('unmapped change: ' + path)
    return reasons


def print_plan(catalog, reasons, kinds=()):
    selected = []
    for check in catalog['checks']:
        if check['id'] not in reasons:
            continue
        state = check['status']
        if state == 'active' and kinds and check['kind'] not in kinds:
            state = 'deferred'
        elif state == 'active':
            state = 'run'
            selected.append(check)
        print(f"{state:11} {check['id']:22} {check['kind']:9} {', '.join(reasons[check['id']])}")
        if check.get('note'):
            print('            ' + check['note'])
    return selected


@contextmanager
def server(root, run_dir, check_id, bundle=None):
    """Each smoke gets a fresh synthetic catalog, a random loopback port and guaranteed cleanup."""
    command = [str(bundle)] if bundle else [sys.executable, '-m', 'afm_workbench']
    with tempfile.TemporaryDirectory(prefix='afm-check-') as workspace:
        log_path = run_dir / (check_id + '-server.log')
        ready = Path(workspace) / 'server-ready.txt'
        # Keep one-file extraction inside this disposable workspace. Its parent
        # bootloader and child server both need stopping before cleanup on Windows.
        env = {**os.environ, 'TEMP': workspace, 'TMP': workspace} if sys.platform == 'win32' else None
        with log_path.open('w') as output:
            process = subprocess.Popen(command + ['--browser', '--demo', '--port', '0',
                                       '--data-dir', workspace, '--ready-file', str(ready)], cwd=root, stdout=output,
                                       stderr=subprocess.STDOUT, env=env)
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if ready.is_file():
                        url = ready.read_text(encoding='utf-8')
                        if re.fullmatch(r'http://127\.0\.0\.1:\d+/', url):
                            yield url
                            return
                    log = log_path.read_text(errors='replace')
                    match = re.search(r'AFM Workbench: (http://127\.0\.0\.1:\d+/)', log)
                    if match:
                        yield match.group(1)
                        return
                    if process.poll() is not None:
                        raise RuntimeError(f'Server exited ({process.returncode}): {log}')
                    time.sleep(.1)
                raise TimeoutError('Server did not start within 60 seconds: ' + str(log_path))
            finally:
                if process.poll() is None:
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       stdout=output, stderr=subprocess.STDOUT, check=True, timeout=15)
                        process.wait(timeout=5)
                    else:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


def run_check(check, args, run_dir):
    start = time.monotonic()
    record = {'id': check['id'], 'kind': check['kind'], 'status': 'failed',
              'target': 'source' if check['kind'] == 'unit' else (str(args.bundle) if args.bundle else 'source')}
    log_path = run_dir / (check['id'] + '.log')
    record['log'] = str(log_path.relative_to(ROOT))
    original_path = sys.path[:]
    with log_path.open('w') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            if check['kind'] == 'unit':
                sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'scripts'), str(ROOT)]
                suite = unittest.defaultTestLoader.loadTestsFromName(Path(check['path']).stem)
                result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
                record.update(tests=result.testsRun, failures=len(result.failures),
                              errors=len(result.errors), skipped=len(result.skipped))
                record['status'] = ('failed' if not result.wasSuccessful() or not result.testsRun
                                    else 'incomplete' if result.skipped else 'passed')
            else:
                with server(ROOT, run_dir, check['id'], args.bundle) as url:
                    command = ([args.node] if check['kind'] == 'browser' else [sys.executable])
                    command += [check['path'], url, *check.get('args', [])]
                    if check['kind'] == 'browser' and args.browser:
                        command.append(args.browser)
                    env = {**os.environ, 'AFM_PYTHON': sys.executable}
                    record['command'] = command
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=args.timeout)
                    record['status'] = 'passed' if result.returncode == 0 else 'failed'
                    record['exit_code'] = result.returncode
        except Exception as exc:
            record['error'] = str(exc)
            traceback.print_exc()
        finally:
            sys.path[:] = original_path
    record['seconds'] = round(time.monotonic() - start, 3)
    print(f"{record['status']:11} {check['id']:22} {record['seconds']:7.2f}s  {record['log']}", flush=True)
    if record['status'] != 'passed':
        print(log_path.read_text()[-4000:])
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--changed', action='store_true', help='Default: staged, unstaged and untracked changes')
    mode.add_argument('--full', action='store_true', help='All active checks, including GUI checks')
    mode.add_argument('--check', action='append', help='Exact catalog ID; repeat to combine without duplicates')
    mode.add_argument('--group', action='append', help='Catalog group; repeat to combine without duplicates')
    mode.add_argument('--list', action='store_true', help='Audit and list the whole catalog without running tests')
    parser.add_argument('--base', default='HEAD', help='Git revision to compare with, including local changes')
    parser.add_argument('--kind', action='append', choices=['unit', 'browser', 'desktop', 'runtime'],
                        help='Run only these kinds; explicitly report the other affected checks as deferred')
    parser.add_argument('--plan', action='store_true', help='Print selections and reasons without running checks')
    parser.add_argument('--bundle', type=Path, help='Smoke-test this rebuilt executable; unit tests still use source')
    parser.add_argument('--node', default='node', help='Node executable for Playwright checks')
    parser.add_argument('--browser', help='Optional Chromium executable for Playwright checks')
    parser.add_argument('--timeout', type=float, default=300, help='Timeout per smoke script in seconds')
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog()
        if args.list:
            for c in catalog['checks']:
                print(f"{c['id']:22} {c['kind']:9} {c['status']:11} {','.join(c['groups'])}\n"
                      f"  {c['path']} — {c['purpose']}")
                if c.get('note'):
                    print('  ' + c['note'])
            return 0
        paths = []
        if args.check:
            unknown = set(args.check) - {c['id'] for c in catalog['checks']}
            if unknown:
                raise ValueError('Unknown check IDs: ' + ', '.join(sorted(unknown)))
            reasons = {name: ['explicit selection'] for name in args.check}
        elif args.group:
            unknown = set(args.group) - {g for c in catalog['checks'] for g in c['groups']}
            if unknown:
                raise ValueError('Unknown groups: ' + ', '.join(sorted(unknown)))
            reasons = {c['id']: ['group selection'] for c in catalog['checks'] if set(c['groups']) & set(args.group)}
        elif args.full:
            reasons = {c['id']: ['full catalog'] for c in catalog['checks']}
        else:
            paths = changed_paths(base=args.base)
            reasons = select_changed(catalog, paths)
            print('Changed paths: ' + (', '.join(paths) or 'none'))
        if args.bundle:
            args.bundle = args.bundle.expanduser().resolve()
            if not args.bundle.is_file():
                raise ValueError('--bundle must name an existing executable, not the .app directory')
            reasons['runtime'] = ['rebuilt executable requested']
        selected = print_plan(catalog, reasons, args.kind)
        print(f'{len(selected)} active check(s) selected. Catalog audit passed.')
        if args.plan:
            return 0
        blocked = [c['id'] for c in catalog['checks'] if args.check and c['id'] in args.check and c['status'] != 'active']
        if blocked:
            raise ValueError('Not runnable by this runner: ' + ', '.join(blocked) + '; see catalog notes')
        if args.timeout <= 0:
            raise ValueError('--timeout must be positive')
        run_dir = ROOT / '.test-artifacts' / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        run_dir.mkdir(parents=True)
        report = {'started_at': datetime.now(timezone.utc).isoformat(), 'base': args.base,
                  'revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
                  'python': sys.version, 'platform': platform.platform(),
                  'changed_paths': paths, 'selection': reasons, 'results': [],
                  'deferred': [c['id'] for c in catalog['checks'] if c['id'] in reasons
                               and c['status'] == 'active' and c not in selected],
                  'inactive': [c['id'] for c in catalog['checks'] if c['id'] in reasons and c['status'] != 'active']}
        report_path = run_dir / 'report.json'
        try:
            for check in selected:
                report['results'].append(run_check(check, args, run_dir))
                report_path.write_text(json.dumps(report, indent=2) + '\n')
        finally:
            report_path.write_text(json.dumps(report, indent=2) + '\n')
        print('Report: ' + str(report_path.relative_to(ROOT)))
        if not selected:
            print('No checks executed; this is not a test pass.')
        return int(any(r['status'] != 'passed' for r in report['results']))
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
