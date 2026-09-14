#!/usr/bin/env python3
"""Open the untouched upstream app for an offline, account-isolated UI preview."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/Users/uno/.local/share/agent-toolkit')
STATE = ROOT / 'state/agent-teams'
APP = ROOT / 'apps/agent-teams-ai/2.14.2/upstream/Agent Teams AI.app'

def main():
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(APP)], check=True)
    for folder in ('claude', 'user-data'):
        (STATE / folder).mkdir(parents=True, exist_ok=True, mode=0o700)
    config = STATE / 'claude/agent-teams-config.json'
    if not config.exists():
        config.write_text(json.dumps({'general': {'telemetryEnabled': False, 'launchAtLogin': False}}))
        config.chmod(0o600)
    protected = [
        '/Users/uno/.codex', '/Users/uno/.claude', '/Users/uno/.claude.json',
        '/Users/uno/.cursor', '/Users/uno/.config/opencode',
        '/Users/uno/.local/share/opencode', '/Users/uno/.ssh',
        '/Users/uno/.aws', '/Users/uno/.config/gcloud',
        '/Users/uno/Library/Keychains', '/Users/uno/Library/Application Support/Cursor',
        '/Users/uno/Downloads', '/Users/uno/Documents', '/Users/uno/Desktop',
    ]
    profile = '(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'
    for path in (str(STATE), '/private/tmp', '/private/var/folders'):
        profile += '(allow file-write* (subpath ' + json.dumps(path) + '))\n'
    profile += '(allow file-write* (literal "/dev/null"))\n'
    for path in protected:
        profile += '(deny file-read* file-write* (subpath ' + json.dumps(path) + '))\n'
    profile_path = STATE / 'offline-preview.sb'
    profile_path.write_text(profile)
    profile_path.chmod(0o600)
    # Deliberately omit inherited credentials and client overrides. Never change HOME/CODEX_HOME.
    env = {key: os.environ[key] for key in ('LANG', 'LC_ALL', 'TMPDIR', 'USER', 'LOGNAME') if key in os.environ}
    env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',
               AGENT_TEAMS_ELECTRON_USER_DATA_DIR=str(STATE / 'user-data'),
               AGENT_TEAMS_ELECTRON_CLAUDE_ROOT=str(STATE / 'claude'))
    command = ['/usr/bin/sandbox-exec', '-f', str(profile_path), str(APP / 'Contents/MacOS/Agent Teams AI')]
    with (STATE / 'offline-preview.log').open('ab') as log:
        process = subprocess.Popen(command, cwd=STATE, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    print(json.dumps({'pid': process.pid, 'mode': 'offline UI preview; no provider connection', 'log': str(STATE / 'offline-preview.log')}))

if __name__ == '__main__':
    main()
