from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hq_api
from chat_management import ChatManagement, reveal_bound_folder
from transcript_archive import TranscriptArchive


class Handler:
    def __init__(self, path=''):
        self.path, self.response, self.error = path, None, None
    def _serve_json(self, value): self.response = value
    def _json_error(self, status, message): self.error = (status, message)


class ChatManagementTest(unittest.TestCase):
    def test_native_export_saves_private_file_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary, patch('chat_management.platform.system',return_value='Darwin'), patch('chat_management.subprocess.run') as reveal:
            manager=ChatManagement(Path(temporary))
            first=manager.save_export('chat-one','markdown');second=manager.save_export('chat-one','markdown')
            self.assertNotEqual(first['savedPath'],second['savedPath'])
            self.assertEqual(Path(first['savedPath']).read_text(),first['content'])
            self.assertEqual(Path(first['savedPath']).stat().st_mode & 0o777,0o600)
            self.assertTrue(first['revealed'])
            self.assertEqual(reveal.call_count,2)
    def test_export_uses_full_durable_archive_and_trash_is_recoverable(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            archive = TranscriptArchive(state / 'runtime')
            for seq in range(1, 141):
                archive.record('chat-one', {'seq': seq, 'type': 'message.user' if seq % 2 else 'message.completed', 'data': {'text': f'message {seq}'}})
            manager = ChatManagement(state)
            manager.delete('chat-one')
            self.assertEqual(manager.deleted(), {'chat-one'})
            exported = manager.export('chat-one', 'markdown')
            self.assertIn('message 1', exported['content'])
            self.assertIn('message 140', exported['content'])
            manager.restore('chat-one')
            self.assertFalse(manager.deleted())

    def test_reveal_only_opens_exact_managed_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); folder = state / 'managed-workspaces' / 'chat-one'; folder.mkdir(parents=True)
            with patch('chat_management.platform.system', return_value='Darwin'), patch('chat_management.subprocess.run') as opened:
                self.assertEqual(reveal_bound_folder(state, 'chat-one', {'projectRoot': str(folder), 'workspaceKind': 'managed'}), str(folder.resolve()))
                opened.assert_called_once_with(['/usr/bin/open', str(folder.resolve())], check=True, timeout=10, shell=False, stdout=-3, stderr=-3)
            with self.assertRaisesRegex(ValueError, 'binding'):
                reveal_bound_folder(state, 'chat-one', {'projectRoot': str(state), 'workspaceKind': 'managed'})

    def test_deleted_chat_cannot_send_and_active_chat_cannot_be_deleted(self):
        class Team: members = []
        class Bridge:
            def status(self, team): return {'state': 'running', 'pendingApprovals': []}
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); manager = ChatManagement(state); manager.delete('chat-one')
            handler = Handler()
            with patch.object(hq_api.TeamManager, 'get_team', return_value=Team()), patch('hq_api.bridge', return_value=Bridge()):
                hq_api.handle_post(handler, state, '/api/workspaces/chat-one/chat/delete', {})
            self.assertEqual(handler.error[0], 400)
            self.assertIn('Stop runtime work', handler.error[1])
            handler = Handler()
            with patch('hq_api.project_for', return_value=str(state)):
                hq_api.handle_post(handler, state, '/api/runtime/chat-one/send', {'prompt': 'hello'})
            self.assertEqual(handler.error[0], 400)
            self.assertIn('Restore it', handler.error[1])

    def test_management_get_route_reports_deleted_chats(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); ChatManagement(state).delete('chat-one')
            handler = Handler('/api/workspaces/chat-management')
            self.assertTrue(hq_api.handle_get(handler, state))
            self.assertEqual(handler.response, {'deleted': ['chat-one']})
