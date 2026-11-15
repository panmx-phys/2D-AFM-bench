"""Regression checks for decisions that can otherwise silently omit test coverage."""
import argparse
from contextlib import contextmanager, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import test as runner


class TestSelectionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = runner.load_catalog()

    def selection(self, *paths):
        return runner.select_changed(self.catalog, paths)

    def test_catalog_covers_every_check_and_rejects_drift_and_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tests').mkdir()
            data = {'checks': [], 'no_test_changes': []}
            manifest = root / 'tests/catalog.json'
            manifest.write_text(json.dumps(data))
            runner.load_catalog(root)
            (root / 'tests/test_new.py').touch()
            with self.assertRaisesRegex(ValueError, 'uncataloged'):
                runner.load_catalog(root)
            entry = dict(id='new', path='tests/test_new.py', status='active', kind='unit',
                         groups=['tooling'], purpose='Example')
            data['checks'] = [entry, entry]
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                runner.load_catalog(root)

    def test_canvas_change_does_not_run_unrelated_numerical_suites(self):
        selected = self.selection('afm_workbench/static/canvas-controls.js')
        self.assertIn('canvas', selected)
        self.assertIn('fluidity', selected)
        self.assertNotIn('science', selected)
        self.assertNotIn('importers', selected)

    def test_shared_fixture_selects_consumers(self):
        selected = self.selection('tests/test_importers.py')
        for name in ('importers', 'service', 'characterization', 'canvas', 'folder-drop-ui', 'folders-ui'):
            self.assertIn(name, selected)
        self.assertNotIn('line-alignment', selected)

    def test_indirect_scientific_and_native_changes_include_integration_consumers(self):
        for path in ('afm_workbench/native_backend.py', 'afm_workbench/leveling.py'):
            selected = self.selection(path)
            for name in ('science', 'service', 'masks-display', 'characterization'):
                self.assertIn(name, selected, (path, name))
        self.assertIn('native-backend', self.selection('native/afm_gwyddion.c'))
        self.assertIn('service', self.selection('native/afm_gwyddion.c'))
        self.assertIn('runtime', self.selection('native/afm_gwyddion.c'))

    def test_new_unmapped_code_selects_every_active_check(self):
        selected = self.selection('afm_workbench/new_feature.py')
        active = {c['id'] for c in self.catalog['checks'] if c['status'] == 'active'}
        self.assertTrue(active <= selected.keys())
        self.assertTrue(all('unmapped change' in selected[name][0] for name in active))

    def test_test_only_and_documentation_changes_stay_focused(self):
        self.assertEqual(set(self.selection('tests/test_performance.py')), {'performance'})
        self.assertEqual(self.selection('README.md', 'docs/testing.md', 'native/README.md'), {})
        self.assertEqual(set(self.selection('tests/catalog.json')), {'test-runner'})

    def test_deleted_implementation_is_conservative(self):
        self.assertIn('science', self.selection('afm_workbench/deleted_module.py'))

    def test_legacy_wildcards_do_not_hide_unmapped_frontend_code(self):
        selected = self.selection('afm_workbench/static/new-feature.js')
        active = {c['id'] for c in self.catalog['checks'] if c['status'] == 'active'}
        self.assertTrue(active <= selected.keys())

    def test_git_scope_includes_index_worktree_untracked_and_rename_sides(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / 'nested project'
            project.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT)
            git('init', '-q')
            for name in ('staged.py', 'unstaged.py', 'old.py'):
                (project / name).write_text('old\n')
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline')
            (project / 'staged.py').write_text('new\n')
            git('add', 'nested project/staged.py')
            (project / 'unstaged.py').write_text('new\n')
            (project / 'untracked name.py').touch()
            git('mv', 'nested project/old.py', 'nested project/new.py')
            (root / 'unrelated.py').touch()
            self.assertEqual(set(runner.changed_paths(project)), {
                'staged.py', 'unstaged.py', 'old.py', 'new.py', 'untracked name.py'})
            with self.assertRaises(subprocess.CalledProcessError), redirect_stdout(io.StringIO()):
                runner.changed_paths(project, 'missing-revision')

    def test_kind_filter_reports_deferred_and_legacy_never_count_as_active(self):
        reasons = {'canvas': ['example'], 'science': ['example'], 'legacy-ui': ['example']}
        output = io.StringIO()
        with redirect_stdout(output):
            selected = runner.print_plan(self.catalog, reasons, ['unit'])
        self.assertEqual([c['id'] for c in selected], ['science'])
        self.assertIn('deferred', output.getvalue())
        self.assertIn('legacy', output.getvalue())


class RunnerOutcomeTests(unittest.TestCase):
    def test_windows_workspace_cleanup_retries_locks_but_reports_persistent_failure(self):
        with patch.object(runner.sys, 'platform', 'win32'), \
                patch.object(runner.tempfile, 'TemporaryDirectory') as temporary, \
                patch.object(runner.time, 'sleep') as pause:
            workspace = temporary.return_value
            workspace.name = 'test-workspace'
            workspace.cleanup.side_effect = [PermissionError('DLL locked'), None]
            with runner.temporary_workspace() as name:
                self.assertEqual(name, workspace.name)
            self.assertEqual(workspace.cleanup.call_count, 2)
            pause.assert_called_once_with(.1)
            workspace.cleanup.reset_mock()
            workspace.cleanup.side_effect = PermissionError('still locked')
            with self.assertRaisesRegex(PermissionError, 'still locked'):
                with runner.temporary_workspace():
                    pass
            self.assertEqual(workspace.cleanup.call_count, 50)

    def test_windows_server_stops_child_tree_and_preserves_smoke_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(runner.sys, 'platform', 'win32'), \
                    patch.object(runner.subprocess, 'Popen') as start, \
                    patch.object(runner.subprocess, 'run') as stop:
                process = start.return_value
                process.pid = 12345
                process.poll.return_value = None
                def launch(command, **kwargs):
                    ready = Path(command[command.index('--ready-file')+1])
                    self.assertEqual(kwargs['env']['TEMP'], str(ready.parent))
                    ready.write_text('http://127.0.0.1:1234/', encoding='utf-8')
                    return process
                start.side_effect = launch
                with self.assertRaisesRegex(RuntimeError, 'smoke failed'):
                    with runner.server(root, root, 'example', root/'portable.exe') as url:
                        self.assertEqual(url, 'http://127.0.0.1:1234/')
                        raise RuntimeError('smoke failed')
                self.assertEqual(stop.call_args.args[0], ['taskkill', '/PID', '12345', '/T', '/F'])
                process.wait.assert_called_once_with(timeout=5)

    def run_example(self, check, **patches):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = argparse.Namespace(bundle=None, node='node', browser=None, timeout=1)
            cleanup_error = patches.pop('cleanup_error', None)
            @contextmanager
            def fake_server(*args):
                yield 'http://127.0.0.1:1/'
                if cleanup_error:
                    raise cleanup_error
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'server', fake_server), \
                    redirect_stdout(io.StringIO()):
                if check['kind'] == 'unit':
                    with patch.object(unittest.defaultTestLoader, 'loadTestsFromName', return_value=patches['suite']):
                        return runner.run_check(check, args, root)
                with patch.object(runner.subprocess, 'run', **patches):
                    return runner.run_check(check, args, root)

    def test_nonzero_smoke_exit_is_a_failure(self):
        result = self.run_example(dict(id='example', kind='runtime', path='example.py'),
                                  return_value=subprocess.CompletedProcess([], 7))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['exit_code'], 7)

    def test_cleanup_failure_overrides_successful_smoke_exit(self):
        result = self.run_example(dict(id='example', kind='runtime', path='example.py'),
                                  return_value=subprocess.CompletedProcess([], 0),
                                  cleanup_error=PermissionError('DLL locked'))
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error'], 'DLL locked')

    def test_missing_dependency_and_timeout_are_failures(self):
        for error in (FileNotFoundError('node'), subprocess.TimeoutExpired(['node'], 1)):
            result = self.run_example(dict(id='example', kind='browser', path='example.cjs'), side_effect=error)
            self.assertEqual(result['status'], 'failed')
            self.assertIn('error', result)

    def test_skips_and_empty_suites_are_not_passes(self):
        @unittest.skip('environment prerequisite unavailable')
        def skipped():
            pass
        suite = unittest.TestSuite([unittest.FunctionTestCase(skipped)])
        check = dict(id='example', kind='unit', path='example.py')
        result = self.run_example(check, suite=suite)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['skipped'], 1)
        result = self.run_example(check, suite=unittest.TestSuite())
        self.assertEqual(result['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
