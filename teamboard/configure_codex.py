#!/usr/bin/env python3
"""Install economical native Codex defaults and personal roles, outside product repos."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib
import sys

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent
INTEGRATION = REPO_ROOT / "clawteam" / "integration"
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
from runtime_config import capabilities_path  # noqa: E402
CODEX_DIR = Path.home() / '.codex'
DEFAULTS = {
    'default_subagent_model': 'gpt-5.6-terra',
    'default_subagent_reasoning_effort': 'medium',
    'max_concurrent_threads_per_session': 3,
}
ROLES = {
    'team-scout': ('gpt-5.6-luna', 'low', 'Narrow read-only search, inventory, or document extraction.',
                   'Return relevant paths, concise findings and unknowns. Do not change files or delegate further.'),
    'team-builder': ('gpt-5.6-terra', 'medium', 'Bounded implementation with clear ownership and acceptance criteria.',
                    'Own only assigned paths. Follow the project instructions. Verify changed behavior and report actual results. Do not delegate further.'),
    'team-reviewer': ('gpt-5.6-sol', 'high', 'Independent review of complex correctness, security or release-sensitive changes.',
                     'Inspect the implementation and test evidence. Report reproducible serious findings and unverified gates. Do not change product files or delegate further.'),
}


def set_key(text, section, key, value):
    """Replace one scalar key in an exact table, preserving all unrelated TOML bytes."""
    headings = list(re.finditer(r'^\s*\[[^\n]+\]\s*(?:#.*)?$', text, re.M))
    if section is None:
        start, end = 0, headings[0].start() if headings else len(text)
    else:
        match = next((h for h in headings if h.group().strip().split('#', 1)[0].strip() == f'[{section}]'), None)
        if match is None:
            return text.rstrip() + f'\n\n[{section}]\n{key} = {json.dumps(value)}\n'
        start = match.end()
        end = next((h.start() for h in headings if h.start() > match.start()), len(text))
    block = text[start:end]
    pattern = re.compile(r'^(\s*)' + re.escape(key) + r'\s*=.*$', re.M)
    if pattern.search(block):
        block = pattern.sub(lambda m: f'{m.group(1)}{key} = {json.dumps(value)}', block, count=1)
    else:
        block = block.rstrip() + f'\n{key} = {json.dumps(value)}\n\n'
    return text[:start] + block + text[end:]


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.team-install-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def apply_locked():
    config = CODEX_DIR / 'config.toml'
    if config.is_symlink():
        raise RuntimeError('Refusing to replace a symlinked config.toml; preserve its external configuration management')
    original = config.read_bytes() if config.exists() else b''
    before = tomllib.loads(original.decode())
    # Use a fresh verified discovery selection when available. The fallback is
    # the last reviewed Codex preference, not an inference from version numbers.
    lead_model, lead_effort = 'gpt-6-astra', 'high'
    policy_file = BASE.parent / 'routing.json'
    if policy_file.exists():
        policy = json.loads(policy_file.read_text())
        choice = next((r for r in policy['preferred_supervisors'] if r['provider'] == 'codex'), None)
        if choice is None: raise RuntimeError('No reviewed Codex supervisor in routing.json')
        lead_model, lead_effort = choice['model'], choice.get('effort', 'high')
    try:
        capabilities = json.loads(capabilities_path().read_text())
        choice = capabilities['selection']
        if 0 <= time.time() - capabilities['checked_unix'] < 86400 and choice['provider'] == 'codex' and choice['model'] and choice['effort']:
            lead_model, lead_effort = choice['model'], choice['effort']
    except (OSError, ValueError, KeyError, TypeError): pass
    updated = set_key(original.decode(), None, 'model', lead_model)
    updated = set_key(updated, None, 'model_reasoning_effort', lead_effort)
    for key, value in DEFAULTS.items():
        updated = set_key(updated, 'agents', key, value)
    after = tomllib.loads(updated)
    expected = dict(before)
    expected['model'] = lead_model; expected['model_reasoning_effort'] = lead_effort
    expected['agents'] = {**before.get('agents', {}), **DEFAULTS}
    if after != expected:
        raise RuntimeError('Unexpected TOML change; no settings written')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = BASE / 'backups' / stamp
    role_files = {}
    for name, (model, effort, description, instruction) in ROLES.items():
        text = '# Managed by shared agent-toolkit teamboard/configure_codex.py\n'
        values = dict(name=name, description=description, model=model,
                      model_reasoning_effort=effort,
                      developer_instructions=instruction + ' Report concise progress, actual messages and results to the parent for Team Board recording. Never include secrets or raw customer content.')
        text += ''.join(f'{key} = {json.dumps(value)}\n' for key, value in values.items())
        tomllib.loads(text)
        path = CODEX_DIR / 'agents' / f'{name}.toml'
        if path.exists() and path.read_text() != text:
            raise RuntimeError(f'Existing custom role differs: {path}; preserved for review')
        role_files[path] = text.encode()
    if updated.encode() != original:
        backup.mkdir(parents=True, mode=0o700)
        atomic_write(backup / 'config.toml', original)
        # Refuse to overwrite a change made after our read.
        if config.is_symlink() or (config.exists() and config.read_bytes() != original):
            raise RuntimeError('Codex config changed during installation; retry after reviewing it')
        atomic_write(config, updated.encode(), config.stat().st_mode & 0o777 if config.exists() else 0o600)
    for path, data in role_files.items():
        if not path.exists(): atomic_write(path, data)
    managed = BASE / 'managed-default.json'
    managed_bytes = (json.dumps({'model': lead_model, 'effort': lead_effort}, sort_keys=True) + '\n').encode()
    if not managed.exists() or managed.read_bytes() != managed_bytes:
        atomic_write(managed, managed_bytes)
    print(json.dumps({'model': after['model'], 'agents': after['agents'],
                      'roles': [str(p) for p in role_files],
                      'config_backup': str(backup / 'config.toml') if backup.exists() else None,
                      'project_changes': False}, indent=2))


def apply():
    # Serialize this installer's invocations. Other editors do not honor this
    # advisory lock: avoid simultaneous Settings/file edits during an explicit
    # reinstall. The before-write check detects ordinary observed conflicts,
    # not a filesystem-wide compare-and-swap guarantee.
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(BASE / '.configure.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        apply_locked()


if __name__ == '__main__':
    apply()
