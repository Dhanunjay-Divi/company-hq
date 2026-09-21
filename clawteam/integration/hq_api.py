"""Company HQ adapters over ClawTeam, Ruflo and the native Codex bridge."""
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import json, os, re, select, subprocess, tempfile, threading, time, uuid
from company_profile import load_profile, validate_profile, profile_path
from clawteam.team.manager import TeamManager
from clawteam.team.tasks import TaskStore
from clawteam.team.models import TaskStatus
from runtime_config import (
    demo_mode,
    health_snapshot,
    routing_path,
    ruflo_launcher,
    saved_projects_path,
)
_memory_cache = {}
_memory_lock = threading.Lock()


def project_for(state, name):
    team = TeamManager.get_team(name)
    if team is None: raise ValueError('Workspace not found')
    profile = load_profile(state, name, {m.name for m in team.members})
    project = profile.get('projectRoot')
    if not project: raise ValueError('Attach a project folder before starting work')
    path = Path(project).resolve()
    if not path.is_dir() or path in {Path('/'), Path.home()}: raise ValueError('Select an existing project folder')
    return str(path)


def save_profile(state, name, profile, names):
    value = validate_profile(profile, names)
    path = profile_path(state, name); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.profile-')
    try:
        with os.fdopen(fd, 'w') as f: json.dump(value, f, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return value


def memory_call(project, operations):
    proc = subprocess.Popen([str(ruflo_launcher())], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    seq = 0
    def rpc(method, params):
        nonlocal seq
        seq += 1
        proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':seq,'method':method,'params':params})+'\n');proc.stdin.flush()
        if not select.select([proc.stdout],[],[],15)[0]: raise ValueError('Memory service timed out')
        result = json.loads(proc.stdout.readline())
        if result.get('error') or result.get('result',{}).get('isError'): raise ValueError('Memory service could not complete the request')
        return result.get('result',{})
    def tool(name, args):
        result = rpc('tools/call',{'name':name,'arguments':{**args,'project_root':project}})
        text = ''.join(x.get('text','') for x in result.get('content',[]) if x.get('type')=='text')
        return json.loads(text)
    try:
        rpc('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'company-hq','version':'1'}})
        return operations(tool)
    finally:
        if proc.stdin: proc.stdin.close()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=3)
        if proc.stdout: proc.stdout.close()


def knowledge(project):
    with _memory_lock:
        cached = _memory_cache.get(project)
        if cached and time.monotonic()-cached[0] < 20: return cached[1]
        def read(tool):
            notes = []
            for namespace in ('company-notes','operating-decisions'):
                listed = tool('memory_list',{'namespace':namespace,'limit':15})
                for entry in listed.get('entries',[])[:15]:
                    value = tool('memory_retrieve',{'key':entry['key'],'namespace':namespace})
                    notes.append({**entry,'value':value.get('value',value)})
            return {'notes':notes,'source':'Ruflo','codeGraph':'codebase-memory-mcp','codeGraphNote':'Agents index and query code relationships when useful. Source files remain authoritative.'}
        result = memory_call(project,read);_memory_cache[project]=(time.monotonic(),result);return result


def bridge(state):
    from codex_bridge import get_codex_bridge
    return get_codex_bridge(state / "runtime")


def handle_get(handler, state):
    path = urlparse(handler.path).path
    if path == '/api/health':
        handler._serve_json(health_snapshot(state));return True
    if not path.startswith(('/api/runtime/','/api/knowledge/','/api/workspaces')): return False
    try:
        if path == '/api/workspaces':
            config = saved_projects_path()
            routing=json.loads(routing_path().read_text())
            handler._serve_json({'projects':json.loads(config.read_text()) if config.exists() else [],'models':routing.get('reviewed_codex_models',[]),'demo':demo_mode()});return True
        if path.startswith('/api/knowledge/'):
            name=unquote(path[len('/api/knowledge/'):]);handler._serve_json(knowledge(project_for(state,name)));return True
        parts=path.strip('/').split('/')
        if len(parts)!=4: raise ValueError('Unknown runtime route')
        name=unquote(parts[2]); project_for(state,name)
        if parts[3]=='status': result=bridge(state).status(name)
        elif parts[3]=='events':
            after=int(parse_qs(urlparse(handler.path).query).get('after',['0'])[0]);result=bridge(state).events(name,max(0,after))
        else: raise ValueError('Unknown runtime route')
        handler._serve_json(result)
    except Exception as exc:
        handler._json_error(400,str(exc))
    return True


def handle_post(handler,state,path,body):
    if not path.startswith(('/api/runtime/','/api/knowledge/','/api/workspaces','/api/task/')): return False
    try:
        if not isinstance(body,dict): raise ValueError('Request must be a JSON object')
        if path=='/api/workspaces':
            label=body.get('label','').strip();project=body.get('project','').strip();goal=body.get('goal','').strip()
            if not label or len(label)>120 or len(goal)>2000: raise ValueError('Enter a short project name and goal')
            folder=Path(project).expanduser().resolve()
            if not project or not folder.is_dir() or folder in {Path('/'),Path.home()}: raise ValueError('Choose an existing project folder')
            name=(re.sub('[^a-z0-9-]','-',label.lower()).strip('-')[:40] or 'project')+'-'+uuid.uuid4().hex[:6]
            TeamManager.create_team(name,'overall-head','not-started',description=goal,user='local',leader_agent_type='overall-head')
            profile=save_profile(state,name,{'projectLabel':label,'projectRoot':str(folder),'goal':goal,'members':{'overall-head':{'displayName':'Overall head','department':'Direction & delivery','model':'','reportsTo':None}}},{'overall-head'})
            handler._serve_json({'team':name,'company':profile,'started':False});return True
        parts=path.strip('/').split('/');name=unquote(parts[2]);project=project_for(state,name)
        if parts[1]=='knowledge':
            title=body.get('title','').strip();content=body.get('content','').strip()
            if not title or not content or len(title)>200 or len(content)>12000: raise ValueError('Enter a title and a note of at most 12000 characters')
            key=uuid.uuid4().hex
            memory_call(project,lambda tool:tool('memory_store',{'key':key,'namespace':'company-notes','value':{'title':title,'content':content,'source':'User','date':time.strftime('%Y-%m-%d')},'provenance_type':'user_claim'}))
            _memory_cache.pop(project,None);handler._serve_json({'saved':True,'key':key});return True
        if parts[1]=='task':
            if len(parts)!=4: raise ValueError('Task ID required')
            status=TaskStatus(body.get('status'))
            task=TaskStore(name).update(parts[3],status=status,caller='user')
            if task is None: raise ValueError('Task not found')
            handler._serve_json({'updated':True});return True
        if parts[1]!='runtime' or len(parts)!=4: raise ValueError('Unknown action')
        client=bridge(state);action=parts[3]
        if demo_mode() and action in ('start','send','execute','worker-message','approve'):
            raise ValueError('Model execution is disabled in model-free demo mode')
        if action in ('start','send'):
            prompt=body.get('prompt','')
            if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>24000: raise ValueError('Enter a message of at most 24000 characters')
            if action=='start':
                routing=json.loads(routing_path().read_text());model=body.get('model','auto')
                if model=='auto':model=routing['preferred_supervisors'][0]['model']
                if model not in routing['reviewed_codex_models']: raise ValueError('Choose a reviewed available Codex model')
                mode=body.get('mode','plan')
                if mode not in ('plan','execute'): raise ValueError('Mode must be plan or execute')
                result=client.start(name,project,prompt.strip(),model,mode)
            else:result=client.send(name,prompt.strip())
        elif action=='execute':
            prompt=body.get('prompt') or 'The user approved the current plan. Begin bounded execution now. Reuse relevant context, prefer economical capable workers, and report progress and blockers.'
            result=client.begin_execution(name,prompt)
        elif action=='worker-message':
            worker=body.get('worker','');content=body.get('content','')
            if not isinstance(worker,str) or not worker or not isinstance(content,str) or not content.strip() or len(content)>12000: raise ValueError('Choose a live worker and enter a message of at most 12000 characters')
            result=client.message_worker(name,worker,content.strip())
        elif action=='stop':result=client.stop(name)
        elif action=='approve':result=client.approve(name,body.get('requestId'),body.get('decision'))
        else:raise ValueError('Unknown runtime action')
        handler._serve_json(result)
    except Exception as exc:handler._json_error(400,str(exc))
    return True
