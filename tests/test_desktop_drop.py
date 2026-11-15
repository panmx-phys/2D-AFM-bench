"""Native drop payload validation; no GUI or experimental data required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from afm_workbench.__main__ import DesktopBridge


class FolderDropTests(unittest.TestCase):
    def setUp(self):
        self.bridge = DesktopBridge()
        self.bridge._window = Mock()

    def drop(self, files):
        self.bridge._window.reset_mock()
        self.bridge._on_folder_drop({'dataTransfer': {'files': files}})
        script = self.bridge._window.evaluate_js.call_args.args[0]
        return json.loads(script.removeprefix('window.afmImportDrop(').removesuffix(');'))

    def test_directory_path_is_preserved_and_json_encoded(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'Session "quoted" μm'
            folder.mkdir()
            self.assertEqual(self.drop([{'pywebviewFullPath': str(folder)}]),
                             {'path': str(folder)})

    def test_files_and_unavailable_folders_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'image.tiff'
            file.write_bytes(b'original')
            for path in (file, Path(root) / 'missing'):
                self.assertIn('error', self.drop([{'pywebviewFullPath': str(path)}]))
            self.assertEqual(file.read_bytes(), b'original')

    def test_missing_full_path_is_not_inferred_from_filename(self):
        self.assertIn('Use Import folder', self.drop([{'name': 'Session'}])['error'])

    def test_multiple_folders_are_not_silently_combined(self):
        self.assertIn('one session folder', self.drop([{'name': 'one'}, {'name': 'two'}])['error'])

    def test_text_and_internal_drags_are_ignored(self):
        for event in ({}, {'dataTransfer': {'files': []}}):
            self.bridge._on_folder_drop(event)
        self.bridge._window.evaluate_js.assert_not_called()


if __name__ == '__main__':
    unittest.main()
