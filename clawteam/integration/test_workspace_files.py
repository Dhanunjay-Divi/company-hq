from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
import workspace_files
from workspace_files import listing, read, write, draft


class WorkspaceFilesTest(unittest.TestCase):
    def test_file_scope_and_edit_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'; root.mkdir()
            path = root / 'app.py'; path.write_text('old')
            outside = Path(tmp) / 'private'; outside.write_text('unrelated')
            (root / 'link').symlink_to(outside)
            hardlink = root / 'hardlink'; hardlink.hardlink_to(outside)
            (root / '.git').mkdir(); (root / '.git/config').write_text('git')
            self.assertEqual([x['name'] for x in listing(root)['items']], ['app.py'])
            for relative in ('../private', str(outside), 'link', 'hardlink', '.git/config'):
                with self.assertRaises(ValueError): read(root, relative)
            value = read(root, 'app.py'); path.write_text('concurrent')
            with self.assertRaises(ValueError): write(root, 'app.py', 'overwrite', value['revision'])
            value = read(root, 'app.py')
            self.assertEqual(write(root, 'app.py', 'saved', value['revision'])['text'], 'saved')
            self.assertEqual(outside.read_text(), 'unrelated')

    @unittest.skipIf(os.name == 'nt' or not getattr(os, 'O_NOFOLLOW', 0), 'requires openat no-follow traversal')
    def test_parent_swapped_to_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'; folder = root / 'folder'; folder.mkdir(parents=True)
            (folder / 'item.txt').write_text('inside')
            outside = Path(tmp) / 'outside'; outside.mkdir(); (outside / 'item.txt').write_text('outside')
            original = workspace_files._path
            def swap(project, relative=''):
                result = original(project, relative)
                folder.rename(root / 'original-folder')
                folder.symlink_to(outside, target_is_directory=True)
                return result
            with patch('workspace_files._path', side_effect=swap):
                with self.assertRaises((OSError, ValueError)): read(root, 'folder/item.txt')
            self.assertEqual((outside / 'item.txt').read_text(), 'outside')

    def test_drafts_persist_outside_http_origin_and_reject_stale_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            self.assertEqual(draft(state, 'new'), {'text': '', 'revision': 0})
            draft(state, 'new', {'text': 'My idea', 'revision': 0})
            self.assertEqual(draft(state, 'new')['text'], 'My idea')
            with self.assertRaises(ValueError): draft(state, 'new', {'text': 'stale', 'revision': 0})
            self.assertEqual(draft(state, 'another')['text'], '')
            self.assertEqual(draft(state, 'new', {'text': '', 'revision': 1})['revision'], 2)


if __name__ == '__main__': unittest.main()
