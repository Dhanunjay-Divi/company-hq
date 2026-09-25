"""Bind reviewed shared memory and code tools to a native HQ session."""
import os
import sys
import hashlib
from pathlib import Path
from runtime_config import ruflo_launcher, codebase_memory_launcher, state_root, node_executable, component_state_root, python_executable
from project_context import validate_team

def servers(project, team=None, access=None):
    root=str(Path(project).resolve(strict=True))
    values={'COMPANY_HQ_STATE_ROOT':str(state_root()),'RUFLO_PROJECT_ROOT':root}
    node=node_executable()
    if node:values['COMPANY_HQ_NODE']=str(node)
    result=[]
    for name,command in [('ruflo',ruflo_launcher()),('codebase_memory',codebase_memory_launcher())]:
        if command.is_file() and os.access(command,os.X_OK):
            env=dict(values)
            # The macOS code guard requires storage outside the account home.
            if name=='codebase_memory':
                project_key=hashlib.sha256(root.encode()).hexdigest()
                env['COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT']=str(component_state_root('codebase-memory')/'projects'/project_key)
                env['COMPANY_HQ_CONTEXT_PROJECT']=root
            result.append({'name':name,'command':str(command),'args':[],'env':[{'name':k,'value':v} for k,v in env.items()]})
    if team is not None:
        validated = validate_team(team)
        python = python_executable()
        entry = Path(__file__).with_name('project_context_mcp.py')
        env = {**values, "COMPANY_HQ_CONTEXT_PROJECT": root, "COMPANY_HQ_CONTEXT_TEAM": validated}
        for key in ('CLAWTEAM_INTEGRATION_TESTING', 'CLAWTEAM_INTEGRATION_TEST_DATA_DIR'):
            if os.environ.get(key): env[key] = os.environ[key]
        if getattr(sys, 'frozen', False):
            # The frozen entry is provided by the desktop build; do not depend
            # on a separately installed Python runtime.
            result.append({'name':'contextMCP','command':sys.executable,'args':['--project-context-mcp',root,validated],'env':[{'name':k,'value':v} for k,v in env.items()]})
        elif python.is_file() and os.access(python, os.X_OK) and entry.is_file():
            result.append({'name':'contextMCP','command':str(python),'args':[str(entry)],'env':[{'name':k,'value':v} for k,v in env.items()]})
    return result
