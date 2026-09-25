"""Fixture tests for the ZCode app-server runtime; no live CLI, network, or account access."""
from __future__ import annotations

import base64
import contextlib
import hashlib
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import runtime_config
import zcode_runtime
from provider_runtime import ProviderRuntimeError
from zcode_runtime import ZCodeRuntime

PNG_BYTES = b'fixture-png-bytes'
PNG_B64 = base64.b64encode(PNG_BYTES).decode('ascii')
VALID_IMAGE = {'mimeType': 'image/png', 'data': PNG_B64}

ZCODE_MODELS = [
    {'ref': {'providerId': 'zai', 'modelId': 'glm-4.7'}, 'label': 'GLM 4.7', 'properties': {'inputFormat': {'supportsImage': True}}},
    {'ref': {'providerId': 'zai', 'modelId': 'glm-4.7-air'}, 'label': 'GLM 4.7 Air', 'properties': {'inputFormat': {'supportsImage': False}}},
]

READ_BASELINE = {'messages': [], 'projection': {'turnCount': 0}}
READ_COMPLETED = {
    'messages': [{'info': {'messageId': 'assistant-1', 'role': 'assistant'}, 'parts': [{'type': 'text', 'text': 'Fixture answer'}]}],
    'projection': {'status': 'completed', 'currentTurnId': None, 'turnCount': 1},
}
READ_RUNNING = {'messages': [], 'projection': {'status': 'running', 'currentTurnId': 'native-turn', 'turnCount': 1}}


def create_result(session_id, current='glm-4.7'):
    return {
        'session': {'sessionId': session_id},
        'settings': {
            'model': {'current': {'providerId': 'zai', 'modelId': current}, 'available': ZCODE_MODELS},
            'mode': {'current': 'build'},
        },
    }


def wait_for(predicate, timeout=5.0, message='fixture condition not met'):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(message)


def find_event(runtime, type_):
    matches = [event for event in runtime.events()['events'] if event['type'] == type_]
    return matches[0] if matches else None


class FakeZcodeRpc:
    """Scripted newline-RPC double for the zcode dialect; records every outbound frame."""

    def __init__(self, command, project, handle, **kwargs):
        self.command, self.project, self.handle, self.kwargs = command, project, handle, kwargs
        self.requests, self.notifies, self.replies, self.rejections = [], [], [], []
        self.scripts, self.gates, self.counts = {}, {}, {}
        self.closed = False
        self.scripts.update({
            'session/create': create_result('zai-session-1'),
            'session/setMode': {'settings': {'mode': {'current': 'build'}}},
            'session/read': [READ_BASELINE, READ_COMPLETED],
            'session/send': {},
            'session/usage': {'inputTokens': 7},
        })

    def script(self, method, value):
        self.scripts[method] = value

    def gate(self, method):
        self.gates.setdefault(method, threading.Event())

    def release(self, method):
        self.gates[method].set()

    def _value(self, method, params):
        index = self.counts.get(method, 0)
        self.counts[method] = index + 1
        value = self.scripts.get(method)
        if isinstance(value, list):
            return value[min(index, len(value) - 1)]
        if callable(value):
            return value(index, params)
        return {} if value is None else value

    def request(self, method, params, timeout=25):
        self.requests.append((method, params))
        gate = self.gates.get(method)
        if gate is not None and not gate.is_set():
            if not gate.wait(timeout=10):
                raise ProviderRuntimeError('fixture gate timed out: ' + method)
        value = self._value(method, params)
        if isinstance(value, Exception):
            raise value
        return value

    def notify(self, method, params):
        self.notifies.append((method, params))

    def reply(self, ident, result):
        self.replies.append((ident, result))

    def reject(self, ident):
        self.rejections.append(ident)

    def close(self):
        self.closed = True

    def push(self, row):
        self.handle(row)


class FactoryLog:
    def __init__(self):
        self.rpcs = []

    @property
    def last(self):
        return self.rpcs[-1]


def make_factory(log, scripts=None):
    def factory(command, project, handle, **kwargs):
        rpc = FakeZcodeRpc(command, project, handle, **kwargs)
        for method, value in (scripts or {}).items():
            rpc.script(method, value)
        log.rpcs.append(rpc)
        return rpc
    return factory


@contextlib.contextmanager
def patched_zcode(entry, *, pin=True):
    with patch.object(zcode_runtime, 'zcode_command', return_value=['/usr/bin/fixture-node', str(entry)]), \
         patch.object(zcode_runtime, 'runtime_env', return_value={'ZCODE_FIXTURE_ENV': '1'}):
        if pin:
            with patch.object(zcode_runtime, 'PIN', hashlib.sha256(entry.read_bytes()).hexdigest()):
                yield
        else:
            yield


class ZCodeRuntimeTest(unittest.TestCase):
    def test_shared_mcp_receives_provider_context_on_initialize_and_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = self.entry_file(tmp)
            team = object()
            calls = []
            expected_servers = [{'name': 'contextMCP', 'transport': 'stdio'}]
            def servers(project, *, team=None, access=None):
                calls.append((project, team, access))
                return expected_servers
            log = FactoryLog()
            runtime = ZCodeRuntime(rpc_factory=make_factory(log), shared_tools=True)
            runtime.context_team = team
            with patched_zcode(entry), patch.dict('sys.modules', {'shared_tools': types.SimpleNamespace(servers=servers)}):
                runtime.initialize(project=str(tmp))
                rpc = log.last
                rpc.script('mcp/list', {'statuses': {'contextMCP': {'status':'connected', 'toolCount':3}}})
                self.assertEqual([params for method, params in rpc.requests if method == 'session/create'][0]['mcpServers'], expected_servers)
                result=runtime.tools()
            self.addCleanup(runtime.stop)
            self.assertEqual(calls, [(str(Path(tmp).resolve()), team, 'workspace'), (str(Path(tmp).resolve()), team, 'workspace')])
            inventory = [params for method, params in rpc.requests if method == 'mcp/list'][0]
            self.assertEqual(inventory['mcpServers'], expected_servers)
            self.assertEqual(inventory['mode'], 'connect')
            self.assertEqual(result['inventoryScope'], 'workspace')
            self.assertEqual(result['servers'][0]['runtimeStatus'], 'connected')
            self.assertEqual(result['servers'][0]['toolCount'], 3)

    def test_retained_projection_turn_is_not_a_running_native_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            result={**READ_COMPLETED, 'runtime':{'stateRevision':5, 'pendingRequestIds':[]}, 'projection':{'status':'idle','currentTurnId':'retained-turn','turnCount':1,'activeToolCalls':[]}}
            runtime,log,_=self.connect(tmp,scripts={'session/read':[{'messages':[], 'projection':{'turnCount':1}},result]})
            runtime.send('finish')
            wait_for(lambda:find_event(runtime,'message.completed'))
            self.assertEqual(runtime.status()['state'],'idle')

    def test_probe_rejects_an_unreviewed_bundle_before_native_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / 'zcode.cjs'
            entry.write_text('fixture bundle')
            with patch.object(zcode_runtime, 'zcode_command', return_value=['node', str(entry)]):
                result = zcode_runtime.probe()
            self.assertTrue(result['installed'])
            self.assertFalse(result['runtimeReady'])
            self.assertFalse(result['checksumVerified'])
            self.assertFalse(result['authenticated'])
            self.assertEqual(result['models'], [])
            self.assertIn('compatibility review', result['message'])

    def entry_file(self, tmp):
        entry = Path(tmp) / 'zcode.cjs'
        entry.write_text('// fixture app-server entry\n')
        return entry

    def connect(self, tmp, *, scripts=None, session_id=None, model=None):
        entry = self.entry_file(tmp)
        scripts = dict(scripts or {})
        if session_id:
            scripts.setdefault('session/resume', create_result(session_id))
        log = FactoryLog()
        runtime = ZCodeRuntime(session_id=session_id, model=model, rpc_factory=make_factory(log, scripts))
        with patched_zcode(entry):
            result = runtime.initialize(project=str(tmp))
        self.addCleanup(runtime.stop)
        return runtime, log, result

    def test_entry_hash_pin_blocks_unreviewed_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = self.entry_file(tmp)
            log = FactoryLog()
            runtime = ZCodeRuntime(rpc_factory=make_factory(log))
            with patched_zcode(entry, pin=False), self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.initialize(project=str(tmp))
            self.assertEqual(str(ctx.exception), 'ZCode was updated. Its execution adapter needs a compatibility review.')
            self.assertEqual(log.rpcs, [])
            self.assertEqual(runtime.status()['state'], 'offline')

    def test_initialize_rejects_unreported_model_and_binds_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            second = Path(tmp) / 'second'
            second.mkdir()
            entry = self.entry_file(tmp)
            log = FactoryLog()
            runtime = ZCodeRuntime(model='zai/glm-ultra', rpc_factory=make_factory(log))
            with patched_zcode(entry), self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.initialize(project=str(tmp))
            self.assertEqual(str(ctx.exception), 'Select a model reported by ZCode')
            rpc = log.last
            self.assertTrue(rpc.closed)
            standalone = str(Path(zcode_runtime.__file__).with_name('zcode_standalone.cjs'))
            self.assertEqual(rpc.command, ['/usr/bin/fixture-node', standalone, str(entry), 'app-server'])
            self.assertEqual(rpc.kwargs, {'dialect': 'zcode', 'env': {'ZCODE_FIXTURE_ENV': '1'}})
            self.assertEqual(rpc.project, str(Path(tmp).resolve()))
            requested = [method for method, _ in rpc.requests]
            self.assertIn('session/create', requested)
            self.assertNotIn('session/setMode', requested)
            with self.assertRaises(ProviderRuntimeError):
                ZCodeRuntime(access='bogus')
            runtime2, log2, result = self.connect(tmp)
            self.assertEqual(result['sessionId'], 'zai-session-1')
            self.assertEqual([m['value'] for m in result['models']], ['zai/glm-4.7', 'zai/glm-4.7-air'])
            self.assertEqual(result['models'][0]['displayName'], 'GLM 4.7')
            self.assertEqual(result['models'][0]['capabilities'], {'supportsImage': True})
            started = find_event(runtime2, 'runtime.started')
            self.assertEqual(started['data'], {'sessionId': 'zai-session-1', 'model': 'zai/glm-4.7', 'project': str(Path(tmp).resolve())})
            cached = runtime2.initialize(project=str(tmp))
            self.assertEqual(cached, {'models': result['models'], 'sessionId': 'zai-session-1'})
            self.assertEqual(len(log2.rpcs), 1)
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime2.initialize(project=str(second))
            self.assertEqual(str(ctx.exception), 'GLM chat belongs to another project')
            self.assertEqual(len(log2.rpcs), 1)
            self.assertEqual(runtime2.status()['state'], 'idle')

    def test_resume_blocks_model_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, result = self.connect(tmp, session_id='zai-existing')
            root = str(Path(tmp).resolve())
            rpc = log.last
            self.assertEqual(rpc.requests[0], ('session/resume', {
                'workspace': {'workspacePath': root, 'workspaceKey': root},
                'mcpServers': [], 'sessionId': 'zai-existing',
            }))
            self.assertEqual(result['sessionId'], 'zai-existing')
            self.assertNotIn('session/create', [method for method, _ in rpc.requests])
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.start('hi', project=str(tmp), model='zai/glm-4.7-air')
            self.assertEqual(str(ctx.exception), 'Start a new chat to change this GLM session model')
            self.assertEqual(len([1 for method, _ in rpc.requests if method == 'session/resume']), 1)
            entry = self.entry_file(tmp)
            log2 = FactoryLog()
            fresh = ZCodeRuntime(session_id='zai-existing', model='zai/glm-4.7-air',
                                 rpc_factory=make_factory(log2, {'session/resume': create_result('zai-existing')}))
            with patched_zcode(entry), self.assertRaises(ProviderRuntimeError) as ctx:
                fresh.initialize(project=str(tmp))
            self.assertEqual(str(ctx.exception), 'Start a new chat to change this GLM session model')
            self.assertEqual([method for method, _ in log2.last.requests if method in ('session/create', 'session/close')], [])
            self.assertEqual(fresh.status()['state'], 'offline')

    def test_model_switch_recreates_session_and_closes_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = {'session/create': lambda index, params: create_result(f'zai-session-{index + 1}')}
            runtime, log, result = self.connect(tmp, scripts=scripts, model='zai/glm-4.7-air')
            rpc = log.last
            creates = [params for method, params in rpc.requests if method == 'session/create']
            self.assertEqual(len(creates), 2)
            self.assertNotIn('model', creates[0])
            self.assertEqual(creates[1]['model'], {'providerId': 'zai', 'modelId': 'glm-4.7-air'})
            self.assertIn(('session/close', {'sessionId': 'zai-session-1'}), rpc.requests)
            self.assertEqual(result['sessionId'], 'zai-session-2')
            self.assertEqual(runtime.session_id, 'zai-session-2')
            self.assertEqual(runtime.model, 'zai/glm-4.7-air')
            self.assertEqual([params for method, params in rpc.requests if method == 'session/setMode'],
                             [{'sessionId': 'zai-session-2', 'mode': 'build'}])
            started = find_event(runtime, 'runtime.started')
            self.assertEqual(started['data']['sessionId'], 'zai-session-2')

    def test_send_images_require_support_and_stage_private_attachments(self):
        with tempfile.TemporaryDirectory() as tmp:
            air, _, _ = self.connect(tmp, model='zai/glm-4.7-air')
            with self.assertRaises(ProviderRuntimeError) as ctx:
                air.send('pic', images=[VALID_IMAGE])
            self.assertEqual(str(ctx.exception), 'This GLM model does not report image support')
            self.assertEqual(air.status()['state'], 'idle')
            state_root = Path(tmp) / 'state'
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            with patch.object(runtime_config, 'state_root', return_value=state_root):
                result = runtime.send('pic', images=[VALID_IMAGE])
            self.assertTrue(result['accepted'])
            self.assertEqual(result['provider'], 'zai')
            self.assertEqual(result['sessionId'], 'zai-session-1')
            wait_for(lambda: any(method == 'session/send' for method, _ in rpc.requests))
            send_params = [params for method, params in rpc.requests if method == 'session/send'][0]
            self.assertEqual(send_params['content'], 'pic')
            self.assertEqual(send_params['inputId'], result['turnId'])
            attachments = send_params['attachments']
            self.assertEqual(len(attachments), 1)
            staged = attachments[0]
            self.assertEqual(staged['type'], 'image')
            path = Path(staged['path'])
            self.assertEqual(path.parent, state_root / 'provider-attachments' / hashlib.sha256(b'zai-session-1').hexdigest())
            self.assertEqual(path.suffix, '.png')
            self.assertEqual(path.read_bytes(), PNG_BYTES)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(runtime.attachments, [path])

    def test_turn_streams_deltas_and_completion_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh = ZCodeRuntime(rpc_factory=make_factory(FactoryLog()))
            with self.assertRaises(ProviderRuntimeError) as ctx:
                fresh.send('   ')
            self.assertIn('Prompt must be non-empty', str(ctx.exception))
            with self.assertRaises(ProviderRuntimeError) as ctx:
                fresh.send('hello')
            self.assertEqual(str(ctx.exception), 'Wait for the current GLM turn or connect first')
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            result = runtime.send('hello')
            self.assertTrue(result['accepted'])
            wait_for(lambda: any(method == 'session/send' for method, _ in rpc.requests))
            send_params = [params for method, params in rpc.requests if method == 'session/send'][0]
            self.assertEqual(send_params, {'sessionId': 'zai-session-1', 'content': 'hello', 'inputId': result['turnId']})
            wait_for(lambda: find_event(runtime, 'message.completed') is not None)
            completed = find_event(runtime, 'message.completed')
            self.assertEqual(completed['data']['text'], 'Fixture answer')
            self.assertEqual(completed['data']['turnId'], result['turnId'])
            self.assertFalse(completed['data']['isError'])
            self.assertEqual(completed['data']['nativeUsage'], {'inputTokens': 7})
            self.assertIn(('session/usage', {'sessionId': 'zai-session-1'}), rpc.requests)
            deltas = [e['data']['text'] for e in runtime.events()['events'] if e['type'] == 'message.delta']
            self.assertEqual(deltas, ['Fixture answer'])
            self.assertEqual(runtime.status()['state'], 'idle')
            native_status = runtime.status()['nativeStatus']
            self.assertEqual(
                {key: native_status[key] for key in ('status', 'currentTurnId', 'turnCount')},
                {'status': 'completed', 'currentTurnId': None, 'turnCount': 1},
            )
            self.assertIsNone(native_status['activeToolCalls'])
            self.assertFalse(native_status['childrenVerified'])
            self.assertIsNone(native_status['activeChildCount'])

    def test_preferences_reply_and_permission_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            rpc.push({'id': 'pref-1', 'method': 'session/requestRuntimePreferences', 'params': {'sessionId': 'zai-session-1'}})
            self.assertEqual(rpc.replies, [('pref-1', {
                'nativeSearchEnhancementsEnabled': True, 'memoryEnabled': False,
                'askUserQuestionAutoResolutionEnabled': False, 'modelContextBudgetStrategy': 'preflight-v1'})])
            rpc.push({'id': 'unknown-1', 'method': 'session/neverHeardOfIt', 'params': {}})
            self.assertIn('unknown-1', rpc.rejections)
            rpc.push({'id': 'wrong-session', 'method': 'interaction/requestPermission',
                      'params': {'sessionId': 'other-session', 'requestId': 'perm-x'}})
            self.assertIn('wrong-session', rpc.rejections)
            rpc.push({'id': '21', 'method': 'interaction/requestPermission',
                      'params': {'sessionId': 'zai-session-1', 'requestId': 'perm-1', 'toolName': 'Bash',
                                 'input': {'command': 'ls'}, 'reason': 'fixture'}})
            approval = find_event(runtime, 'approval.requested')
            self.assertEqual(approval['data']['tool'], 'Bash')
            self.assertEqual(approval['data']['toolInput'], {'command': 'ls'})
            self.assertEqual(approval['data']['reason'], 'fixture')
            key = approval['data']['requestId']
            rpc.push({'id': '22', 'method': 'interaction/requestPermission',
                      'params': {'sessionId': 'zai-session-1', 'requestId': 'perm-1', 'toolName': 'Bash',
                                 'input': {'command': 'ls'}}})
            approvals = [e for e in runtime.events()['events'] if e['type'] == 'approval.requested']
            self.assertEqual(len(approvals), 1)
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.respond('missing-key', {'allow': True})
            self.assertEqual(str(ctx.exception), 'Native request is stale or unknown')
            self.assertEqual(runtime.respond(key, {'allow': True}), {'accepted': True})
            self.assertEqual(rpc.replies[-1], ('22', {'decision': 'allow'}))
            self.assertNotIn(('21', {'decision': 'allow'}), rpc.replies)
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.respond(key, {'allow': True})
            self.assertEqual(str(ctx.exception), 'Native request is stale or unknown')
            rpc.push({'id': '31', 'method': 'interaction/requestPermission',
                      'params': {'sessionId': 'zai-session-1', 'requestId': 'perm-2', 'toolName': 'Write'}})
            approvals = [e for e in runtime.events()['events'] if e['type'] == 'approval.requested']
            key2 = approvals[-1]['data']['requestId']
            self.assertEqual(runtime.respond(key2, {'decision': 'deny'}), {'accepted': True})
            self.assertEqual(rpc.replies[-1], ('31', {'decision': 'deny'}))
            resolved = [e for e in runtime.events()['events'] if e['type'] == 'request.resolved']
            self.assertEqual([e['data']['requestId'] for e in resolved], [key, key2])

    def test_stop_cancels_turn_and_pending_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, _ = self.connect(tmp, scripts={'session/read': [READ_BASELINE, READ_RUNNING]})
            rpc = log.last
            result = runtime.send('long work')
            self.assertTrue(result['accepted'])
            wait_for(lambda: any(method == 'session/send' for method, _ in rpc.requests))
            rpc.push({'id': 'perm-stop', 'method': 'interaction/requestPermission',
                      'params': {'sessionId': 'zai-session-1', 'requestId': 'perm-9', 'toolName': 'Bash'}})
            approval = find_event(runtime, 'approval.requested')
            self.assertIsNotNone(approval)
            self.assertEqual(runtime.stop(), {'accepted': True, 'sessionId': 'zai-session-1'})
            self.assertIn(('session/stop', {'sessionId': 'zai-session-1'}), rpc.requests)
            self.assertTrue(rpc.closed)
            self.assertEqual(runtime.status()['state'], 'offline')
            cancelled = [e for e in runtime.events()['events'] if e['type'] == 'request.cancelled']
            self.assertEqual([e['data']['requestId'] for e in cancelled], [approval['data']['requestId']])
            self.assertIsNone(find_event(runtime, 'message.completed'))


if __name__ == '__main__':
    unittest.main()
