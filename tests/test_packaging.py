"""Public archive privacy and missing-notice packaging gates."""
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import package_notices, source_release
from scripts import test as runner


class PackagingTests(unittest.TestCase):
    def test_upstream_notice_changes_select_packaging_checks(self):
        selected = runner.select_changed(runner.load_catalog(), ['licenses/python-fallbacks/manifest.json'])
        self.assertIn('packaging', selected)

    def test_tar_roundtrip_removes_account_metadata_including_pax_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'source.txt'
            source.write_text('public source')
            archive = root/'release.tar.gz'
            with tarfile.open(archive, 'w:gz') as output:
                member = output.gettarinfo(source, arcname='Workbench/source.txt')
                member.uid, member.gid = 501, 20
                member.uname, member.gname = 'private-account', 'private-group'
                member.pax_headers.update(uname='private-account', uid='501')
                with source.open('rb') as stream:
                    output.addfile(source_release.public_tar_metadata(member), stream)
            with tarfile.open(archive) as packed:
                member = packed.getmember('Workbench/source.txt')
                self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, '', ''))
                self.assertEqual(packed.extractfile(member).read(), b'public source')

    def test_missing_distribution_notice_stops_packaging(self):
        class NoNotice:
            files = []
            version = '99.0'
            metadata = {'Name': 'example'}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(package_notices, 'distribution_names', return_value=['example']), \
                    patch.object(package_notices.metadata, 'distribution', return_value=NoNotice()):
                with self.assertRaisesRegex(RuntimeError, 'No license notice for example 99.0'):
                    package_notices.collect_notices([], Path(__file__).resolve().parents[1], folder)

    def test_distribution_mapping_uses_collected_paths_not_all_installed_packages(self):
        with patch.object(package_notices.metadata, 'packages_distributions', return_value={
                'used': ['used-dist'], 'unused': ['unused-dist']}):
            result = package_notices.distribution_names([
                ('used', '/example/site-packages/used/__init__.py', 'PYMODULE'),
                ('json', '/example/lib/python3.12/json/__init__.py', 'PYMODULE')])
        self.assertEqual(result, ['pyinstaller', 'used-dist'])


if __name__ == '__main__':
    unittest.main()
