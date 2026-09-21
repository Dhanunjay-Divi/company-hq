"""Read-only projection of the tools this particular native runtime exposes."""
from datetime import datetime, timezone
from pathlib import Path


def inventory(rpc, thread_id: str, project: str, repo: Path) -> dict:
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'servers': [],
              'apps': [], 'skills': [], 'errors': [], 'truncated': False}
    try:
        cursor = None
        seen_cursors = set()
        for _ in range(10):
            params = {'threadId': thread_id, 'limit': 100, 'detail': 'toolsAndAuthOnly'}
            if cursor: params['cursor'] = cursor
            page = rpc('mcpServerStatus/list', params)
            if not isinstance(page, dict):
                raise ValueError('MCP response was not an object')
            for server in page.get('data', []) or []:
                if not isinstance(server, dict):
                    continue
                raw_tools = server.get('tools')
                tools = sorted(key for key in (raw_tools or {}) if isinstance(key, str)) if isinstance(raw_tools, dict) else []
                result['servers'].append({
                    'name': server.get('name', 'Unnamed'), 'authStatus': server.get('authStatus'),
                    'runtimeStatus': server.get('runtimeStatus'), 'tools': tools[:300],
                    'toolsError': bool(server.get('toolsError')),
                })
                result['truncated'] |= len(tools) > 300
            next_cursor = page.get('nextCursor')
            if not next_cursor: break
            if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
                result['truncated'] = True
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else: result['truncated'] = True
    except Exception:
        result['errors'].append({'source': 'MCP', 'message': 'The runtime could not report its MCP tools.'})
    try:
        response = rpc('app/installed', {'threadId': thread_id, 'forceRefresh': False})
        if not isinstance(response, dict):
            raise ValueError('Apps response was not an object')
        result['apps'] = [
            {'id': row['id'], 'name': row.get('runtimeName') or row['id'],
             'enabled': row.get('enabled') is True, 'callable': row.get('callable') is True}
            for row in response.get('apps', [])[:300] if isinstance(row, dict) and isinstance(row.get('id'), str)
        ]
        result['truncated'] |= len(response.get('apps', []) or []) > 300
    except Exception:
        result['errors'].append({'source': 'Apps', 'message': 'Installed app tools were not reported by this runtime.'})
    try:
        response = rpc('skills/list', {'cwds': [project], 'forceReload': False})
        if not isinstance(response, dict):
            raise ValueError('Skills response was not an object')
        skills = {}
        for entry in response.get('data', []) or []:
            if not isinstance(entry, dict):
                continue
            for row in entry.get('skills', []) or []:
                if not isinstance(row, dict):
                    continue
                name = row.get('name')
                if isinstance(name, str):
                    skills[name] = {'name': name, 'description': str(row.get('description', ''))[:600], 'enabled': row.get('enabled') is True}
            if entry.get('errors'):
                result['errors'].append({'source': 'Skills', 'message': 'Some skill files could not be read.'})
        result['skills'] = list(skills.values())[:500]
        result['truncated'] |= len(skills) > 500
    except Exception:
        result['errors'].append({'source': 'Skills', 'message': 'Skills were not reported by this runtime.'})
    library = repo / 'agency-agents' / 'upstream'
    areas = ('design', 'engineering', 'marketing', 'product', 'project-management', 'testing', 'support', 'specialized',
             'research', 'paid-media', 'sales', 'security', 'spatial-computing', 'healthcare', 'academic', 'finance',
             'game-development', 'gis')
    roles = [file for area in areas for file in (library / area).rglob('*.md')]
    result['roleLibrary'] = {'available': library.is_dir(), 'count': len(roles),
                             'description': 'Pinned specialist guidance, selected on demand. These are role references, not running agents.'}
    return result
