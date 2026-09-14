"""Validated, project-local presentation metadata; never agent liveness."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def profile_path(state: Path, team: str) -> Path:
    return state / 'company-profiles' / (hashlib.sha256(team.encode()).hexdigest() + '.json')


def validate_profile(value: object, names: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ValueError('Company profile must be an object')
    result = {}
    for key in ('projectLabel', 'goal'):
        item = value.get(key, '')
        if not isinstance(item, str) or len(item) > 2000:
            raise ValueError(f'{key} must be text of at most 2000 characters')
        result[key] = item
    project = value.get('projectRoot', '')
    if not isinstance(project, str) or len(project) > 4096:
        raise ValueError('Project folder must be an absolute path')
    if project and not Path(project).is_absolute():
        raise ValueError('Project folder must be an absolute path')
    result['projectRoot'] = project
    entries = value.get('members', {})
    if not isinstance(entries, dict) or not set(entries).issubset(names):
        raise ValueError('Company profile must reference registered members only')
    result['members'] = {}
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError('Each member profile must be an object')
        clean = {}
        for key in ('displayName', 'department', 'model'):
            item = entry.get(key, '')
            if not isinstance(item, str) or len(item) > 200:
                raise ValueError(f'{key} must be short text')
            clean[key] = item
        parent = entry.get('reportsTo')
        if parent is not None and (not isinstance(parent, str) or parent not in names or parent == name):
            raise ValueError('Reporting supervisor must be a different registered member')
        clean['reportsTo'] = parent
        result['members'][name] = clean
    for name in entries:
        seen = {name}
        parent = result['members'][name]['reportsTo']
        while parent is not None:
            if parent in seen:
                raise ValueError('Reporting hierarchy contains a cycle')
            seen.add(parent)
            parent = result['members'].get(parent, {}).get('reportsTo')
    return result


def load_profile(state: Path, team: str, names: set[str]) -> dict:
    path = profile_path(state, team)
    if not path.exists():
        return {'members': {}, 'projectLabel': team, 'goal': ''}
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('Company profile must be a regular small local file')
    return validate_profile(json.loads(path.read_text()), names)
