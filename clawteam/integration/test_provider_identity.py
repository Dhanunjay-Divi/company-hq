"""Identity and private-attachment guards for native provider adapters."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import kimi_runtime
import runtime_config
import zcode_runtime
from kimi_runtime import KimiRuntime
from provider_runtime import ProviderRuntimeError
from zcode_runtime import ZCodeRuntime


class Rpc:
    def __init__(self, command=None, project=None, callback=None, **_):
        self.callback = callback
        self.replies, self.rejections = [], []
        self.responses = {}

    def request(self, method, params, timeout=25):
        value = self.responses.get(method, {})
        return value(params) if callable(value) else value

    def reply(self, ident, result): self.replies.append((ident, result))
    def reject(self, ident): self.rejections.append(ident)
    def notify(self, method, params): pass
    def close(self): pass


def kimi_session(session_id):
    return {'sessionId': session_id, 'configOptions': [{'id': 'model', 'currentValue': 'kimi', 'options': [{'value': 'kimi'}]}]}


def zcode_session(session_id):
    return {'session': {'sessionId': session_id}, 'settings': {'model': {'current': {'providerId': 'zai', 'modelId': 'glm'}, 'available': [{'ref': {'providerId': 'zai', 'modelId': 'glm'}, 'properties': {'inputFormat': {'supportsImage': True}}}]}, 'mode': {'current': 'build'}}}


class ProviderIdentityTest(unittest.TestCase):
    def test_kimi_resume_and_permission_require_exact_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            rpc = Rpc()
            rpc.responses = {'initialize': {'agentCapabilities': {}}, 'authenticate': {}, 'session/load': kimi_session('other-session')}
            with patch.object(kimi_runtime, 'kimi_binary', return_value='/fixture/kimi'):
                runtime = KimiRuntime(session_id='expected-session', rpc_factory=lambda *args: rpc)
                with self.assertRaisesRegex(ProviderRuntimeError, 'resumed a different session'):
                    runtime.initialize(project=temporary)
            runtime = KimiRuntime(session_id='expected-session')
            runtime.rpc, runtime._state = rpc, 'running'
            runtime._handle({'id': 1, 'method': 'session/request_permission', 'params': {}})
            self.assertEqual(rpc.rejections, [1])
            runtime._handle({'id': 2, 'method': 'session/request_permission', 'params': {'sessionId': 'expected-session', 'toolCall': {}}})
            self.assertEqual(len(runtime.pending), 1)
            runtime._handle({'method': 'session/update', 'params': {'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'text': 'unbound'}}}})
            self.assertEqual([event['type'] for event in runtime.events()['events']], ['approval.requested'])

    def test_zcode_resume_and_interactive_requests_require_exact_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry = Path(temporary) / 'zcode.cjs'; entry.write_text('// fixture')
            rpc = Rpc(); rpc.responses = {'session/resume': zcode_session('other-session')}
            runtime = ZCodeRuntime(session_id='expected-session', rpc_factory=lambda *args, **kwargs: rpc)
            with patch.object(zcode_runtime, 'zcode_command', return_value=['node', str(entry)]), patch.object(zcode_runtime, 'runtime_env', return_value={}), patch.object(zcode_runtime, 'PIN', hashlib.sha256(entry.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(ProviderRuntimeError, 'resumed a different session'):
                    runtime.initialize(project=temporary)
            runtime = ZCodeRuntime(session_id='expected-session'); runtime.rpc = rpc
            runtime._handle({'id': 'prefs', 'method': 'session/requestRuntimePreferences', 'params': {}})
            self.assertEqual(rpc.replies[-1][0], 'prefs')
            runtime._handle({'id': 'permission', 'method': 'interaction/requestPermission', 'params': {}})
            runtime._handle({'id': 'question', 'method': 'interaction/requestUserInput', 'params': {}})
            self.assertEqual(rpc.rejections[-2:], ['permission', 'question'])

    def test_zcode_image_staging_is_private_session_scoped_and_capped(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / 'state'
            runtime = ZCodeRuntime(session_id='zai-session')
            with patch.object(runtime_config, 'state_root', return_value=state):
                folder = runtime._attachment_folder()
            self.assertEqual(folder.parent, state / 'provider-attachments')
            self.assertEqual(folder.name, hashlib.sha256(b'zai-session').hexdigest())
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            runtime.rpc, runtime._state = Rpc(), 'idle'
            runtime.catalog = {'zai/glm': {'properties': {'inputFormat': {'supportsImage': True}}}}
            runtime.model = 'zai/glm'
            image = {'mimeType': 'image/png', 'data': base64.b64encode(b'fixture').decode()}
            with patch.object(runtime_config, 'state_root', return_value=state), patch.object(zcode_runtime, 'MAX_SESSION_ATTACHMENTS', 0):
                with self.assertRaisesRegex(ProviderRuntimeError, 'attachment limit'):
                    runtime.send('image', images=[image])


if __name__ == '__main__':
    unittest.main()
