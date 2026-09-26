from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import provider_connections
from provider_connections import CodexSignIn, ProviderConnections


class FakeConnection:
    def __init__(self, responses=None, *, immediate_login=None):
        self.responses = responses or {}
        self.immediate_login = immediate_login
        self.sent = []
        self.on_message = None
        self.on_exit = None
        self.is_running = False

    def start(self, on_message, on_exit):
        self.on_message = on_message
        self.on_exit = on_exit
        self.is_running = True

    def running(self):
        return self.is_running

    def close(self):
        self.is_running = False

    def send(self, message):
        self.sent.append(json.loads(json.dumps(message)))
        if 'id' not in message:
            return
        method = message['method']
        response = self.responses.get(method, {})
        if callable(response):
            response = response(message)
        if isinstance(response, Exception):
            self.on_message({'id': message['id'], 'error': {'message': str(response)}})
            return
        if method == 'account/login/start' and self.immediate_login is not None:
            self.on_message({
                'method': 'account/login/completed',
                'params': dict(self.immediate_login),
            })
        self.on_message({'id': message['id'], 'result': response})

    def calls(self, method):
        return [item for item in self.sent if item.get('method') == method]


def inventory(*, desktop_path=None):
    return {
        'providers': [{
            'id': 'codex',
            'name': 'Codex',
            'desktopPath': desktop_path,
            'cliPath': '/private/local/provider-cli',
        }],
    }


class ProviderConnectionsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='provider-connections-')
        self.root = Path(self.temporary.name)
        self.routing = self.root / 'routing.json'
        self.routing.write_text(json.dumps({
            'reviewed_codex_models': ['gpt-6-astra', 'gpt-5.6-terra'],
        }))
        self.routing_patch = patch.object(provider_connections, 'routing_path', return_value=self.routing)
        self.routing_patch.start()

    def tearDown(self):
        self.routing_patch.stop()
        self.temporary.cleanup()

    def signed_in_responses(self):
        return {
            'initialize': {'userAgent': 'fixture'},
            'account/read': {
                'account': {
                    'type': 'chatgpt',
                    'email': 'private@example.test',
                    'planType': 'plus',
                    'unexpectedToken': 'must-not-leak',
                },
                'requiresOpenaiAuth': True,
            },
            'model/list': {
                'data': [
                    {'model': 'gpt-6-astra', 'id': 'astra', 'hidden': False},
                    {'model': 'gpt-5.6-terra', 'id': 'terra', 'hidden': True},
                    {'model': 'unreviewed', 'id': 'unreviewed', 'hidden': False},
                ],
            },
            'account/rateLimits/read': {
                'accountId': 'private-account-id',
                'rateLimits': {'primary': {'usedPercent': 99}},
                'rateLimitsByLimitId': {
                    'codex': {
                        'limitId': 'codex',
                        'limitName': 'Codex included usage',
                        'primary': {'usedPercent': 25, 'windowDurationMins': 300, 'resetsAt': 1_800_000_000},
                        'secondary': {'usedPercent': 50.5, 'windowDurationMins': 10080, 'resetsAt': 1_800_500_000},
                    },
                    'luna-reserve': {
                        'limitId': 'luna-reserve',
                        'limitName': 'Luna reserve',
                        'primary': {'usedPercent': 5, 'windowDurationMins': 1440, 'resetsAt': 1_800_100_000},
                    },
                },
                'totalTokens': 987654,
            },
        }

    def test_signed_in_check_sanitizes_account_models_and_distinct_quota_buckets(self):
        connection = FakeConnection(self.signed_in_responses())
        auth = CodexSignIn(factory=lambda: connection)
        result = auth.check()

        self.assertEqual(result['authentication'], 'signed_in')
        self.assertEqual(result['models'], ['gpt-6-astra'])
        self.assertEqual(result['usageScope'], 'account_allowance')
        self.assertEqual(
            [(row['id'], row['limitId'], row['limitLabel'], row['window']) for row in result['usageWindows']],
            [
                ('codex-primary', 'codex', 'Codex included usage', 'primary'),
                ('codex-secondary', 'codex', 'Codex included usage', 'secondary'),
                ('luna-reserve-primary', 'luna-reserve', 'Luna reserve', 'primary'),
            ],
        )
        self.assertEqual(result['usageWindows'][0]['windowDurationMins'], 300)
        serialized = json.dumps(result)
        for secret in ('private@example.test', 'private-account-id', 'must-not-leak', '987654'):
            self.assertNotIn(secret, serialized)
        self.assertNotIn('totalTokens', serialized)

    def test_invalid_usage_percentages_are_unknown_not_zero(self):
        rows = provider_connections._usage_windows({
            'rateLimitsByLimitId': {
                'invalid': {
                    'limitName': 'Invalid values',
                    'primary': {'usedPercent': None, 'windowDurationMins': 300},
                    'secondary': {'usedPercent': True, 'windowDurationMins': 300},
                },
                'nonfinite': {
                    'primary': {'usedPercent': math.nan, 'windowDurationMins': math.inf},
                    'secondary': {'usedPercent': 101, 'windowDurationMins': 300},
                },
                'negative': {
                    'primary': {'usedPercent': -1, 'windowDurationMins': 30},
                },
                'valid': {
                    'primary': {'usedPercent': 0, 'windowDurationMins': 60, 'resetsAt': 0},
                },
            },
        })
        self.assertEqual(rows, [
            {
                'id': 'nonfinite-secondary',
                'limitId': 'nonfinite',
                'limitLabel': 'nonfinite',
                'window': 'secondary',
                'usedPercent': 100,
                'windowDurationMins': 300,
                'resetsAt': None,
            },
            {
                'id': 'negative-primary',
                'limitId': 'negative',
                'limitLabel': 'negative',
                'window': 'primary',
                'usedPercent': 0,
                'windowDurationMins': 30,
                'resetsAt': None,
            },
            {
                'id': 'valid-primary',
                'limitId': 'valid',
                'limitLabel': 'valid',
                'window': 'primary',
                'usedPercent': 0,
                'windowDurationMins': 60,
                'resetsAt': 0,
            },
        ])

    def test_connect_reuses_existing_sign_in_without_starting_oauth(self):
        connection = FakeConnection(self.signed_in_responses())
        result = CodexSignIn(factory=lambda: connection).connect()
        self.assertEqual(result['authentication'], 'signed_in')
        self.assertEqual(connection.calls('account/login/start'), [])

    def test_immediate_login_callback_is_buffered_before_rpc_response(self):
        login_id = 'login-immediate'
        connection = FakeConnection({
            'initialize': {},
            'account/read': {'account': None, 'requiresOpenaiAuth': True},
            'account/login/start': {
                'type': 'chatgpt',
                'loginId': login_id,
                'authUrl': 'https://auth.openai.com/oauth/authorize?state=opaque',
            },
        }, immediate_login={'loginId': login_id, 'success': True, 'error': None})
        result = CodexSignIn(factory=lambda: connection).connect()
        self.assertEqual(result['authentication'], 'signed_in')
        self.assertNotIn('authUrl', result)
        self.assertEqual(len(connection.calls('account/login/start')), 1)

    def test_valid_oauth_can_be_cancelled_without_returning_login_id(self):
        connection = FakeConnection({
            'initialize': {},
            'account/read': {'account': None, 'requiresOpenaiAuth': True},
            'account/login/start': {
                'type': 'chatgpt',
                'loginId': 'private-login-id',
                'authUrl': 'https://auth.openai.com/oauth/authorize?state=opaque',
            },
            'account/login/cancel': {'status': 'canceled'},
        })
        auth = CodexSignIn(factory=lambda: connection)
        started = auth.connect()
        self.assertEqual(started['authentication'], 'signing_in')
        self.assertNotIn('loginId', json.dumps(started))
        cancelled = auth.cancel()
        self.assertEqual(cancelled['authentication'], 'not_checked')
        self.assertNotIn('authUrl', cancelled)
        self.assertEqual(connection.calls('account/login/cancel')[0]['params'], {'loginId': 'private-login-id'})

    def test_malicious_oauth_urls_are_rejected_and_native_login_is_cancelled(self):
        bad_urls = (
            'http://auth.openai.com/oauth',
            'https://auth.openai.com.evil.test/oauth',
            'https://user:password@auth.openai.com/oauth',
            'https://auth.openai.com:444/oauth',
            'https://auth.openai.com/oauth\nheader',
        )
        for number, url in enumerate(bad_urls):
            with self.subTest(url=url):
                login_id = f'bad-login-{number}'
                connection = FakeConnection({
                    'initialize': {},
                    'account/read': {'account': None, 'requiresOpenaiAuth': True},
                    'account/login/start': {'type': 'chatgpt', 'loginId': login_id, 'authUrl': url},
                    'account/login/cancel': {'status': 'canceled'},
                })
                auth = CodexSignIn(factory=lambda: connection)
                with self.assertRaisesRegex(ValueError, 'unsupported sign-in address'):
                    auth.connect()
                self.assertEqual(connection.calls('account/login/cancel')[0]['params'], {'loginId': login_id})
                self.assertNotIn('authUrl', auth.snapshot())

    def test_failed_check_clears_stale_models_and_account_quota(self):
        responses = self.signed_in_responses()
        connection = FakeConnection(responses)
        auth = CodexSignIn(factory=lambda: connection)
        self.assertTrue(auth.check()['usageWindows'])
        responses['account/read'] = RuntimeError('/private/account/path must not leak')

        with self.assertRaisesRegex(ValueError, 'connection check failed') as failure:
            auth.check()
        self.assertNotIn('/private/account/path', str(failure.exception))
        snapshot = auth.snapshot()
        self.assertEqual(snapshot['authentication'], 'connection_failed')
        self.assertEqual(snapshot['models'], [])
        self.assertEqual(snapshot['usageWindows'], [])

    def test_demo_blocks_action_before_inventory_or_auth(self):
        class ForbiddenAuth:
            def connect(self):
                raise AssertionError('auth must not run in demo')

        providers = ProviderConnections(auth=ForbiddenAuth())
        with patch.object(provider_connections, 'demo_mode', return_value=True), patch.object(
            provider_connections, '_inventory', side_effect=AssertionError('inventory must not run in demo'),
        ):
            with self.assertRaisesRegex(ValueError, 'disabled in demo mode'):
                providers.action('codex', 'connect')

    def test_snapshot_hides_local_executable_paths(self):
        auth = CodexSignIn(factory=lambda: FakeConnection())
        with patch.object(provider_connections, '_inventory', return_value=inventory()):
            result = ProviderConnections(auth=auth).snapshot()
        serialized = json.dumps(result)
        self.assertNotIn('/private/local/provider-cli', serialized)
        self.assertTrue(result['providers'][0]['cliInstalled'])
        self.assertFalse(result['providers'][0]['desktopInstalled'])

    def test_open_uses_fixed_binary_and_resolved_app_path(self):
        app = self.root / 'Provider.app'
        app.mkdir()
        providers = ProviderConnections(auth=CodexSignIn(factory=lambda: FakeConnection()))
        with patch.object(provider_connections, 'demo_mode', return_value=False), patch.object(
            provider_connections, '_inventory', return_value=inventory(desktop_path=str(app)),
        ), patch.object(provider_connections.sys, 'platform', 'darwin'), patch.object(
            provider_connections.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0),
        ) as run:
            result = providers.action('codex', 'open')
        self.assertEqual(result['state'], 'desktop_opened')
        self.assertIn('separate', result['message'])
        self.assertEqual(run.call_args.args[0], ['/usr/bin/open', str(app.resolve())])
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertIs(run.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_desktop_only_claude_is_not_misreported_as_ready_or_signed_in(self):
        app = self.root / 'Claude.app'
        app.mkdir()
        rows = {'providers': [{'id': 'claude', 'label': 'Claude', 'installed': True,
                              'desktopPath': str(app), 'cliPath': None, 'runtimeReady': False}]}
        providers = ProviderConnections(auth=CodexSignIn(factory=lambda: FakeConnection()))
        providers.claude.value = {'authentication': 'not_installed', 'installed': False, 'models': []}
        with patch.object(provider_connections, '_inventory', return_value=rows), patch(
            'claude_runtime.claude_binary', return_value=None,
        ), patch.object(provider_connections, 'demo_mode', return_value=False), patch.object(
            providers.claude, 'connect', side_effect=AssertionError('login must not start'),
        ):
            row = providers.snapshot()['providers'][0]
            self.assertTrue(row['installed'])
            self.assertTrue(row['desktopInstalled'])
            self.assertFalse(row['cliInstalled'])
            self.assertFalse(row['runtimeReady'])
            self.assertIn('separate', row['reason'])
            with self.assertRaisesRegex(ValueError, 'runtime is not ready'):
                providers.action('claude', 'connect')

    def test_open_failure_returns_generic_error_without_app_path(self):
        app = self.root / 'Private Provider.app'
        app.mkdir()
        providers = ProviderConnections(auth=CodexSignIn(factory=lambda: FakeConnection()))
        with patch.object(provider_connections, 'demo_mode', return_value=False), patch.object(
            provider_connections, '_inventory', return_value=inventory(desktop_path=str(app)),
        ), patch.object(provider_connections.sys, 'platform', 'darwin'), patch.object(
            provider_connections.subprocess, 'run', side_effect=OSError(f'failed {app}'),
        ):
            with self.assertRaisesRegex(ValueError, 'Provider connection step failed') as failure:
                providers.action('codex', 'open')
        self.assertNotIn(str(app), str(failure.exception))


if __name__ == '__main__':
    unittest.main()
