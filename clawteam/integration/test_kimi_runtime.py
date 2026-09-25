"""Fixture tests for the Kimi native ACP runtime; no live CLI, network, or account access."""
from __future__ import annotations

import base64
import contextlib
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from kimi_runtime import KimiRuntime, kimi_binary, login_command
from provider_runtime import ProviderRuntimeError

PNG_B64 = base64.b64encode(b'fixture-png-bytes').decode('ascii')
VALID_IMAGE = {'mimeType': 'image/png', 'data': PNG_B64}

KIMI_CAPABILITIES = {'promptCapabilities': {'image': True}}
KIMI_SESSION = {
    'sessionId': 'kimi-session-1',
    'configOptions': [
        {'id': 'model', 'currentValue': 'kimi-for-coding', 'options': [
            {'value': 'kimi-for-coding', 'name': 'Kimi For Coding'},
            {'value': 'kimi-turbo', 'name': 'Kimi Turbo'},
        ]},
    ],
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


class FakeKimiRpc:
    """Scripted newline-RPC double; records every outbound frame."""

    def __init__(self, command, project, handle):
        self.command, self.project, self.handle = command, project, handle
        self.requests, self.notifies, self.replies, self.rejections = [], [], [], []
        self.scripts, self.gates, self.counts = {}, {}, {}
        self.closed = False
        self.scripts.update({
            'initialize': {'agentInfo': {'version': '2.0.2-fixture'}, 'agentCapabilities': KIMI_CAPABILITIES},
            'authenticate': {},
            'session/new': dict(KIMI_SESSION),
            'session/set_config_option': {},
            'session/set_mode': {},
            'session/prompt': {'stopReason': 'end_turn'},
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
    def factory(command, project, handle):
        rpc = FakeKimiRpc(command, project, handle)
        for method, value in (scripts or {}).items():
            rpc.script(method, value)
        log.rpcs.append(rpc)
        return rpc
    return factory


@contextlib.contextmanager
def patched_kimi_binary(path='/fixtures/kimi-cli'):
    with patch('kimi_runtime.kimi_binary', return_value=path):
        yield


class KimiRuntimeTest(unittest.TestCase):
    def build(self, *, scripts=None, **kwargs):
        log = FactoryLog()
        return KimiRuntime(rpc_factory=make_factory(log, scripts), **kwargs), log

    def connect(self, tmp, *, scripts=None, **kwargs):
        runtime, log = self.build(scripts=scripts, **kwargs)
        with patched_kimi_binary():
            result = runtime.initialize(project=str(tmp))
        self.addCleanup(runtime.stop)
        return runtime, log, result

    def test_binary_discovery_override_and_missing_cli_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / 'kimi'
            override.write_text('#!/bin/sh\n')
            override.chmod(0o755)
            with patch.dict(os.environ, {'COMPANY_HQ_KIMI_PATH': str(override)}):
                self.assertEqual(kimi_binary(), str(Path(override).resolve()))
            with patch.dict(os.environ, {}, clear=True), \
                 patch('kimi_runtime.shutil.which', return_value=None), \
                 patch.object(Path, 'home', return_value=Path(tmp) / 'absent-home'):
                self.assertIsNone(kimi_binary())
                with self.assertRaises(ProviderRuntimeError) as ctx:
                    login_command()
            self.assertEqual(str(ctx.exception), 'Install the official Kimi Code CLI to connect.')

    def test_initialize_rejects_model_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log = self.build(model='kimi-ultra')
            with patched_kimi_binary(), self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.initialize(project=str(tmp))
            self.assertEqual(str(ctx.exception), 'Select a model reported by Kimi')
            rpc = log.last
            self.assertTrue(rpc.closed)
            self.assertIsNone(runtime.rpc)
            self.assertEqual(runtime.status()['state'], 'offline')
            requested = [method for method, _ in rpc.requests]
            self.assertIn('authenticate', requested)
            self.assertIn('session/new', requested)
            self.assertNotIn('session/set_config_option', requested)
            with self.assertRaises(ProviderRuntimeError):
                KimiRuntime(access='bogus')

    def test_initialize_caches_session_and_binds_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            second = Path(tmp) / 'second'
            second.mkdir()
            runtime, log, result = self.connect(tmp)
            root = str(Path(tmp).resolve())
            self.assertEqual(result['sessionId'], 'kimi-session-1')
            self.assertEqual([m['value'] for m in result['models']], ['kimi-for-coding', 'kimi-turbo'])
            self.assertEqual(result['models'][1]['displayName'], 'Kimi Turbo')
            self.assertEqual(result['capabilities'], KIMI_CAPABILITIES)
            rpc = log.last
            self.assertEqual(rpc.command, ['/fixtures/kimi-cli', 'acp'])
            self.assertEqual(rpc.project, root)
            started = find_event(runtime, 'runtime.started')
            self.assertEqual(started['data'], {'sessionId': 'kimi-session-1', 'model': 'kimi-for-coding', 'project': root})
            self.assertIn(('session/set_mode', {'sessionId': 'kimi-session-1', 'modeId': 'auto'}), rpc.requests)
            cached = runtime.initialize(project=str(tmp))
            self.assertEqual(cached, {'models': result['models'], 'sessionId': 'kimi-session-1'})
            self.assertEqual(len(log.rpcs), 1)
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.initialize(project=str(second))
            self.assertEqual(str(ctx.exception), 'Kimi chat belongs to another project')
            self.assertEqual(len(log.rpcs), 1)
            self.assertEqual(runtime.status()['state'], 'idle')

    def test_start_switches_reported_model_and_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            rpc.gate('session/prompt')
            result = runtime.start('switch please', project=str(tmp), model='kimi-turbo')
            self.assertTrue(result['accepted'])
            self.assertEqual(runtime.model, 'kimi-turbo')
            settings = [params['value'] for method, params in rpc.requests if method == 'session/set_config_option']
            self.assertEqual(settings, ['kimi-for-coding', 'kimi-turbo'])
            self.assertEqual(len(log.rpcs), 1)
            wait_for(lambda: any(method == 'session/prompt' for method, _ in rpc.requests))
            rpc.release('session/prompt')
            wait_for(lambda: find_event(runtime, 'message.completed') is not None)
            completed = find_event(runtime, 'message.completed')
            self.assertEqual(completed['data']['turnId'], result['turnId'])
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.start('again', project=str(tmp), model='kimi-ultra')
            self.assertEqual(str(ctx.exception), 'Select a model reported by Kimi')
            self.assertEqual(runtime.status()['state'], 'idle')

    def test_send_gates_turns_and_streams_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh, _ = self.build()
            with self.assertRaises(ProviderRuntimeError) as ctx:
                fresh.send('   ')
            self.assertIn('Prompt must be non-empty', str(ctx.exception))
            with self.assertRaises(ProviderRuntimeError) as ctx:
                fresh.send('hello')
            self.assertEqual(str(ctx.exception), 'Wait for the current Kimi turn or connect first')
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            rpc.gate('session/prompt')
            result = runtime.send('hello')
            self.assertTrue(result['accepted'])
            self.assertEqual(result['provider'], 'kimi')
            self.assertEqual(result['sessionId'], 'kimi-session-1')
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.send('second')
            self.assertEqual(str(ctx.exception), 'Wait for the current Kimi turn or connect first')
            wait_for(lambda: any(method == 'session/prompt' for method, _ in rpc.requests))
            self.assertEqual(rpc.requests[-1], ('session/prompt', {'sessionId': 'kimi-session-1', 'prompt': [{'type': 'text', 'text': 'hello'}]}))
            user = find_event(runtime, 'message.user')
            self.assertEqual(user['data']['turnId'], result['turnId'])
            rpc.push({'method': 'session/update', 'params': {'sessionId': 'elsewhere', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'text': 'ignored'}}}})
            rpc.push({'method': 'session/update', 'params': {'sessionId': 'kimi-session-1', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'text': 'Bonjour '}}}})
            rpc.push({'method': 'session/update', 'params': {'sessionId': 'kimi-session-1', 'update': {'sessionUpdate': 'tool_call', 'title': 'Read file', 'status': 'pending', 'toolCallId': 't-1'}}})
            rpc.push({'method': 'session/update', 'params': {'sessionId': 'kimi-session-1', 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'text': 'le monde'}}}})
            wait_for(lambda: len([e for e in runtime.events()['events'] if e['type'] == 'message.delta']) >= 2)
            rpc.release('session/prompt')
            wait_for(lambda: find_event(runtime, 'message.completed') is not None)
            completed = find_event(runtime, 'message.completed')
            self.assertEqual(completed['data']['text'], 'Bonjour le monde')
            self.assertEqual(completed['data']['stopReason'], 'end_turn')
            self.assertFalse(completed['data']['isError'])
            self.assertEqual(completed['data']['turnId'], result['turnId'])
            activity = find_event(runtime, 'tool.activity')
            self.assertEqual(activity['data'], {'title': 'Read file', 'status': 'pending', 'toolCallId': 't-1', 'sessionId': 'kimi-session-1', 'turnId': result['turnId']})
            deltas = [e['data']['text'] for e in runtime.events()['events'] if e['type'] == 'message.delta']
            self.assertEqual(deltas, ['Bonjour ', 'le monde'])
            self.assertEqual(runtime.status()['state'], 'idle')

    def test_images_require_capability_and_forward_as_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            capped, _, _ = self.connect(tmp, scripts={'initialize': {'agentInfo': {'version': '2.0.2-fixture'}, 'agentCapabilities': {'promptCapabilities': {}}}})
            with self.assertRaises(ProviderRuntimeError) as ctx:
                capped.send('look', images=[VALID_IMAGE])
            self.assertEqual(str(ctx.exception), 'This Kimi runtime does not report image support')
            self.assertEqual(capped.status()['state'], 'idle')
            runtime, log, _ = self.connect(tmp, scripts={'session/prompt': {'stopReason': 'cancelled'}})
            rpc = log.last
            rpc.gate('session/prompt')
            result = runtime.send('look', images=[VALID_IMAGE])
            self.assertTrue(result['accepted'])
            wait_for(lambda: any(method == 'session/prompt' for method, _ in rpc.requests))
            self.assertEqual(rpc.requests[-1][1]['prompt'], [
                {'type': 'text', 'text': 'look'},
                {'type': 'image', 'data': PNG_B64, 'mimeType': 'image/png'},
            ])
            rpc.release('session/prompt')
            wait_for(lambda: find_event(runtime, 'message.completed') is not None)
            completed = find_event(runtime, 'message.completed')
            self.assertEqual(completed['data']['stopReason'], 'cancelled')
            self.assertTrue(completed['data']['isError'])
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.send('again', images=[{'mimeType': 'image/tiff', 'data': 'AAAA'}])
            self.assertEqual(str(ctx.exception), 'Claude image attachment has an unsupported media type')
            self.assertEqual(runtime.status()['state'], 'idle')

    def test_permission_request_round_trip(self):
        permission = {'sessionId': 'kimi-session-1', 'options': [
            {'kind': 'allow_once', 'optionId': 'allow-1'}, {'kind': 'reject_once', 'optionId': 'reject-1'}]}
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            rpc.push({'id': 11, 'method': 'session/request_permission', 'params': {**permission, 'toolCall': {'title': 'Bash', 'rawInput': {'command': 'ls'}}}})
            approval = find_event(runtime, 'approval.requested')
            self.assertEqual(approval['data']['tool'], 'Bash')
            self.assertEqual(approval['data']['toolInput'], {'command': 'ls'})
            key = approval['data']['requestId']
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.respond(key, 'yes')
            self.assertEqual(str(ctx.exception), 'Provide an approval response')
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.respond('stale-key', {'allow': True})
            self.assertEqual(str(ctx.exception), 'Native request is stale or unknown')
            self.assertEqual(runtime.respond(key, {'allow': True}), {'accepted': True})
            self.assertEqual(rpc.replies, [(11, {'outcome': {'outcome': 'selected', 'optionId': 'allow-1'}})])
            rpc.push({'id': 12, 'method': 'session/request_permission', 'params': {**permission, 'toolCall': {}}})
            approvals = [e for e in runtime.events()['events'] if e['type'] == 'approval.requested']
            self.assertEqual(approvals[-1]['data']['tool'], 'Kimi tool')
            key2 = approvals[-1]['data']['requestId']
            self.assertEqual(runtime.respond(key2, {'decision': 'deny'}), {'accepted': True})
            self.assertEqual(rpc.replies[-1], (12, {'outcome': {'outcome': 'selected', 'optionId': 'reject-1'}}))
            rpc.push({'id': 'u9', 'method': 'session/neverHeardOfIt', 'params': {'sessionId': 'kimi-session-1'}})
            self.assertIn('u9', rpc.rejections)
            # A pending native request blocks new turns until resolved.
            rpc.push({'id': 13, 'method': 'session/request_permission', 'params': {**permission, 'toolCall': {}}})
            approvals = [e for e in runtime.events()['events'] if e['type'] == 'approval.requested']
            key3 = approvals[-1]['data']['requestId']
            with self.assertRaises(ProviderRuntimeError) as ctx:
                runtime.send('blocked')
            self.assertEqual(str(ctx.exception), 'Respond to the pending native request')
            self.assertEqual(runtime.respond(key3, {'allow': False}), {'accepted': True})
            self.assertEqual(rpc.replies[-1], (13, {'outcome': {'outcome': 'selected', 'optionId': 'reject-1'}}))
            self.assertEqual([e['type'] for e in runtime.events()['events']].count('request.resolved'), 3)

    def test_stream_close_marks_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = self.connect(tmp)
            runtime.rpc.push({'method': 'hq/stream_closed', 'params': {}})
            self.assertEqual(runtime.status()['state'], 'error')
            self.assertFalse(runtime.status()['connected'])
            error = find_event(runtime, 'runtime.error')
            self.assertEqual(error['data']['message'], 'Kimi connection closed')

    def test_stop_cancels_running_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, log, _ = self.connect(tmp)
            rpc = log.last
            rpc.gate('session/prompt')
            result = runtime.send('long work')
            self.assertTrue(result['accepted'])
            wait_for(lambda: any(method == 'session/prompt' for method, _ in rpc.requests))
            self.assertEqual(runtime.stop(), {'accepted': True, 'sessionId': 'kimi-session-1'})
            self.assertEqual(rpc.notifies, [('session/cancel', {'sessionId': 'kimi-session-1'})])
            self.assertTrue(rpc.closed)
            self.assertIsNone(runtime.rpc)
            self.assertEqual(runtime.status()['state'], 'offline')
            rpc.release('session/prompt')
            time.sleep(0.2)
            self.assertIsNone(find_event(runtime, 'message.completed'))


if __name__ == '__main__':
    unittest.main()
