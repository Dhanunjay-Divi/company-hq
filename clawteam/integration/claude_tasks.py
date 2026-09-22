"""Explicit read-only Claude Code metadata through its official SDK."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from runtime_config import REPO_ROOT, demo_mode, node_executable


def _call(payload):
    if demo_mode():raise ValueError('Provider task browsing is disabled in demo mode.')
    sdk=REPO_ROOT/'build/providers/claude-agent-sdk/node_modules/@anthropic-ai/claude-agent-sdk/sdk.mjs'
    node=node_executable()
    if not node or not sdk.is_file():raise ValueError('Claude task metadata needs the reviewed Claude Agent SDK and Node runtime.')
    try:
        process=subprocess.run([str(node),str(Path(__file__).with_suffix('.mjs')),str(sdk),json.dumps(payload)],capture_output=True,text=True,timeout=20,check=True)
        if len(process.stdout)>512000:raise ValueError('Provider task response is too large.')
        return json.loads(process.stdout)
    except (OSError,subprocess.SubprocessError,json.JSONDecodeError):raise ValueError('Claude task metadata could not be read.') from None


def list_tasks(cursor=None,search='',archived=False,include_agents=False):
    if cursor is not None and (not isinstance(cursor,str) or not re.fullmatch(r'\d{1,7}',cursor)):raise ValueError('Invalid task cursor.')
    if not isinstance(search,str) or len(search)>200 or not isinstance(include_agents,bool):raise ValueError('Invalid filters.')
    if archived:raise ValueError('Claude Code does not report an archive filter through this SDK.')
    return _call({'action':'list','offset':int(cursor or 0),'search':search,'includeAgents':include_agents})


def read_task(task_id):
    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task_id):raise ValueError('Invalid task ID.')
    return _call({'action':'read','id':task_id})
