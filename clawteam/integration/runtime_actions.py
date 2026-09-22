"""User-initiated native commands and project-scoped evidence, without model calls."""
import os
from pathlib import Path
import shlex
from urllib.parse import urlparse

from context_pipeline import ContextPipeline
from runtime_config import REPO_ROOT, demo_mode


def pipeline(state):
    return ContextPipeline(state, rtk_path=REPO_ROOT / 'build/tools' / ('rtk.exe' if os.name == 'nt' else 'rtk'),
        graphify_python=REPO_ROOT / 'build/graphify-venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))


def command(bridge, state, team, text):
    if demo_mode(): raise ValueError('Commands are disabled in demo mode.')
    if not isinstance(text, str) or not text.strip() or len(text) > 8000: raise ValueError('Enter a command of at most 8000 characters.')
    session = bridge._require_session(team)
    with session.operation_lock:
        if not session.connection.running(): raise ValueError('Connect the native runtime before running a command.')
        mode = session.mode
        policy = {'type': 'dangerFullAccess'} if mode == 'full' else {'type': 'readOnly'} if mode == 'plan' else {
            'type': 'workspaceWrite', 'writableRoots': [str(session.project)], 'networkAccess': False}
        argv = ['cmd.exe', '/c', text] if os.name == 'nt' else ['/bin/sh', '-c', text]
        # thread/shellCommand deliberately runs unsandboxed. Use command/exec
        # with an explicit policy derived from the chat's persisted access mode.
        value = bridge._rpc(session, 'command/exec', {'command': argv, 'cwd': str(session.project),
            'sandboxPolicy': policy, 'timeoutMs': 20000, 'outputBytesCap': 512 * 1024})
        if not isinstance(value.get('exitCode'), int) or any(not isinstance(value.get(k), str) for k in ('stdout', 'stderr')):
            raise ValueError('The runtime did not return command evidence.')
        try: hint = shlex.split(text)
        except ValueError: hint = argv
        evidence = pipeline(state).record(team, str(session.project), {'command': hint, 'stdout': value['stdout'],
            'stderr': value['stderr'], 'exit_code': value['exitCode']})
        output = evidence.compact if evidence.compact is not None else (value['stdout'] + value['stderr'])[-32000:]
        bridge._event(session, 'command.evidence', {'text': f'Command finished with exit {value["exitCode"]}',
            'evidenceId': evidence.id, 'exitCode': value['exitCode']})
        return {'exitCode': value['exitCode'], 'output': output, 'evidenceId': evidence.id,
            'truncated': evidence.raw_truncated or len(value['stdout']) >= 512 * 1024 or len(value['stderr']) >= 512 * 1024 or len(output) < evidence.raw_bytes,
            'filter': evidence.rtk, 'rawBytes': evidence.raw_bytes, 'compactBytes': evidence.compact_bytes}


def evidence(state, team, project, record_id=None, offset=0):
    service = pipeline(state)
    if record_id: return service.raw(team, project, record_id, offset=offset, limit=16000)
    return service.recall(team, project, cursor=offset, limit=20)


def tool_action(bridge, team, action, name, enabled=None):
    if demo_mode(): raise ValueError('Tool settings cannot be changed in demo mode.')
    if not isinstance(name, str) or not 0 < len(name) <= 200: raise ValueError('Choose a reported runtime tool.')
    session = bridge._require_session(team)
    inventory = bridge.tools(team)
    with session.operation_lock:
        if action == 'sign-in':
            rows = [row for row in inventory.get('servers', []) if row.get('name') == name]
            if len(rows) != 1: raise ValueError('This server was not reported by the connected runtime.')
            value = bridge._rpc(session, 'mcpServer/oauth/login', {'name': name, 'threadId': session.thread_id, 'timeoutSecs': 300})
            url = value.get('authorizationUrl')
            parsed = urlparse(url if isinstance(url, str) else '')
            if parsed.username or parsed.password or not parsed.hostname or not (parsed.scheme == 'https' or parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1','localhost','::1'}):
                raise ValueError('The runtime did not provide a valid sign-in link.')
            return {'authorizationUrl': url, 'message': 'Finish sign-in in the provider window, then refresh tools.'}
        if action == 'skill':
            if not isinstance(enabled, bool) or sum(row.get('name') == name for row in inventory.get('skills', [])) != 1:
                raise ValueError('Choose one installed skill and whether to enable it.')
            bridge._rpc(session, 'skills/config/write', {'name': name, 'enabled': enabled})
            return {'updated': True, 'message': 'Native skill setting updated. Refresh the list; a new turn may be needed.'}
        raise ValueError('Unsupported tool setting.')
