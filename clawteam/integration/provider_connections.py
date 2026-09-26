"""Provider discovery and explicit native sign-in; never a credential store."""
from __future__ import annotations

import atexit
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import urlparse

from codex_bridge import _StdioConnection
from runtime_config import REPO_ROOT, codex_executable, demo_mode, routing_path


def _now():
    return datetime.now(timezone.utc).isoformat()


def _inventory():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from provider_registry import inventory
    return inventory()


HELP_URLS = {
    'openai-compatible': None,
    'deepseek': 'https://platform.deepseek.com/api_keys',
    'codex': 'https://chatgpt.com/',
    'claude': 'https://claude.ai/login',
    'kimi': 'https://www.kimi.com/code/',
    'zai': 'https://z.ai/',
    'cursor': 'https://cursor.com/',
    'grok': 'https://grok.com/',
    'ollama': 'https://ollama.com/',
}

SETUP_URLS = {
    'codex': 'https://developers.openai.com/codex/quickstart',
    'claude': 'https://code.claude.com/docs/en/setup',
    'kimi': 'https://moonshotai.github.io/kimi-code/en/guides/getting-started',
    'zai': 'https://zcode.z.ai/en/docs/install',
}

OFFICIAL_CODEX_AUTH_HOSTS = frozenset({
    'auth.openai.com',
    'auth0.openai.com',
    'chatgpt.com',
})


def _official_auth_url(value):
    """Accept only ordinary HTTPS URLs on the native provider's known hosts."""
    if not isinstance(value, str) or not value or len(value) > 8192:
        return False
    if any(ord(character) <= 32 for character in value):
        return False
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == 'https'
        and parsed.hostname in OFFICIAL_CODEX_AUTH_HOSTS
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
    )


def _finite_number(value, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _usage_windows(payload):
    """Return account allowance windows without inventing unknown percentages."""
    by_limit = payload.get('rateLimitsByLimitId')
    if isinstance(by_limit, dict) and by_limit:
        buckets = by_limit.items()
    else:
        buckets = (('codex', payload.get('rateLimits')),)
    rows = []
    for bucket_key, bucket in buckets:
        if not isinstance(bucket_key, str) or not isinstance(bucket, dict):
            continue
        reported_id = bucket.get('limitId')
        limit_id = reported_id if isinstance(reported_id, str) and reported_id else bucket_key
        reported_label = bucket.get('limitName')
        limit_label = reported_label if isinstance(reported_label, str) and reported_label else limit_id
        for window_id in ('primary', 'secondary'):
            window = bucket.get(window_id)
            if not isinstance(window, dict):
                continue
            reported_percent = _finite_number(window.get('usedPercent'))
            if reported_percent is None:
                continue
            used_percent = max(0, min(100, reported_percent))
            duration = _finite_number(window.get('windowDurationMins'), minimum=0)
            resets_at = _finite_number(window.get('resetsAt'), minimum=0)
            rows.append({
                'id': f'{bucket_key}-{window_id}',
                'limitId': limit_id,
                'limitLabel': limit_label,
                'window': window_id,
                'usedPercent': used_percent,
                'windowDurationMins': duration,
                'resetsAt': resets_at,
            })
    return rows


class CodexSignIn:
    """App-owned native transport for sign-in and read-only metadata. Never starts turns."""
    def __init__(self, factory=None):
        self.factory = factory or (lambda: _StdioConnection(codex_executable()))
        self.connection = None
        self.pending = {}
        self.counter = 0
        self.lock = threading.RLock()
        self.operation = threading.RLock()
        self.login_id = None
        self.login_results = {}
        self.cancelled_login_ids = deque(maxlen=8)
        self.value = {'authentication': 'not_checked'}

    def _receive(self, message):
        with self.lock:
            pending = self.pending.get(message.get('id'))
            if pending is not None:
                pending[1].append(message)
                pending[0].set()
                return
            if message.get('method') == 'account/login/completed':
                params = message.get('params', {})
                login_id = params.get('loginId')
                if login_id in self.cancelled_login_ids:
                    return
                if isinstance(login_id, str):
                    self.login_results[login_id] = bool(params.get('success'))
                    self.login_results = dict(list(self.login_results.items())[-8:])
                if self.login_id and login_id == self.login_id:
                    self.value = {
                        'authentication': 'signed_in' if params.get('success') else 'sign_in_failed',
                        'message': 'Sign-in completed. Check connection to load models.' if params.get('success') else 'Sign-in did not complete. You can try again.',
                        'checkedAt': _now(),
                    }
                    self.login_id = None

    def _exit(self, _reason):
        with self.lock:
            for event, output in self.pending.values():
                output.append({'error': {'message': 'Native connection closed'}})
                event.set()
            self.login_id = None
            self.value = {
                'authentication': 'connection_failed',
                'models': [],
                'usageWindows': [],
                'usageScope': 'account_allowance',
                'message': 'Native provider connection closed. Try again.',
                'checkedAt': _now(),
            }

    def _rpc(self, method, params):
        with self.lock:
            self.counter += 1
            request_id = self.counter
            event, output = threading.Event(), []
            self.pending[request_id] = (event, output)
        try:
            try:
                self.connection.send({'id': request_id, 'method': method, 'params': params})
            except Exception as exc:
                raise ValueError('The native provider could not complete this connection step.') from exc
            if not event.wait(15):
                raise ValueError('Provider connection timed out. Try again.')
            if not output or 'error' in output[0]:
                raise ValueError('The native provider could not complete this connection step.')
            return output[0].get('result', {})
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def _ensure(self):
        if self.connection and self.connection.running():
            return
        try:
            self.connection = self.factory()
            self.connection.start(self._receive, self._exit)
            self._rpc('initialize', {'clientInfo': {'name': 'company-hq-connections', 'version': '1'}})
            self.connection.send({'method': 'initialized', 'params': {}})
        except Exception as exc:
            if self.connection:
                self.connection.close()
            self.connection = None
            raise ValueError('The native provider connection could not start.') from exc

    def snapshot(self):
        with self.lock:
            return deepcopy(self.value)

    def check(self):
        with self.operation:
            try:
                self._ensure()
                raw = self._rpc('account/read', {'refreshToken': False})
                account = raw.get('account')
                signed_in = isinstance(account, dict) and account.get('type') in ('chatgpt', 'apiKey', 'amazonBedrock')
                # Account email, account IDs, plan metadata and unexpected fields are discarded.
                value = {
                    'authentication': 'signed_in' if signed_in else 'sign_in_required',
                    'checkedAt': _now(),
                    'models': [],
                    'usageWindows': [],
                    'usageScope': 'account_allowance',
                }
                if signed_in:
                    reviewed = set(json.loads(routing_path().read_text()).get('reviewed_codex_models', []))
                    catalog = self._rpc('model/list', {'limit': 100, 'includeHidden': False})
                    rows = catalog.get('data', [])
                    if not isinstance(rows, list):
                        raise ValueError('The native provider returned an invalid model catalog.')
                    value['models'] = [
                        model_id for row in rows if isinstance(row, dict)
                        and not row.get('hidden')
                        and isinstance((model_id := row.get('model') or row.get('id')), str)
                        and model_id in reviewed
                    ]
                    value['message'] = 'Native sign-in found. Reviewed models loaded; execution access is checked when work starts.'
                    try:
                        quota = self._rpc('account/rateLimits/read', {})
                        if isinstance(quota, dict):
                            value['usageWindows'] = _usage_windows(quota)
                    except ValueError:
                        value['usageWindows'] = []
                else:
                    value['message'] = 'Sign in with your provider to continue.'
                with self.lock:
                    # A status check must not erase an in-progress native login.
                    if self.login_id and not signed_in:
                        return deepcopy(self.value)
                    self.value = value
                return deepcopy(value)
            except Exception as exc:
                with self.lock:
                    if not self.login_id:
                        self.value = {
                            'authentication': 'connection_failed',
                            'checkedAt': _now(),
                            'models': [],
                            'usageWindows': [],
                            'usageScope': 'account_allowance',
                            'message': 'Native provider connection check failed. Try again.',
                        }
                raise ValueError('Native provider connection check failed. Try again.') from exc

    def list_tasks(self, **filters):
        from native_tasks import list_tasks
        with self.operation:
            self._ensure()
            return list_tasks(self._rpc, **filters)

    def read_task(self, thread_id):
        from native_tasks import read_task
        with self.operation:
            self._ensure()
            return read_task(self._rpc, thread_id)

    def connect(self):
        with self.operation:
            if self.login_id:
                return self.snapshot()
            status = self.check()
            if status['authentication'] == 'signed_in':
                return status
            result = self._rpc('account/login/start', {'type': 'chatgpt'})
            url = result.get('authUrl', '')
            login_id = result.get('loginId')
            valid_login_id = isinstance(login_id, str) and bool(login_id) and len(login_id) <= 512
            if not valid_login_id or not _official_auth_url(url):
                if valid_login_id:
                    self._rpc('account/login/cancel', {'loginId': login_id})
                    with self.lock:
                        self.cancelled_login_ids.append(login_id)
                        self.login_results.pop(login_id, None)
                        self.value = {'authentication': 'sign_in_failed', 'message': 'The provider returned an unsupported sign-in response.'}
                raise ValueError('The provider returned an unsupported sign-in address.')
            with self.lock:
                self.login_id = login_id
                self.value = {'authentication': 'signing_in', 'authUrl': url, 'message': 'Complete sign-in in your browser, then return here.'}
                if self.login_id in self.login_results:
                    success = self.login_results.pop(self.login_id)
                    self.login_id = None
                    self.value = {'authentication': 'signed_in' if success else 'sign_in_failed', 'message': 'Sign-in completed. Check connection to load models.' if success else 'Sign-in did not complete.'}
            return self.snapshot()

    def cancel(self):
        with self.operation:
            if self.login_id:
                login_id = self.login_id
                self._rpc('account/login/cancel', {'loginId': login_id})
                with self.lock:
                    self.cancelled_login_ids.append(login_id)
                    self.login_results.pop(login_id, None)
                    self.login_id = None
                    self.value = {'authentication': 'not_checked', 'message': 'Sign-in cancelled.'}
            return self.snapshot()

    def close(self):
        if self.connection:
            self.connection.close()


class ProviderConnections:
    def __init__(self, auth=None):
        self.auth = auth or CodexSignIn()
        from claude_connection import ClaudeConnection
        self.claude = ClaudeConnection()
        from native_provider_connection import NativeProviderConnection
        self.native = {key:NativeProviderConnection(key) for key in ("kimi","zai")}
        self.activity = deque(maxlen=60)
        self.lock = threading.RLock()

    def _record(self, provider, message, status='completed'):
        with self.lock:
            self.activity.append({'provider': provider, 'message': message, 'status': status, 'time': _now()})

    def snapshot(self):
        snapshot = deepcopy(_inventory())
        from deepseek_connection import connection as deepseek_connection
        snapshot['providers'].append({'id':'deepseek','label':'DeepSeek','installed':True, 'desktopInstalled':False,'cliInstalled':False, **deepseek_connection().snapshot()})
        from openai_compatible_connection import connection as custom_connection
        snapshot['providers'].append({'id':'openai-compatible','label':'Custom API','installed':True,
            'desktopInstalled':False,'cliInstalled':False,'reason':'User-configured OpenAI-compatible text endpoint.',
            **custom_connection().snapshot()})
        with self.lock:
            activity = list(self.activity)
        for row in snapshot['providers']:
            desktop_installed = bool(row.get('desktopPath'))
            row['helpUrl'] = HELP_URLS.get(row['id'])
            row['activity'] = [item for item in activity if item['provider'] == row['id']][-10:]
            if row['id'] == 'codex':
                row.update(self.auth.snapshot())
            elif row['id'] == 'claude':
                from provider_setup import setup
                from claude_runtime import claude_binary
                binary=claude_binary()
                claude_snapshot = self.claude.snapshot()
                row.update(claude_snapshot)
                row['installed']=bool(desktop_installed or row.get('installed') or binary)
                row['runtimeReady']=bool(binary) and claude_snapshot.get('runtimeReady', True)
                if binary: row['cliPath']=binary
                row['reason']='Claude Code runtime detected. Sign in to load available models.' if binary else 'Claude Desktop is separate from Claude Code. Set up Claude Code to use it in HQ.'
                row['setup'] = setup().snapshot()
            elif row['id'] in self.native:
                native_snapshot = self.native[row['id']].snapshot()
                row.update(native_snapshot)
                import importlib
                module=importlib.import_module('kimi_runtime' if row['id']=='kimi' else 'zcode_runtime')
                binary=module.kimi_binary() if row['id']=='kimi' else module.zcode_command()
                row['installed']=bool(desktop_installed or row.get('installed') or binary)
                row['runtimeReady']=bool(binary) and native_snapshot.get('runtimeReady', True)
                if binary: row['cliPath']=binary[0] if isinstance(binary,list) else binary
                row['reason']=('Native provider runtime detected. Check sign-in to load available models.' if row['runtimeReady']
                               else 'Desktop app detected, but a compatible HQ runtime is not available.' if desktop_installed
                               else 'No compatible HQ runtime was found.')
            # File locations remain server-side implementation details.
            row['desktopInstalled'] = bool(row.pop('desktopPath', None))
            row['cliInstalled'] = bool(row.pop('cliPath', None))
        return snapshot

    def list_tasks(self, **filters):
        if demo_mode():
            raise ValueError('Provider task browsing is disabled in demo mode.')
        return self.auth.list_tasks(**filters)

    def read_task(self, thread_id):
        if demo_mode():
            raise ValueError('Provider task browsing is disabled in demo mode.')
        return self.auth.read_task(thread_id)

    def action(self, provider, action, *, api_key=None, base_url=None, model=None, temperature=None, context_hint=None, approved=False):
        if demo_mode():
            raise ValueError('Provider connections are disabled in demo mode.')
        if provider not in HELP_URLS or action not in ('connect', 'check', 'open', 'cancel', 'test-generation', 'guide', 'terminal', 'install') or (action == 'test-generation' and provider != 'openai-compatible'):
            raise ValueError('Unknown provider connection action.')
        try:
            if action == 'install':
                if provider != 'claude': raise ValueError('Automatic installation is not reviewed for this provider.')
                from provider_setup import setup
                return {'setup': setup().start(approved)}
            if action in ('guide', 'terminal'):
                if provider not in SETUP_URLS or sys.platform != 'darwin':
                    raise ValueError('Open the setup guide or Terminal manually on this device.')
                command = ['/usr/bin/open', SETUP_URLS[provider]] if action == 'guide' else ['/usr/bin/open', '-a', 'Terminal']
                subprocess.run(command, check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {'message': 'Setup guide opened in your browser.' if action == 'guide' else 'Terminal opened. Copy the command shown in HQ and run it there.'}
            if provider == 'openai-compatible':
                from openai_compatible_connection import connection
                if action == 'open': raise ValueError('Enter the endpoint address in Company HQ settings.')
                result = (connection().connect(base_url=base_url, model=model, api_key=api_key,
                    temperature=temperature, context_hint=context_hint) if action == 'connect'
                    else getattr(connection(), {'test-generation':'test_generation'}.get(action,action))())
                self._record(provider, result.get('message','Connection checked'), result.get('authentication','completed'))
                return result
            if provider == 'deepseek':
                from deepseek_connection import connection
                if action == 'open': raise ValueError('Open the DeepSeek API platform to create a key.')
                result = connection().connect(api_key) if action == 'connect' else getattr(connection(), action)()
                self._record(provider, result.get('message','Connection checked'), result.get('authentication','completed'))
                return result
            rows = _inventory()['providers']
            row = next((item for item in rows if item['id'] == provider), None)
            if not row:
                raise ValueError('Provider is not available.')
            if action == 'connect' and provider in ('claude', 'kimi', 'zai'):
                current = next(item for item in self.snapshot()['providers'] if item['id'] == provider)
                if not current['runtimeReady']:
                    raise ValueError(f'{current["label"]} runtime is not ready for Company HQ. Check setup, then retry.')
            if provider in self.native and action != 'open':
                result=getattr(self.native[provider],action)()
                self._record(provider,result.get('message','Connection checked'),result.get('authentication','completed'))
                return result
            if provider == 'claude' and action != 'open':
                result=getattr(self.claude,action)()
                self._record(provider,result.get('message','Connection checked'),result.get('authentication','completed'))
                return result
            if provider == 'codex' and action != 'open':
                result = getattr(self.auth, {'connect': 'connect', 'check': 'check', 'cancel': 'cancel'}[action])()
                self._record(provider, result.get('message', 'Connection checked'), result.get('authentication', 'completed'))
                return result
            if action == 'open':
                path = Path(row.get('desktopPath') or '')
                if sys.platform != 'darwin' or path.suffix != '.app' or not path.is_dir():
                    raise ValueError('No supported installed desktop app was found. Use the provider website.')
                app_path = path.resolve(strict=True)
                subprocess.run(['/usr/bin/open', str(app_path)], check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                message = 'Provider app opened. Its desktop sign-in is separate from the runtime HQ uses for tasks.'
                self._record(provider, message, 'desktop_opened')
                return {'authentication': 'not_checked', 'state': 'desktop_opened', 'message': message}
            message = 'Desktop sign-in stays with the provider. The HQ execution adapter is not connected yet.'
            self._record(provider, message, 'adapter_required')
            return {'authentication': 'not_checked', 'state': 'adapter_required', 'message': message}
        except ValueError:
            self._record(provider, 'Connection step failed. Check the provider and try again.', 'failed')
            raise
        except Exception as exc:
            self._record(provider, 'Connection step failed. Check the provider and try again.', 'failed')
            raise ValueError('Provider connection step failed. Check the provider and try again.') from exc


_connections = ProviderConnections()
atexit.register(_connections.auth.close)
atexit.register(_connections.claude.close)
for _native in _connections.native.values():atexit.register(_native.close)


def connections():
    return _connections
