"""Release input gates and deterministic, portable distribution archives."""
import gzip
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from scripts import build_gwyddion, release_macos, release_windows, source_release
from scripts import test as runner


class ReleaseTests(unittest.TestCase):
    def test_windows_dll_closure_stages_transitive_dependencies_and_rejects_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle, prefix = root/'bundle', root/'prefix'
            bundle.mkdir(); prefix.mkdir()
            (bundle/'adapter.dll').write_bytes(b'adapter')
            (prefix/'dependency.dll').write_bytes(b'dependency')
            (prefix/'transitive.dll').write_bytes(b'transitive')
            imports = {'adapter.dll': 'dependency.dll', 'dependency.dll': 'transitive.dll', 'transitive.dll': 'api-ms-win-core-libraryloader-l1-2-0.dll'}
            def headers(command, **kwargs):
                return 'file format pei-x86-64\nDLL Name: '+imports[Path(command[-1]).name]
            with patch.object(build_gwyddion.subprocess, 'check_output', side_effect=headers):
                build_gwyddion.bundle_windows(bundle, [prefix])
                self.assertEqual((bundle/'transitive.dll').read_bytes(), b'transitive')
                imports['transitive.dll'] = 'missing-afm-test-dependency.dll'
                with self.assertRaisesRegex(RuntimeError, 'Unresolved DLL'):
                    build_gwyddion.bundle_windows(bundle, [prefix])

    def test_windows_zip_is_deterministic_and_preserves_application_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root/'AFM Workbench'
            (app/'_internal').mkdir(parents=True)
            (app/'AFM Workbench.exe').write_bytes(b'exe')
            dll = app/'_internal/backend.dll'
            dll.write_bytes(b'dll')
            a, b = root/'a.zip', root/'b.zip'
            release_windows.deterministic_zip(a, app, 1234567890)
            os.utime(dll, (123, 123))
            release_windows.deterministic_zip(b, app, 1234567890)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as archive:
                self.assertEqual(archive.read('AFM Workbench/_internal/backend.dll'), b'dll')

    def test_windows_cleanup_rejects_source_and_checkout_root(self):
        for path in (release_windows.ROOT, release_windows.ROOT/'afm_workbench', release_windows.WORK):
            with self.assertRaisesRegex(RuntimeError, 'Refusing cleanup'):
                release_windows.remove_generated(path)

    def test_tag_version_commit_and_clean_tree_are_required(self):
        release_macos.validate_tag('v1.2.3', '1.2.3', 'abc', 'abc', False)
        for tag, target, dirty in [('v9.9.9', 'abc', False), ('v1.2.3', 'def', False),
                                   ('v1.2.3', 'abc', True), ('v1.2.3;echo bad', 'abc', False)]:
            with self.subTest(tag=tag, target=target, dirty=dirty), self.assertRaises(RuntimeError):
                release_macos.validate_tag(tag, '1.2.3', 'abc', target, dirty)

    def test_project_and_runtime_version_must_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'afm_workbench').mkdir()
            (root / 'pyproject.toml').write_text('[project]\nversion="1.2.3"\n')
            init = root / 'afm_workbench/__init__.py'
            init.write_text('__version__ = "1.2.3"\n')
            with patch.object(release_macos, 'ROOT', root):
                self.assertEqual(release_macos.version(), '1.2.3')
                init.write_text('__version__ = "1.2.4"\n')
                with self.assertRaisesRegex(RuntimeError, 'matching'):
                    release_macos.version()

    def test_archive_bytes_ignore_checkout_mtime_order_and_output_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'Example.app'
            app.mkdir()
            exe = app / 'executable'
            exe.write_bytes(b'executable')
            exe.chmod(0o755)
            (app / 'alias').symlink_to('executable')
            entries = [(p, 'Example.app/' + p.name) for p in app.iterdir()]
            a, b = root / 'a.tar.gz', root / 'different-name.tar.gz'
            source_release.deterministic_archive(a, entries, 1234567890)
            os.utime(exe, (123, 123))
            source_release.deterministic_archive(b, list(reversed(entries)), 1234567890)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with tarfile.open(a) as archive:
                for member in archive:
                    self.assertEqual(member.mtime, 1234567890)
                    self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, '', ''))
                expected_mode = 0o755 if exe.stat().st_mode & 0o111 else 0o644
                self.assertEqual(archive.getmember('Example.app/executable').mode, expected_mode)
                self.assertTrue(archive.getmember('Example.app/alias').issym())
                extracted = root / 'extracted'
                archive.extractall(extracted, filter='data')
            self.assertEqual((extracted / 'Example.app/alias').read_bytes(), b'executable')
            self.assertTrue(gzip.decompress(a.read_bytes()))

    def test_checksum_mismatch_rejected_before_package_extraction(self):
        from scripts.collect_native_sources import acquire
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            (cache / 'input.conda').write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'):
                acquire({'url': 'https://example.invalid/input.conda', 'sha256': '0' * 64}, cache, False)

    def test_release_inputs_select_release_packaging_and_runtime_checks(self):
        catalog = runner.load_catalog()
        for path in ['release/macos-arm64.lock', '.github/workflows/release.yml',
                     'scripts/release_macos.py', 'native/dependencies-macos-arm64.json']:
            selected = runner.select_changed(catalog, [path])
            for check in ('release', 'packaging', 'runtime'):
                with self.subTest(path=path, check=check):
                    self.assertIn(check, selected)

    def test_all_python_inputs_are_exact_and_hash_locked(self):
        for lock in release_macos.LOCKS:
            for line in lock.read_text().splitlines():
                if line and not line.startswith('#'):
                    self.assertRegex(line, r'^[\w-]+==[\w.]+ --hash=sha256:[0-9a-f]{64}$')
        config = json.loads(release_macos.CONFIG.read_text())
        workflow = (release_macos.ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn('runs-on: ' + config['runner'], workflow)
        self.assertIn("python-version: '" + config['bootstrap_python'] + "'", workflow)

    def test_public_report_does_not_expose_build_machine_paths(self):
        report = {'results': [{'id': 'runtime', 'kind': 'runtime', 'status': 'passed',
                               'target': '/Users/private/dist/app', 'log': '/Users/private/log'}],
                  'deferred': ['canvas'], 'inactive': ['legacy-ui']}
        public = release_macos.summarize_report(report)
        self.assertNotIn('/Users', json.dumps(public))
        self.assertEqual(public['results'][0]['status'], 'passed')
        self.assertEqual(public['deferred'], ['canvas'])

    def test_bundle_inspection_rejects_host_libraries_and_records_deployment_floor(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder)
            (app / 'binary').write_bytes(bytes.fromhex('cffaedfe'))
            def otool(*args):
                if '-l' in args:
                    return 'cmd LC_BUILD_VERSION\n minos 14.0\n sdk 15.0'
                return 'binary:\n\t@loader_path/liblocal.dylib (compatibility version 1.0)'
            with patch.object(release_macos, 'run'), patch.object(release_macos, 'output', side_effect=otool):
                self.assertEqual(release_macos.inspect_bundle(app)['minimum_macos'], '14.0.0')
            with patch.object(release_macos, 'run'), patch.object(release_macos, 'output', return_value=
                    'binary:\n\t/opt/homebrew/lib/libforeign.dylib (compatibility version 1.0)'):
                with self.assertRaisesRegex(RuntimeError, 'External library'):
                    release_macos.inspect_bundle(app)


if __name__ == '__main__':
    unittest.main()
