"""Company HQ adapters over ClawTeam, Ruflo and the native Codex bridge."""
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import json, os, re, select, subprocess, tempfile, threading, time, uuid
from company_profile import load_profile, validate_profile, profile_path
from clawteam.team.manager import TeamManager
from task_authority import TaskStore
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
_workspace_locks = {}
_workspace_locks_guard = threading.Lock()


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
                "why": "Keeps provider account homes intact, uses the reviewed flagship supervisor, and assigns bounded work to economical capable workers.",
                "fallback": "Escalate one tier only after evidence, risk or failure justifies it.",
                "notChosen": "Silent billing-route switching, copied auth, or putting the flagship model in every worker role.",
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
                "primary": "Beads task authority with ClawTeam wire compatibility",
                "why": "Beads supplies dependencies, readiness and atomic claims; existing board and inbox clients keep their familiar task model.",
                "fallback": "Import ClawTeam records read-only during migration.",
                "notChosen": "Two canonical task databases at the same time.",
                "evidence": "Migration, dependencies, claims, close/restart and unchanged legacy-source tests pass using the pinned Beads binary.",
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
                "primary": "Rust desktop lifecycle with a frozen Python control plane",
                "why": "Rust owns the desktop window and backend process lifecycle. The frozen control plane integrates provider protocols and tested project boundaries without requiring a user Python installation.",
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


def workspace_operation_lock(name):
    """Serialize project attachment with the first native binding per team."""
    with _workspace_locks_guard:
        lock = _workspace_locks.get(name)
        if lock is None:
            lock = threading.RLock()
            _workspace_locks[name] = lock
        return lock


def _project_folder(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Choose an existing project folder')
    folder = Path(value).expanduser().resolve()
    if not folder.is_dir() or folder in {Path('/'), Path.home()}:
        raise ValueError('Choose an existing project folder')
    return folder


def _managed_workspace_folder(state, name):
    """Create one private native-work directory beneath isolated app state."""
    state_root = Path(state).resolve()
    root = state_root / 'managed-workspaces'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.resolve() != root or not root.resolve().is_relative_to(state_root):
        raise ValueError('Managed workspace state is unsafe')
    os.chmod(root, 0o700)
    folder = root / name
    folder.mkdir(mode=0o700)
    resolved = folder.resolve()
    if folder.is_symlink() or resolved.parent != root.resolve() or not resolved.is_dir():
        raise ValueError('Managed workspace state is unsafe')
    os.chmod(resolved, 0o700)
    return resolved


def _default_supervisor_model(routing):
    """Choose only a reviewed routing-policy model, never provider discovery."""
    reviewed = routing.get('reviewed_codex_models', [])
    if not isinstance(reviewed, list):
        raise ValueError('No reviewed Codex model is configured')
    reviewed = [model for model in reviewed if isinstance(model, str)]
    tier_name = routing.get('supervisor_tier')
    if not isinstance(tier_name, str) or not tier_name:
        tier_name = routing.get('escalation', {}).get('start_tier', 'standard')
    tier = routing.get('tiers', {}).get(tier_name, {})
    candidate = tier.get('codex_model') if isinstance(tier, dict) else None
    if candidate in reviewed:
        return candidate
    # Schema-1 compatibility while old checked-in routing policies are retired.
    legacy = routing.get('preferred_supervisors', [])
    if isinstance(legacy, list):
        for entry in legacy:
            candidate = entry.get('model') if isinstance(entry, dict) else None
            if candidate in reviewed:
                return candidate
    if reviewed:
        return reviewed[0]
    raise ValueError('No reviewed Codex model is configured')


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
    from runtime_config import node_executable
    node=node_executable()
    env=dict(os.environ)
    if node: env['COMPANY_HQ_NODE']=str(node)
    proc = subprocess.Popen([str(ruflo_launcher())], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
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


_provider_hubs = {}
_provider_hubs_lock = threading.RLock()

def bridge(state):
    from codex_bridge import get_codex_bridge
    from provider_hub import ProviderHub
    directory=(state / "runtime").resolve()
    with _provider_hubs_lock:
        if directory not in _provider_hubs:
            _provider_hubs[directory]=ProviderHub(directory,codex=get_codex_bridge(directory))
        return _provider_hubs[directory]

def shutdown_runtime(state):
    # Shutdown must not create a new runtime directory or provider connection.
    with _provider_hubs_lock:
        hub=_provider_hubs.pop((state / "runtime").resolve(),None)
    if hub is not None: hub.shutdown_all()

def native_client(client,team):
    from provider_hub import ProviderHub
    if isinstance(client,ProviderHub):
        if client.status(team).get('provider') != 'codex':
            raise ValueError('This control uses the Codex native runtime. Ask Claude in chat to use its native tools and permissions.')
        return client.codex
    return client


def handle_get(handler, state):
    path = urlparse(handler.path).path
    if path.startswith(('/api/files/', '/api/drafts/')):
        try:
            from workspace_files import listing, read, draft
            parts = path.strip('/').split('/')
            if len(parts) != 3: raise ValueError('Invalid project route.')
            name = unquote(parts[2])
            if parts[1] == 'drafts':
                if name != 'new': project_for(state, name)
                result = draft(state, name)
            else:
                project = project_for(state, name)
                query = parse_qs(urlparse(handler.path).query, keep_blank_values=True)
                if set(query) - {'path', 'kind'}: raise ValueError('Invalid file filters.')
                relative = query.get('path', [''])[0]
                result = read(project, relative) if query.get('kind', ['folder'])[0] == 'file' else listing(project, relative)
            handler._serve_json(result)
        except (ValueError, OSError) as exc: handler._json_error(400, str(exc))
        return True
    if path == '/api/health':
        handler._serve_json(health_snapshot(state));return True
    if path == '/api/decisions':
        handler._serve_json(decisions());return True
    if path.startswith('/api/attachments/'):
        try:
            parts = path.strip('/').split('/')
            if len(parts) != 4: raise ValueError('Invalid image route')
            name = unquote(parts[2]); project_for(state, name)
            from image_attachments import read
            meta, file_path = read(state, name, parts[3])
            content = file_path.read_bytes()
            handler.send_response(200)
            handler.send_header('Content-Type', meta['mimeType'])
            handler.send_header('Content-Length', str(len(content)))
            handler.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            handler.end_headers(); handler.wfile.write(content)
        except Exception:
            handler._json_error(404, 'Image not found in this chat')
        return True
    if path.startswith(('/api/providers/codex/tasks','/api/providers/claude/tasks')):
        try:
            from provider_connections import connections
            parts = path.strip('/').split('/')
            query = parse_qs(urlparse(handler.path).query, keep_blank_values=True)
            provider=parts[2]
            if provider=='claude':
                import claude_tasks as task_service
            else: task_service=connections()
            if parts == ['api', 'providers', provider, 'tasks']:
                allowed = {'cursor', 'search', 'archived', 'includeAgents'}
                if set(query) - allowed or any(len(values) != 1 for values in query.values()):
                    raise ValueError('Invalid task filters.')
                def flag(key):
                    value = query.get(key, ['false'])[0]
                    if value not in ('true', 'false'): raise ValueError('Invalid task filter.')
                    return value == 'true'
                result = task_service.list_tasks(cursor=query.get('cursor', [None])[0],
                    search=query.get('search', [''])[0], archived=flag('archived'), include_agents=flag('includeAgents'))
            elif len(parts) == 5 and parts[:4] == ['api', 'providers', provider, 'tasks'] and not query:
                result = task_service.read_task(unquote(parts[4]))
            else: raise ValueError('Invalid task route.')
            handler._serve_json(result)
        except Exception:
            handler._json_error(400, 'Provider tasks could not be loaded. Check the filters and native connection.')
        return True
    if path == '/api/providers':
        try:
            from provider_connections import connections
            handler._serve_json(connections().snapshot())
        except Exception:
            handler._json_error(503, 'Provider discovery is unavailable. Try again.')
        return True
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
        elif parts[3]=='history':
            from transcript_archive import TranscriptArchive
            query=parse_qs(urlparse(handler.path).query)
            before=int(query['before'][0]) if query.get('before') else None
            result=TranscriptArchive(state/'runtime').page(name,before)
        elif parts[3]=='workers': result=bridge(state).workers(name)
        elif parts[3]=='evidence':
            from runtime_actions import evidence
            query=parse_qs(urlparse(handler.path).query)
            result=evidence(state,name,project_for(state,name),query.get('id',[None])[0],int(query.get('offset',['0'])[0]))
        elif parts[3]=='tools': result=bridge(state).tools(name)
        elif parts[3]=='events':
            after=int(parse_qs(urlparse(handler.path).query).get('after',['0'])[0]);result=bridge(state).events(name,max(0,after))
        else: raise ValueError('Unknown runtime route')
        handler._serve_json(result)
    except Exception as exc:
        handler._json_error(400,str(exc))
    return True


def handle_post(handler,state,path,body):
    if path.startswith('/api/plans/'):
        try:
            from workflow_plan import WorkflowPlans
            parts = path.strip('/').split('/')
            if len(parts) != 4 or parts[3] not in ('preview','apply') or not isinstance(body,dict):
                raise ValueError('Unknown plan action.')
            if set(body) - {'plan','requestId'}: raise ValueError('Unsupported plan fields.')
            name=unquote(parts[2]); project_for(state,name)
            team=TeamManager.get_team(name)
            members=[member.name for member in team.members]
            plans=WorkflowPlans(state)
            with workspace_operation_lock(name):
                if parts[3]=='preview': result=plans.preview(name,body.get('plan'),members)
                else:
                    if demo_mode(): raise ValueError('Plan import is disabled in demo mode.')
                    result=plans.apply(name,body.get('requestId'),body.get('plan'),members)
            handler._serve_json(result)
        except (ValueError,OSError) as exc: handler._json_error(400,str(exc))
        return True
    if path.startswith(('/api/files/', '/api/drafts/')):
        try:
            from workspace_files import write, draft
            parts = path.strip('/').split('/')
            if len(parts) != 3 or not isinstance(body, dict): raise ValueError('Invalid project request.')
            name = unquote(parts[2])
            if parts[1] == 'drafts':
                if name != 'new': project_for(state, name)
                result = draft(state, name, body)
            else:
                project = project_for(state, name)
                status = bridge(state).status(name)
                if demo_mode() or status.get('mode') != 'execute': raise ValueError('Enable workspace or full access before editing files.')
                if set(body) != {'path', 'text', 'revision'}: raise ValueError('Invalid file edit.')
                result = write(project, body['path'], body['text'], body['revision'])
            handler._serve_json(result)
        except (ValueError, OSError) as exc: handler._json_error(400, str(exc))
        return True
    if path.startswith('/api/attachments/'):
        try:
            parts = path.strip('/').split('/')
            if len(parts) != 3: raise ValueError('Invalid upload route')
            name = unquote(parts[2]); project_for(state, name)
            if demo_mode(): raise ValueError('Image uploads are disabled in demo mode')
            from image_attachments import upload
            handler._serve_json(upload(state, name, body))
        except Exception as exc:
            handler._json_error(400, str(exc))
        return True
    if path == '/api/access/settings':
        try:
            if demo_mode(): raise ValueError('Opening system settings is disabled in demo mode.')
            from access_settings import open_settings
            handler._serve_json(open_settings(body))
        except Exception as exc:
            handler._json_error(400, str(exc))
        return True
    if path == '/api/folders/pick':
        try:
            if not isinstance(body, dict) or body:
                raise ValueError('Folder selection does not accept a path or command.')
            if demo_mode(): raise ValueError('Native folder selection is disabled in demo mode.')
            from folder_picker import choose_folder
            handler._serve_json(choose_folder())
        except Exception as exc:
            handler._json_error(400, str(exc))
        return True
    if path.startswith('/api/providers/'):
        try:
            if not isinstance(body,dict) or body: raise ValueError('Provider actions do not accept credentials or file paths.')
            parts=path.strip('/').split('/')
            if len(parts)!=4: raise ValueError('Unknown provider action')
            from provider_connections import connections
            handler._serve_json(connections().action(parts[2],parts[3]))
        except Exception as exc:handler._json_error(400,str(exc))
        return True
    if not path.startswith(('/api/runtime/','/api/knowledge/','/api/workspaces','/api/task/','/api/budget/')): return False
    try:
        if not isinstance(body,dict): raise ValueError('Request must be a JSON object')
        if path=='/api/workspaces':
            raw_label=body.get('label','');raw_project=body.get('project','');raw_goal=body.get('goal','')
            if not all(isinstance(value,str) for value in (raw_label,raw_project,raw_goal)):
                raise ValueError('Workspace details must be text')
            label=raw_label.strip() or 'New conversation';project=raw_project.strip();goal=raw_goal.strip()
            if len(label)>120 or len(goal)>2000: raise ValueError('Enter a short project name and goal')
            if not goal: goal=f'Discuss and plan {label}.'
            name=(re.sub('[^a-z0-9-]','-',label.lower()).strip('-')[:40] or 'project')+'-'+uuid.uuid4().hex[:6]
            kind='project' if project else 'managed'
            folder=_project_folder(project) if project else _managed_workspace_folder(state,name)
            TeamManager.create_team(name,'overall-head','not-started',description=goal,user='local',leader_agent_type='overall-head')
            profile=save_profile(state,name,{'projectLabel':label,'projectRoot':str(folder),'workspaceKind':kind,'goal':goal,'members':{'overall-head':{'displayName':'Overall head','department':'Direction & delivery','model':'','reportsTo':None}}},{'overall-head'})
            bridge(state).set_budget(name, 200000, True)
            handler._serve_json({'team':name,'company':profile,'started':False});return True
        parts=path.strip('/').split('/')
        if len(parts)==4 and parts[:2]==['api','workspaces'] and parts[3]=='attach':
            name=unquote(parts[2]);team=TeamManager.get_team(name)
            if team is None: raise ValueError('Workspace not found')
            with workspace_operation_lock(name):
                profile=load_profile(state,name,{m.name for m in team.members})
                if profile.get('workspaceKind') != 'managed':
                    raise ValueError('Only an unopened managed workspace can attach a project folder')
                runtime=bridge(state).status(name)
                if runtime.get('project') is not None or runtime.get('threadId') is not None:
                    raise ValueError('This workspace is already bound to its managed folder; start a new project workspace instead')
                folder=_project_folder(body.get('project'))
                profile=save_profile(state,name,{**profile,'projectRoot':str(folder),'workspaceKind':'project'}, {m.name for m in team.members})
            handler._serve_json({'team':name,'company':profile,'attached':True});return True
        name=unquote(parts[2])
        if parts[1]=='budget':
            if len(parts)!=3: raise ValueError('Unknown budget route')
            project_for(state,name)
            budget=bridge(state).set_budget(name, body.get('limitTokens', body.get('maxTotalTokens', 200000)), body.get('enforced', True))
            handler._serve_json({'updated':True,'budget':budget});return True
        if parts[1]=='knowledge':
            if demo_mode():
                raise ValueError('Saving memory is disabled in model-free demo mode')
            project=project_for(state,name)
            title=body.get('title','').strip();content=body.get('content','').strip()
            if not title or not content or len(title)>200 or len(content)>12000: raise ValueError('Enter a title and a note of at most 12000 characters')
            key=uuid.uuid4().hex
            memory_call(project,lambda tool:tool('memory_store',{'key':key,'namespace':'company-notes','value':{'title':title,'content':content,'source':'User','date':time.strftime('%Y-%m-%d')},'provenance_type':'user_claim'}))
            _memory_cache.pop(project,None);handler._serve_json({'saved':True,'key':key});return True
        if parts[1]=='task':
            if len(parts)!=4: raise ValueError('Task ID required')
            project_for(state,name)
            status=TaskStatus(body.get('status'))
            task=TaskStore(name).update(parts[3],status=status,caller='user')
            if task is None: raise ValueError('Task not found')
            handler._serve_json({'updated':True});return True
        if parts[1]!='runtime' or len(parts)!=4: raise ValueError('Unknown action')
        client=bridge(state);action=parts[3]
        if demo_mode() and action in ('start','send','execute','approve','respond','access'):
            raise ValueError('Model execution is disabled in model-free demo mode')
        if action in ('start','send'):
            prompt=body.get('prompt','')
            if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>24000: raise ValueError('Enter a message of at most 24000 characters')
            project_for(state, name)
            from image_attachments import resolve
            attachments = resolve(state, name, body.get('attachmentIds', []))
            image_options = {'attachments': attachments} if attachments else {}
            if action=='start':
                routing=json.loads(routing_path().read_text());model=body.get('model','auto');provider=body.get('provider','codex')
                if provider=='codex':
                    if model=='auto':model=_default_supervisor_model(routing)
                    if model not in routing['reviewed_codex_models']: raise ValueError('Choose a reviewed available Codex model')
                elif provider=='claude':
                    if not isinstance(model,str) or not model or len(model)>200 or model=='auto':
                        raise ValueError('Check the Claude connection and choose a reported model.')
                    # ProviderHub verifies this exact selection against the
                    # official initialize response before sending any prompt.
                    image_options['provider']='claude'
                else: raise ValueError('This provider does not have a verified HQ execution adapter.')
                with workspace_operation_lock(name):
                    project=project_for(state,name)
                    work_mode=body.get('workMode','plan')
                    if work_mode not in ('plan','auto','full'):raise ValueError('Choose plan or automatic work')
                    if work_mode in ('auto','full'): image_options['work_mode'] = work_mode
                    result=client.start(name,project,prompt.strip(),model,**image_options)
            else:
                project_for(state,name)
                result=client.send(name,prompt.strip(),**image_options)
        elif action=='execute':
            project_for(state,name)
            result=client.begin_execution(name)
        elif action=='access':
            project_for(state,name)
            result=client.set_access(name,body.get('accessMode'))
        elif action=='stop':
            project_for(state,name)
            result=client.stop(name)
        elif action=='worker-message':
            project_for(state,name)
            if demo_mode(): raise ValueError('Worker execution is disabled in demo mode.')
            if set(body) != {'threadId', 'prompt'}: raise ValueError('Choose a worker and enter a message.')
            result=client.send_worker(name,body['threadId'],body['prompt'])
        elif action=='stop-workers':
            project_for(state,name)
            result=client.stop_workers(name)
        elif action=='command':
            project_for(state,name)
            from runtime_actions import command
            if set(body) != {'command'}: raise ValueError('Enter a terminal command.')
            result=command(native_client(client,name),state,name,body['command'])
        elif action=='tool-action':
            project_for(state,name)
            from runtime_actions import tool_action
            if set(body)-{'action','name','enabled'}: raise ValueError('Unsupported tool setting.')
            result=tool_action(native_client(client,name),name,body.get('action'),body.get('name'),body.get('enabled'))
        elif action=='respond':
            project_for(state,name)
            if set(body) != {'requestId', 'response'}: raise ValueError('A request ID and response are required.')
            result=client.respond(name,body.get('requestId'),body.get('response'))
        elif action=='approve':
            project_for(state,name)
            result=client.approve(name,body.get('requestId'),body.get('decision'))
        else:raise ValueError('Unknown runtime action')
        handler._serve_json(result)
    except Exception as exc:handler._json_error(400,str(exc))
    return True
