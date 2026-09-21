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
    REPO_ROOT,
    routing_path,
    ruflo_launcher,
    saved_projects_path,
)
_memory_cache = {}
_memory_lock = threading.Lock()


ADDITIONAL_COMPONENTS = [
    {
        "name": "777genius/agent-teams-ai",
        "area": "Graph UI and team workspace reference",
        "decision": "Reuse the licensed graph package and selected UI patterns inside Company HQ.",
        "evidence": "Graph package and avatar source are already vendored with retained notices and source-download support.",
        "boundary": "Do not run the separate desktop app because its runtime/auth behavior was blocked.",
    },
    {
        "name": "ruvnet/ruflo",
        "area": "Coordination and memory",
        "decision": "Keep the reviewed scoped memory adapter; evaluate workflow, cost, observability and routing modules behind Company HQ contracts.",
        "evidence": "Installed restricted MCP wrapper; expanded modules not yet accepted.",
        "boundary": "No autopilot, provider routing, federation, hooks or second scheduler by default.",
    },
    {
        "name": "HKUDS/ClawTeam",
        "area": "Compatibility task and inbox layer",
        "decision": "Use for the current visible board and inbox compatibility until the accepted task-store port replaces it.",
        "evidence": "Current source tests and browser acceptance exercise the ClawTeam-backed routes.",
        "boundary": "Not the permanent canonical DAG if Beads migration passes.",
    },
    {
        "name": "NanmiCoder/dsh-agent-teams",
        "area": "Team-management reference",
        "decision": "Reference only until a concrete UI/backend pattern wins an acceptance test.",
        "evidence": "No current source vendoring or runtime execution in Company HQ.",
        "boundary": "No second scheduler or copied agent runtime.",
    },
    {
        "name": "Orkas-AI/Orkas",
        "area": "Agent orchestration reference",
        "decision": "Reference only for possible workflow ideas.",
        "evidence": "No current source vendoring or runtime execution in Company HQ.",
        "boundary": "No provider routing, auth management or autonomous background workers.",
    },
    {
        "name": "bradygaster/squad",
        "area": "Team orchestration reference",
        "decision": "Reference only; compare against Company HQ worker lifecycle before adoption.",
        "evidence": "No current source vendoring or runtime execution in Company HQ.",
        "boundary": "No duplicate work queue.",
    },
    {
        "name": "2FastLabs/agent-squad",
        "area": "Agent-team reference",
        "decision": "Reference only; keep native Codex collaboration as the default execution route.",
        "evidence": "No current source vendoring or runtime execution in Company HQ.",
        "boundary": "No always-on alternate team runtime.",
    },
    {
        "name": "Seeed-Solution/MeshClaw",
        "area": "Distributed/mesh-agent reference",
        "decision": "Reference only until mesh behavior is needed and sandboxed.",
        "evidence": "No current source vendoring or runtime execution in Company HQ.",
        "boundary": "No networked agent mesh or federation by default.",
    },
    {
        "name": "trailhq/Graft / @nanonets/graft",
        "area": "Optional code-structure visualization",
        "decision": "Default-off optional wrapper; blocked from promotion until native install is reproducible.",
        "evidence": "Prior fixture/install work exists, but the latest evidence run failed native parser setup.",
        "boundary": "Not the primary code-intelligence path.",
    },
    {
        "name": "DeusData/codebase-memory-mcp",
        "area": "Code intelligence",
        "decision": "Primary structural code-intelligence candidate.",
        "evidence": "Smoke tests recovered 6/6 required code locations with external state.",
        "boundary": "Source files remain authoritative; no global indexing or credential copying.",
    },
    {
        "name": "Graphify-Labs/graphify",
        "area": "Broad graph fallback",
        "decision": "Second-stage graph for broad or cross-asset questions.",
        "evidence": "Smoke tests recovered 6/6 required locations with no source changes.",
        "boundary": "Not always-on beside Codebase Memory.",
    },
    {
        "name": "rtk-ai/rtk",
        "area": "Command output reduction",
        "decision": "Selected for bounded pytest/log output when raw evidence is retained.",
        "evidence": "Preserved required failure evidence in model-free reduction cases.",
        "boundary": "Byte reduction is not billed-token savings; unsupported output falls back to raw.",
    },
    {
        "name": "headroomlabs-ai/headroom",
        "area": "Structured context reduction",
        "decision": "Optional challenger for large structured payloads above thresholds.",
        "evidence": "No benefit on the tested pytest text configuration.",
        "boundary": "Never double-compress every prompt or replace raw evidence.",
    },
    {
        "name": "msitarzewski/agency-agents",
        "area": "Specialist roles",
        "decision": "Lazy role catalog for task-specific prompts.",
        "evidence": "Reviewed as guidance, not runtime execution.",
        "boundary": "Do not spawn or load the whole roster.",
    },
]


def _read_json(path):
    return json.loads(path.read_text())


def _safe_repo_entry(entry):
    metadata = entry.get("metadata", {})
    return {
        "repo": entry.get("repo"),
        "category": entry.get("category"),
        "reviewStatus": entry.get("review_status"),
        "installed": bool(entry.get("installed_by_this_handoff")),
        "nextAction": entry.get("next_action"),
        "license": metadata.get("license_spdx") or "unknown",
        "url": metadata.get("url"),
        "description": metadata.get("description"),
        "observedHead": metadata.get("observed_head"),
        "pushedAt": metadata.get("pushed_at"),
    }


def decisions():
    routing = _read_json(routing_path())
    candidates = _read_json(REPO_ROOT / "docs" / "repository-candidates.json")
    evidence = _read_json(REPO_ROOT / "benchmarks" / "evidence" / "selection-2026-09-21.json")
    code_results = evidence.get("code_intelligence", {}).get("results", {})
    output_cases = evidence.get("output_reduction", {}).get("cases", [])
    return {
        "schema": 1,
        "date": evidence.get("date"),
        "scope": evidence.get("scope"),
        "policy": routing.get("policy"),
        "providerSelection": routing.get("provider_selection", {}),
        "tiers": routing.get("tiers", {}),
        "decisions": [
            {
                "area": "Supervisor and model routing",
                "primary": "Company HQ router over authorized native runtimes",
                "why": "Keeps provider account homes intact and starts from the smallest capable reviewed tier.",
                "fallback": "Escalate one tier only after evidence, risk or failure justifies it.",
                "notChosen": "Silent billing-route switching, copied auth, or flagship-by-default staffing.",
                "evidence": f"{len(routing.get('reviewed_codex_models', []))} reviewed Codex model labels in routing policy.",
            },
            {
                "area": "Code intelligence",
                "primary": "Codebase Memory MCP",
                "why": "Recovered required locations with the smallest median output in the smoke test and no project-tree writes.",
                "fallback": "Graphify for broad or cross-asset questions; CodeGraph only after external-state adaptation.",
                "notChosen": "Running every indexer for every task, or treating Graft setup failure as an accuracy verdict.",
                "evidence": "Codebase Memory, Graphify and CodeGraph each matched 6/6 required queries in the final evidence run.",
            },
            {
                "area": "Task and work authority",
                "primary": "Current ClawTeam compatibility; Beads target migration",
                "why": "The live UI and tests already exercise ClawTeam safely, while Beads better matches DAG/claim/readiness needs.",
                "fallback": "Import ClawTeam records read-only during migration.",
                "notChosen": "Two canonical task databases at the same time.",
                "evidence": "Browser acceptance verifies current ClawTeam-backed flow; Beads remains a target contract.",
            },
            {
                "area": "Memory and decisions",
                "primary": "Restricted Ruflo memory adapter",
                "why": "Project-scoped decision memory without granting Ruflo provider/runtime control.",
                "fallback": "Current guarded memory until Supermemory/local target is accepted.",
                "notChosen": "Autopilot, hooks, federation, copied chat history or duplicate always-on stores.",
                "evidence": "Only the restricted allowlisted memory path is admitted today.",
            },
            {
                "area": "Output and context efficiency",
                "primary": "RTK for supported command output",
                "why": "Preserved required pytest evidence while cutting repetitive output bytes in fixture cases.",
                "fallback": "Raw output, then Headroom only for separately accepted structured payloads.",
                "notChosen": "Claiming byte savings as billed-token savings or hiding raw diagnostics.",
                "evidence": f"{sum(1 for case in output_cases if case.get('rtk_gate_passed'))}/{len(output_cases)} RTK evidence gates passed.",
            },
            {
                "area": "Usage budget enforcement",
                "primary": "Per-workspace reported-token action gate",
                "why": "Keeps frugality enforceable at Company HQ runtime boundaries without confusing reported tokens with billed spend.",
                "fallback": "Tracking-only mode when a workspace needs observation before enforcement.",
                "notChosen": "Pretending local token reports are provider billing caps or account-wide quota.",
                "evidence": "Bridge tests block later runtime actions after a native totalTokens report reaches the configured ceiling.",
            },
            {
                "area": "User experience",
                "primary": "Company HQ workbench with Agent Teams AI graph",
                "why": "One cockpit can show plan, approvals, task ownership and observed runtime events without another scheduler.",
                "fallback": "Borrow visual patterns from team dashboards only when backed by actual data.",
                "notChosen": "A separate full Agent Teams runtime that manages auth or invents liveness.",
                "evidence": "Main branch browser acceptance exercises the workbench with synthetic provider transport.",
            },
            {
                "area": "Runtime language boundary",
                "primary": "Python control plane now; Rust for proven runtime hot spots",
                "why": "Python integrates fastest with Codex, ClawTeam, evidence scripts and browser acceptance while the product contract is still moving.",
                "fallback": "Port process supervision, file watching, sandboxed command running, packaged desktop helpers or high-volume indexing when benchmarks justify it.",
                "notChosen": "A C/Rust rewrite based on preference rather than measured bottlenecks and equal lifecycle tests.",
                "evidence": "Architecture docs already reserve Rust/TypeScript for the runtime boundary; current checks pass on the Python integration.",
            },
        ],
        "codeIntelligence": [
            {"name": name, **value} for name, value in code_results.items()
        ],
        "outputReduction": output_cases,
        "actualModelTokens": evidence.get("actual_model_tokens"),
        "billedSavings": evidence.get("billed_savings"),
        "repositories": [_safe_repo_entry(entry) for entry in candidates.get("repositories", [])],
        "additionalComponents": ADDITIONAL_COMPONENTS,
        "limitations": evidence.get("limitations", []),
        "docs": {
            "bestStack": "docs/BEST-STACK.md",
            "selection": "docs/SELECTION-DECISIONS.md",
            "upstream": "docs/UPSTREAM-REVIEW.md",
        },
    }


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


def demo_knowledge():
    return {
        'notes': [
            {
                'namespace': 'company-notes',
                'key': 'demo-scope',
                'value': {
                    'title': 'Model-free demo',
                    'content': 'This workspace is synthetic. No provider, Ruflo process, or model is called while demo mode is active.',
                    'source': 'Demo fixture',
                    'date': time.strftime('%Y-%m-%d'),
                },
            },
            {
                'namespace': 'operating-decisions',
                'key': 'demo-boundaries',
                'value': {
                    'title': 'Boundaries stay explicit',
                    'content': 'Runtime state remains outside the source checkout, provider account homes stay unchanged, and execution is disabled until normal mode is started.',
                    'source': 'Demo fixture',
                    'date': time.strftime('%Y-%m-%d'),
                },
            },
        ],
        'source': 'Demo fixture',
        'codeGraph': 'unavailable-in-demo',
        'codeGraphNote': 'Code graph tools are not required for the model-free walkthrough.',
    }


def knowledge(project):
    if demo_mode():
        return demo_knowledge()
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
    if path == '/api/decisions':
        handler._serve_json(decisions());return True
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
    if not path.startswith(('/api/runtime/','/api/knowledge/','/api/workspaces','/api/task/','/api/budget/')): return False
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
            bridge(state).set_budget(name, 200000, True)
            handler._serve_json({'team':name,'company':profile,'started':False});return True
        parts=path.strip('/').split('/');name=unquote(parts[2]);project=project_for(state,name)
        if parts[1]=='budget':
            if len(parts)!=3: raise ValueError('Unknown budget route')
            budget=bridge(state).set_budget(name, body.get('limitTokens', body.get('maxTotalTokens', 200000)), body.get('enforced', True))
            handler._serve_json({'updated':True,'budget':budget});return True
        if parts[1]=='knowledge':
            if demo_mode():
                raise ValueError('Saving memory is disabled in model-free demo mode')
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
        if demo_mode() and action in ('start','send','execute','approve'):
            raise ValueError('Model execution is disabled in model-free demo mode')
        if action in ('start','send'):
            prompt=body.get('prompt','')
            if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>24000: raise ValueError('Enter a message of at most 24000 characters')
            if action=='start':
                routing=json.loads(routing_path().read_text());model=body.get('model','auto')
                if model=='auto':model=routing['preferred_supervisors'][0]['model']
                if model not in routing['reviewed_codex_models']: raise ValueError('Choose a reviewed available Codex model')
                result=client.start(name,project,prompt.strip(),model)
            else:result=client.send(name,prompt.strip())
        elif action=='execute':
            result=client.begin_execution(name)
        elif action=='stop':result=client.stop(name)
        elif action=='approve':result=client.approve(name,body.get('requestId'),body.get('decision'))
        else:raise ValueError('Unknown runtime action')
        handler._serve_json(result)
    except Exception as exc:handler._json_error(400,str(exc))
    return True
