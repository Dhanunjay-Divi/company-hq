from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import hq_api
from provider_connections import CodexSignIn, ProviderConnections
from test_provider_connections import FakeConnection


class Handler:
    def __init__(self, path=''):
        self.path, self.response, self.error = path, None, None
    def _serve_json(self, value): self.response = value
    def _json_error(self, status, message): self.error = status, message


class NativeTaskAPITest(unittest.TestCase):
    def test_read_only_transport_has_no_turn_or_resume_calls(self):
        transport = FakeConnection({'thread/list': {'data': []}, 'thread/read': {'thread': {'id': 'safe-id'}}})
        auth = CodexSignIn(factory=lambda: transport)
        self.assertEqual(auth.list_tasks()['tasks'], [])
        self.assertEqual(auth.read_task('safe-id')['task']['id'], 'safe-id')
        self.assertEqual([x['method'] for x in transport.sent], ['initialize', 'initialized', 'thread/list', 'thread/read'])
        auth.close()

    def test_demo_never_opens_transport(self):
        auth = Mock()
        service = ProviderConnections(auth)
        with patch('provider_connections.demo_mode', return_value=True):
            with self.assertRaises(ValueError): service.list_tasks()
            with self.assertRaises(ValueError): service.read_task('id')
        self.assertEqual(auth.mock_calls, [])

    def test_list_filters_detail_and_generic_errors(self):
        service = Mock()
        service.list_tasks.return_value = {'tasks': [], 'readOnly': True}
        service.read_task.return_value = {'task': {'id': 'safe-id', 'summary': ''}}
        with patch('provider_connections.connections', return_value=service):
            h = Handler('/api/providers/codex/tasks?cursor=a&search=hello&archived=true&includeAgents=false')
            self.assertTrue(hq_api.handle_get(h, Path('/tmp')))
            service.list_tasks.assert_called_once_with(cursor='a', search='hello', archived=True, include_agents=False)
            h = Handler('/api/providers/codex/tasks/safe-id')
            hq_api.handle_get(h, Path('/tmp'))
            service.read_task.assert_called_once_with('safe-id')
            for path in ('tasks?archived=yes', 'tasks?search=a&search=b', 'tasks?raw=true', 'tasks/id?raw=true', 'tasks-extra'):
                h = Handler('/api/providers/codex/' + path)
                hq_api.handle_get(h, Path('/tmp'))
                self.assertEqual(h.error[0], 400)
            service.list_tasks.side_effect = RuntimeError('/private/secret')
            h = Handler('/api/providers/codex/tasks')
            hq_api.handle_get(h, Path('/tmp'))
            self.assertNotIn('secret', h.error[1])

    def test_settings_demo_block_and_response_binding(self):
        service = Mock()
        with patch('hq_api.demo_mode', return_value=True), patch('access_settings.open_settings') as opening:
            h = Handler()
            hq_api.handle_post(h, Path('/tmp'), '/api/access/settings', {'pane': 'accessibility'})
            self.assertEqual(h.error[0], 400)
            opening.assert_not_called()
        with patch('hq_api.demo_mode', return_value=False), patch('hq_api.project_for'), patch('hq_api.bridge', return_value=service):
            h = Handler()
            response = {'answers': {'q': {'answers': ['Choice']}}}
            hq_api.handle_post(h, Path('/tmp'), '/api/runtime/team/respond', {'requestId': 'r', 'response': response})
            service.respond.assert_called_once_with('team', 'r', response)
            hq_api.handle_post(h, Path('/tmp'), '/api/runtime/team/respond', {'requestId': 'r', 'response': response, 'extra': True})
            self.assertEqual(h.error[0], 400)
