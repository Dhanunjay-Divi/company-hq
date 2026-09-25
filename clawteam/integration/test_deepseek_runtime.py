"""Fixture-only DeepSeek runtime wiring; no provider turns or processes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deepseek_runtime import DeepSeekRuntime
from provider_runtime import ProviderRuntimeError


class Conn:
    def __init__(self, key='fixture-key', models=None): self.key, self.models = key, models or [{'value': 'deepseek-fixture'}]
    def key_for_runtime(self): return self.key
    def catalog_for_runtime(self): return [dict(row) for row in self.models]


class Stream:
    def close(self): pass


class Process:
    def __init__(self): self.stdin, self.stdout, self.stderr = Stream(), iter(()), None
    def poll(self): return None


class DeepSeekRuntimeTests(unittest.TestCase):
    def test_resumed_session_cannot_use_new_credentials(self):
        runtime = DeepSeekRuntime(binary='/fixture/claude', session_id='old-session', connection_=Conn(key='new-key'))
        with tempfile.TemporaryDirectory() as tmp, patch('claude_runtime.ClaudeCodeRuntime.initialize') as initialize:
            with self.assertRaisesRegex(ProviderRuntimeError, 'original session key'):
                runtime.initialize(project=tmp)
        initialize.assert_not_called()
        self.assertEqual(runtime.events()['events'], [])

    def test_unknown_model_fails_before_parent_initialize(self):
        runtime = DeepSeekRuntime(binary='/fixture/claude', model='not-listed', connection_=Conn())
        with tempfile.TemporaryDirectory() as tmp, patch('claude_runtime.ClaudeCodeRuntime.initialize') as initialize:
            with self.assertRaisesRegex(ProviderRuntimeError, 'reported by DeepSeek'):
                runtime.initialize(project=tmp)
        initialize.assert_not_called()

    def test_launch_uses_isolated_deepseek_environment_and_preserves_homes(self):
        captured = {}
        def factory(*args, **kwargs): captured.update(kwargs); captured['argv'] = args[0]; return Process()
        runtime = DeepSeekRuntime(binary='/fixture/claude', model='deepseek-fixture', connection_=Conn(), process_factory=factory)
        runtime._bound_key, runtime._bound_model = 'fixture-key', 'deepseek-fixture'
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {'HOME': '/home/fixture', 'CODEX_HOME': '/codex/fixture', 'PATH': '/usr/bin', 'OPENAI_API_KEY': 'other-secret', 'AWS_SECRET_ACCESS_KEY': 'cloud-secret', 'DEEPSEEK_API_KEY': 'unbound-secret', 'ANTHROPIC_AUTH_TOKEN': 'wrong', 'CLAUDE_CONFIG_DIR': '/claude/account'}, clear=True), patch('deepseek_runtime.state_root', return_value=Path(state)):
            runtime.project = tmp; runtime._launch(resume=False)
        env = captured['env']
        self.assertEqual(env['HOME'], '/home/fixture'); self.assertEqual(env['CODEX_HOME'], '/codex/fixture')
        self.assertEqual(env['PATH'], '/usr/bin')
        for name in ('OPENAI_API_KEY', 'AWS_SECRET_ACCESS_KEY', 'DEEPSEEK_API_KEY'):
            self.assertNotIn(name, env)
        self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'], 'fixture-key'); self.assertEqual(env['ANTHROPIC_BASE_URL'], 'https://api.deepseek.com/anthropic')
        self.assertEqual(env['ANTHROPIC_MODEL'], 'deepseek-fixture'); self.assertEqual(env['CLAUDE_CODE_SUBAGENT_MODEL'], 'deepseek-fixture'); self.assertNotEqual(env['CLAUDE_CONFIG_DIR'], '/claude/account')
        self.assertNotIn('fixture-key', ' '.join(captured['argv']))
        self.assertEqual(captured['argv'][captured['argv'].index('--setting-sources') + 1], '')
        self.assertIn('--strict-mcp-config', captured['argv'])

    def test_send_model_change_validates_catalog_before_any_turn(self):
        runtime = DeepSeekRuntime(binary='/fixture/claude', connection_=Conn())
        with self.assertRaisesRegex(ProviderRuntimeError, 'not started'):
            runtime.send('hello', model='other')
        self.assertEqual(runtime.events()['events'], [])

    def test_bound_key_redacts_nested_events_after_connection_changes(self):
        conn = Conn(); runtime = DeepSeekRuntime(binary='/fixture/claude', connection_=conn)
        runtime._bound_key = 'fixture-key'; conn.key = None
        runtime._event('provider.event', nested={'message': 'fixture-key must not leak'})
        self.assertNotIn('fixture-key', repr(runtime.events()))

    def test_active_session_rejects_model_change(self):
        runtime = DeepSeekRuntime(binary='/fixture/claude', connection_=Conn())
        runtime.process, runtime.project, runtime._bound_model = Process(), '/fixture', 'deepseek-fixture'
        with self.assertRaisesRegex(ProviderRuntimeError, 'new DeepSeek chat'):
            runtime.initialize(project='/fixture', model='other')
