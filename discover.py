#!/usr/bin/env python3
"""Discover installed clients and the native model catalog without launching model work."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time
import sys

BASE = Path(__file__).resolve().parent
INTEGRATION = BASE / "clawteam" / "integration"
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
from runtime_config import capabilities_path
TTL = 24 * 60 * 60
CLIENTS = {'codex': ('codex',), 'claude': ('claude',), 'cursor': ('cursor-agent', 'agent'),
           'kimi': ('kimi',), 'opencode': ('opencode',), 'grok': ('grok',), 'glm': ('glm',),
           'ollama': ('ollama',)}


def save(path, obj):
    fd, tmp = tempfile.mkstemp(prefix='.discovery-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(obj, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def codex_models(executable):
    # No account/read, turn/start, third-party proxy, or authentication-file reads.
    process = subprocess.Popen([executable, 'app-server', '--listen', 'stdio://'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    def send(value):
        process.stdin.write(json.dumps(value) + '\n'); process.stdin.flush()
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'agent-toolkit-discovery', 'version': '1'}}})
        deadline = time.monotonic() + 12
        rows = []; pages = 0
        while time.monotonic() < deadline:
            if not selector.select(.25):
                if process.poll() is not None: break
                continue
            line = process.stdout.readline()
            if not line: break
            value = json.loads(line)
            if 'error' in value: raise ValueError('Native model discovery returned an error')
            if value.get('id') == 1:
                send({'id': 2, 'method': 'model/list', 'params': {'limit': 100, 'includeHidden': False}})
            elif value.get('id') == 2:
                result = value['result']; pages += 1
                for row in result['data']:
                    if row.get('hidden'): continue
                    model = row.get('model') or row.get('id')
                    if not isinstance(model, str) or not model.strip() or len(model) > 200: continue
                    rows.append({key: row.get(key) for key in ('id', 'model', 'displayName', 'description',
                                      'isDefault', 'upgrade', 'defaultReasoningEffort', 'supportedReasoningEfforts')})
                cursor = result.get('nextCursor')
                if not cursor: return rows
                if pages >= 5: raise ValueError('Native catalog exceeds bounded pagination limit')
                send({'id': 2, 'method': 'model/list', 'params': {'limit': 100, 'includeHidden': False, 'cursor': cursor}})
        raise ValueError('Native model discovery unavailable or timed out')
    finally:
        selector.close(); process.terminate()
        try: process.communicate(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.communicate()


def select_supervisor(policy, capabilities):
    for preferred in policy['preferred_supervisors']:
        provider = preferred['provider']
        client = capabilities['providers'].get(provider, {})
        if client.get('status') != 'catalog_verified': continue
        models = {r.get('model') or r['id']: r for r in client['models']}
        selected = preferred['model']; chain = []
        while selected in models and policy.get('follow_official_upgrade_hint'):
            hint = models[selected].get('upgrade')
            if not isinstance(hint, str) or hint not in models or hint in chain or hint == selected: break
            chain.append(selected); selected = hint
        if selected not in models: continue
        supported = [e['reasoningEffort'] for e in models[selected].get('supportedReasoningEfforts', [])]
        effort = preferred.get('effort', 'high')
        if effort not in supported: effort = models[selected].get('defaultReasoningEffort')
        return {'provider': provider, 'model': selected, 'effort': effort,
                'basis': 'official runtime upgrade hint' if chain else 'reviewed available supervisor',
                'upgraded_from': chain, 'reviewed_on': policy.get('reviewed_on')}
    return {'provider': None, 'model': None, 'effort': None,
            'basis': 'No reviewed supervisor is currently available; review the catalog before launching.'}


def discover(refresh=False, base=BASE):
    policy = json.loads((base / 'routing.json').read_text())
    paths = {provider: next((shutil.which(name) for name in names if shutil.which(name)), None)
             for provider, names in CLIENTS.items()}
    resolved_base = Path(base).resolve()
    cache = capabilities_path() if resolved_base == BASE.resolve() else resolved_base / "capabilities.json"
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700); now = time.time()
    if not refresh:
        try:
            value = json.loads(cache.read_text())
            if 0 <= now - value['checked_unix'] < TTL and value['client_paths'] == paths:
                selection = select_supervisor(policy, value)
                known = set(policy.get('reviewed_codex_models', []))
                unreviewed = [r.get('model') or r['id'] for r in value['providers']['codex']['models']
                              if (r.get('model') or r['id']) not in known]
                changed = selection != value.get('selection') or unreviewed != value.get('unreviewed_codex_models')
                value['selection'] = selection
                value['unreviewed_codex_models'] = unreviewed
                value['cached'] = True
                if changed: save(cache, value)
                return value
        except (OSError, ValueError, KeyError, TypeError): pass
    providers = {}
    for provider, executable in paths.items():
        entry = {'executable': executable, 'status': 'client_detected' if executable else 'not_installed',
                 'models': [], 'authentication': 'not_checked'}
        if provider == 'codex' and executable:
            try:
                entry['models'] = codex_models(executable); entry['status'] = 'catalog_verified'
            except (OSError, ValueError, KeyError, TypeError) as exc:
                entry['status'] = 'discovery_unavailable'; entry['error'] = str(exc)[:300]
        elif executable:
            entry['integration'] = 'Client presence only; execution/model discovery not verified by this adapter.'
        providers[provider] = entry
    value = {'schema': 1, 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
             'checked_unix': now, 'client_paths': paths, 'providers': providers,
             'desktop_only': ['Grok Bot'] if Path('/Applications/Grok Bot.app').exists() else [], 'cached': False}
    known = set(policy.get('reviewed_codex_models', []))
    value['unreviewed_codex_models'] = [r.get('model') or r['id'] for r in providers['codex']['models']
                                        if (r.get('model') or r['id']) not in known]
    value['selection'] = select_supervisor(policy, value)
    save(cache, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args(); value = discover(args.refresh)
    result = value if args.full else {key: value[key] for key in ('checked_at', 'cached', 'selection', 'unreviewed_codex_models', 'desktop_only')}
    if not args.full: result['providers'] = {p: r['status'] for p, r in value['providers'].items()}
    print(json.dumps(result, indent=2))
    return 0 if value['selection'].get('model') else 1


if __name__ == '__main__':
    raise SystemExit(main())
