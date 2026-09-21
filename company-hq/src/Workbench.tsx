import React, { useEffect, useRef, useState } from 'react';
import { Layers3, Play, Network, LayoutGrid, Brain, Settings2, X, Menu, Scale, BookOpenCheck } from 'lucide-react';
import TeamGraph from './TeamGraph';
import RunOverview from './RunOverview';
import DecisionCenter from './DecisionCenter';
import OperatingGuide from './OperatingGuide';
import './run-overview.css';

type RecordData = Record<string, any>;
const phases = ['pending', 'in_progress', 'blocked', 'completed'];
const phaseNames: Record<string, string> = { pending: 'To do', in_progress: 'In progress', blocked: 'Blocked', completed: 'Done' };
async function request(path: string, body?: RecordData) {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

/** One UI over existing APIs and the licensed Agent Teams graph. No second task store. */
export default function Workbench() {
  const [view, setView] = useState('run');
  const [teams, setTeams] = useState<RecordData[]>([]);
  const [team, setTeam] = useState('');
  const [snapshot, setSnapshot] = useState<RecordData | null>(null);
  const [profile, setProfile] = useState<RecordData>({});
  const [health, setHealth] = useState<RecordData>({});
  const [runtime, setRuntime] = useState<RecordData>({state: 'offline'});
  const [events, setEvents] = useState<RecordData[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState('auto');
  const [drafts, setDrafts] = useState<Record<string,string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [dialog, setDialog] = useState('');
  const [task, setTask] = useState<RecordData | null>(null);
  const [member, setMember] = useState('');
  const [notes, setNotes] = useState<RecordData[]>([]);
  const [memoryError, setMemoryError] = useState('');
  const [decisions, setDecisions] = useState<RecordData | null>(null);
  const [decisionError, setDecisionError] = useState('');
  const [decisionsLoading, setDecisionsLoading] = useState(false);
  const modal = useRef<HTMLDialogElement>(null);
  const selected = useRef(team); selected.current = team;
  const demo = health.mode === 'demo';
  const encoded = encodeURIComponent(team);
  const draft = drafts[team] || '';
  const tasks = phases.flatMap(status => (snapshot?.tasks?.[status] || []).map((t: RecordData) => ({...t, status})));
  const members = snapshot?.members || [];
  const planReady = !demo && runtime.connected && runtime.state === 'idle' && runtime.mode === 'plan' && runtime.planReady;
  const running = ['starting','running','awaiting_approval','stopping'].includes(runtime.state);
  const name = (id: string) => profile.members?.[id]?.displayName || id || 'Unassigned';

  async function refreshList() {
    const list = await request('/api/overview');
    setTeams(list);
    setTeam(current => current || list[0]?.name || '');
  }
  useEffect(() => {
    let cancelled = false;
    Promise.all([request('/api/health'), request('/api/workspaces'), request('/api/overview')])
      .then(([h, w, list]) => { if (!cancelled) { setHealth(h); setModels(w.models || []); setTeams(list); setTeam(list[0]?.name || ''); } })
      .catch(e => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (dialog) modal.current?.showModal(); else modal.current?.close();
  }, [dialog]);
  useEffect(() => {
    if (!team) return;
    let cancelled = false, inFlight = false, cursor = 0;
    setSnapshot(null); setProfile({}); setRuntime({state: 'offline'}); setEvents([]); setMember(''); setModel('auto'); setError(''); setNotice(''); setConsoleOpen(false);
    const poll = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const [s, p, r, feed] = await Promise.all([
          request(`/api/team/${encoded}`), request(`/api/company/${encoded}`),
          request(`/api/runtime/${encoded}/status`), request(`/api/runtime/${encoded}/events?after=${cursor}`),
        ]);
        if (cancelled) return;
        setSnapshot(s); setProfile(p); setRuntime(r);
        cursor = feed.nextSeq ?? cursor;
        setEvents(old => [...new Map([...old, ...(feed.events || [])].map(e => [e.seq, e])).values()].slice(-300));
      } catch (e: any) { if (!cancelled) setError(e.message); }
      finally { inFlight = false; }
    };
    poll(); const timer = setInterval(poll, 900);
    return () => { cancelled = true; clearInterval(timer); };
  }, [team]);
  useEffect(() => {
    if (view !== 'memory' || !team) return;
    let cancelled = false; setNotes([]); setMemoryError('');
    if (!demo && !health.capabilities?.rufloMemory?.available) { setMemoryError('Ruflo is not ready. No memory connection is claimed.'); return; }
    request(`/api/knowledge/${encoded}`).then(data => !cancelled && setNotes(data.notes || [])).catch(e => !cancelled && setMemoryError(e.message));
    return () => { cancelled = true; };
  }, [team, view, demo, health]);
  useEffect(() => {
    if (view !== 'decisions' || decisions) return;
    let cancelled = false;
    setDecisionError('');
    setDecisionsLoading(true);
    request('/api/decisions')
      .then(data => { if (!cancelled) setDecisions(data); })
      .catch(e => { if (!cancelled) setDecisionError(e.message); })
      .finally(() => { if (!cancelled) setDecisionsLoading(false); });
    return () => { cancelled = true; };
  }, [view, decisions]);
  const chooseView = (next: string) => { setView(next); setMobileNav(false); };
  async function action(path: string, body: RecordData = {}) {
    if (busy) return;
    const startedTeam = team; setBusy(true); setError('');
    try { const result = await request(path, body); return result; }
    catch (e: any) { if (selected.current === startedTeam) setError(e.message); }
    finally { setBusy(false); }
  }
  async function send() {
    if (!draft.trim() || !team) return;
    if (demo || !health.capabilities?.codex?.available) { setError('A ready, authorized runtime is required. Demo mode never calls a provider.'); return; }
    const startedTeam = team;
    const result = await action(`/api/runtime/${encoded}/${!runtime.connected ? 'start' : 'send'}`, {prompt: draft, model: runtime.model || model});
    if (result && selected.current === startedTeam) { setDrafts(old => ({...old, [startedTeam]: ''})); setConsoleOpen(true); }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    let result;
    if (dialog === 'workspace') {
      result = await action('/api/workspaces', data);
      if (result) { await refreshList(); setTeam(result.team); chooseView('run'); }
    } else if (dialog === 'budget') {
      result = await action(`/api/budget/${encoded}`, {
        limitTokens: Number(data.limitTokens || 0),
        enforced: data.enforced === 'true',
      });
      if (result?.budget) setRuntime((old: RecordData) => ({...old, budget: result.budget, limits: result.budget.blocked ? {blockedReason: result.budget.reason} : {}}));
    } else if (dialog === 'task') result = await action(`/api/team/${encoded}/task`, data);
    else if (dialog === 'message') {
      const recipient = members.find((m: RecordData) => m.name === member)?.inboxName || member;
      result = await action(`/api/team/${encoded}/message`, {from:'user', to:recipient, content:data.content});
      if (result) setNotice('Stored in the worker inbox. Delivery to a running process and acknowledgement are not confirmed.');
    }
    if (result) setDialog('');
  }
  return <div className="app-shell workbench">
    <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}>
      <div className="brand"><Layers3/><b>Company HQ</b><button className="icon-btn close-nav" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X/></button></div>
      <label className="workspace-picker">Project<select aria-label="Current workspace" value={team} onChange={e => setTeam(e.target.value)}><option value="" disabled>Select a workspace</option>{teams.map(t => <option key={t.name} value={t.name}>{t.name === team ? profile.projectLabel || t.name : t.name}</option>)}</select></label>
      <nav>{[['run',Play,'Run overview'],['guide',BookOpenCheck,'How to use'],['map',Network,'Company map'],['board',LayoutGrid,'Work board'],['decisions',Scale,'Why this stack'],['memory',Brain,'Shared memory'],['system',Settings2,'System status']].map(([id,Icon,label]:any) => <button key={id} className={view === id ? 'active' : ''} onClick={() => chooseView(id)}><Icon size={17}/>{label}</button>)}</nav>
      <div className="section-label">REGISTERED TEAM · {members.length}</div>
      <div className="roster">{members.map((m:RecordData) => <button key={m.name} className="person-row" onClick={() => { setMember(m.name); setDialog('message'); }}><span><b>{name(m.name)}</b><small>{profile.members?.[m.name]?.department || 'Role record'} · runtime not inferred</small></span></button>)}</div>
      <button className="new-workspace" onClick={() => setDialog('workspace')}>+ Connect project</button>
      <button className="small-button" onClick={() => setDialog('help')}>How this works</button>
    </aside>
    <main className="main-shell">
      <header className="topbar"><button className="icon-btn mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu/></button><div className="breadcrumb"><b>{profile.projectLabel || 'Company HQ'}</b></div><div className="top-controls"><span className="runtime-pill">{demo ? 'Model-free demo' : runtime.mode === 'execute' ? 'Execution approved' : 'Plan first'}</span><button className="small-button" onClick={() => setDialog('task')} disabled={!team}>Add task</button></div></header>
      <section className="mission-bar"><div><small>THE OUTCOME</small><h1>{profile.goal || 'Connect your project and describe the result you need.'}</h1></div></section>
      {error && <div className="error-banner" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X/></button></div>}
      {notice && <div className="notice-banner" role="status">{notice}</div>}
      {runtime.budget?.blocked && <div className="approval-bar"><div><b>Budget gate reached</b><p>{runtime.budget.reason}</p></div><button className="small-button" onClick={() => setDialog('budget')}>Adjust budget</button></div>}
      {planReady && <div className="approval-bar"><div><b>Plan ready — review before enabling writes</b><p>Read the plan in the conversation. Execution is a separate decision.</p></div><button className="primary-button" disabled={busy || runtime.budget?.blocked} onClick={() => { action(`/api/runtime/${encoded}/execute`); setConsoleOpen(true); }}>Approve plan & start execution</button></div>}
      <div className={`work-area ${consoleOpen ? 'with-inspector' : ''}`}>
        <section className={`stage ${view === 'map' ? 'map-stage' : ''}`}>
          {view === 'run' && <RunOverview runtime={runtime} events={events as any} demo={demo} connectedProject={!!team} registeredCount={members.length} completedCount={tasks.filter(t => t.status === 'completed').length} taskCount={tasks.length} onConsole={() => setConsoleOpen(true)} onSystem={() => chooseView('system')} onBudget={() => setDialog('budget')} onDraft={text => setDrafts(old => ({...old,[team]:text}))}/>}
          {view === 'guide' && <OperatingGuide demo={demo} health={health} runtime={runtime}/>}
          {view === 'map' && <><div className="stage-heading"><h2>Company map</h2><p>Task ownership and recorded reporting lines; runtime evidence stays separate.</p></div>{snapshot && <div className="graph-host"><TeamGraph snapshot={snapshot as any} company={profile} runtime={runtime} onSelectMember={id => {setMember(id);setDialog('message')}} onSelectTask={id => setTask(tasks.find(t=>t.id===id)||null)}/></div>}</>}
          {view === 'board' && <div className="board-view"><h2>Work board</h2><p>One canonical ClawTeam task list. Status alone is not test evidence.</p><div className="kanban">{phases.map(status => <section className="column" key={status}><header><h3>{phaseNames[status]}</h3></header>{tasks.filter(t=>t.status===status).map(t=><button className="task-card" key={t.id} onClick={()=>{setTask(t);setDialog('task-detail')}}><h4>{t.subject}</h4><p>{t.description}</p><footer>{name(t.owner)}</footer></button>)}</section>)}</div></div>}
          {view === 'decisions' && <DecisionCenter data={decisions} loading={decisionsLoading} error={decisionError}/>}
          {view === 'memory' && <div className="memory-view"><h2>Shared project memory</h2><p>{demo ? 'Synthetic fixtures; no memory server is called.' : 'Scoped Ruflo decisions, not your entire chat history.'}</p>{memoryError && <p role="status">{memoryError}</p>}{notes.map(n=><article className="note" key={n.key}><h3>{n.value?.title || n.key}</h3><pre>{typeof n.value === 'string' ? n.value : n.value?.content || JSON.stringify(n.value,null,2)}</pre></article>)}</div>}
          {view === 'system' && <div className="memory-view"><h2>Connections & capabilities</h2><p>Installed is not the same as authenticated. Subscription quota and billing remain unknown unless a supported runtime reports them.</p><button className="small-button" onClick={()=>request('/api/health').then(setHealth).catch(e=>setError(e.message))}>Refresh capabilities</button><div className="note-grid">{Object.entries(health.capabilities || {}).map(([key,c]:any)=><article className="note" key={key}><h3>{key}</h3><b>{c.available ? 'Locally available' : 'Unavailable'}</b><p>{c.reason || 'Account access still requires native runtime verification.'}</p><pre>{c.path}</pre></article>)}</div><p>App state: {health.stateRoot}</p><p>No account credentials are copied into Company HQ.</p></div>}
        </section>
        {consoleOpen && <aside className="inspector"><header className="inspector-header"><h2>Supervisor conversation</h2><button className="icon-btn" aria-label="Close conversation" onClick={()=>setConsoleOpen(false)}><X/></button></header><div className="inspector-scroll">{(runtime.pendingApprovals || []).map((a:RecordData)=><section className="approval-card" key={a.requestId}><h3>Permission requested</h3><p>{a.reason}</p><pre>{a.command}</pre><button className="small-button" onClick={()=>action(`/api/runtime/${encoded}/approve`,{requestId:a.requestId,decision:'reject'})}>Decline</button><button className="primary-button" onClick={()=>action(`/api/runtime/${encoded}/approve`,{requestId:a.requestId,decision:'approve'})}>Approve once</button></section>)}{events.filter(e=>e.type!=='message.delta').map(e=><article className="runtime-event" key={e.seq}><header>{e.type}</header><pre>{e.type==='usage' ? JSON.stringify(e.data?.counts || {},null,2) : e.data?.text || ''}</pre></article>)}{!events.length && <p className="quiet-state">Describe the goal below. The first turn is read-only.</p>}</div></aside>}
      </div>
      <div className="composer-dock"><div className="composer"><div className="composer-top"><b>Overall supervisor</b><select aria-label="Supervisor model" value={runtime.model || model} disabled={!!runtime.threadId || demo} onChange={e=>setModel(e.target.value)}><option value="auto">Automatic policy</option>{models.map(m=><option key={m}>{m}</option>)}</select></div><textarea aria-label="Direction for the team" value={draft} onChange={e=>setDrafts(old=>({...old,[team]:e.target.value}))} placeholder="Describe the outcome, constraints and acceptance checks."/><div className="composer-bottom"><span>{runtime.budget?.blocked ? 'Budget gate reached · adjust before more model work' : demo ? 'No model calls in demo' : 'No silent account or billing-route changes'}</span><div>{running && <button className="stop-button" onClick={()=>action(`/api/runtime/${encoded}/stop`)}>Stop</button>}<button className="send-button" disabled={busy || !team || !draft.trim() || demo || !health.capabilities?.codex?.available || runtime.budget?.blocked} onClick={send}>{busy?'Sending…':runtime.budget?.blocked?'Budget reached':runtime.mode==='execute'?'Continue execution':'Discuss & plan'}</button></div></div></div></div>
    </main>
    <dialog ref={modal} className="modal" onCancel={()=>setDialog('')}><button className="modal-close icon-btn" aria-label="Close dialog" onClick={()=>setDialog('')}><X/></button>
      {dialog==='help'?<><h2>One workspace for the whole team</h2><p>Connect a project → discuss a read-only plan → approve execution → follow actual worker events → inspect tests and results.</p><p>Ruflo memory and code indexes are optional capabilities. Registered roles are not proof that workers are running. No model, billing plan or quota is invented.</p><p>Agent Teams AI graph, ClawTeam tasks and the current native Codex adapter are reused. Additional providers require their own verified adapter and authorization.</p><a href="/api/source">Application source and retained upstream licenses</a></>:dialog==='task-detail'?<><h2>{task?.subject}</h2><p>{task?.description}</p><label>Task status<select aria-label="Task status" value={task?.status||'pending'} onChange={async e=>{const next=e.target.value;const r=await action(`/api/task/${encoded}/${encodeURIComponent(task?.id)}`,{status:next});if(r)setTask(t=>({...t,status:next}))}}>{phases.map(p=><option value={p} key={p}>{phaseNames[p]}</option>)}</select></label><p>Manual status changes do not claim that tests passed.</p></>:<form onSubmit={submit}><h2>{dialog==='workspace'?'Connect a workspace':dialog==='message'?`Message ${name(member)}`:dialog==='budget'?'Set usage budget':'Add a task'}</h2>{dialog==='workspace'?<><label>Workspace name<input name="label" required maxLength={120}/></label><label>Project folder<input name="project" required/></label><label>Desired outcome<textarea name="goal" required maxLength={2000}/></label><p>Connecting does not start a model or change the project.</p></>:dialog==='message'?<><label>Direction<textarea name="content" required maxLength={12000}/></label><p>This stores an inbox message; it does not promise wake-up or acknowledgement.</p></>:dialog==='budget'?<><label>Token ceiling<input name="limitTokens" type="number" min="0" max="20000000" required defaultValue={runtime.budget?.limitTokens ?? 200000}/></label><label>Action gate<select name="enforced" defaultValue={String(runtime.budget?.enforced ?? true)}><option value="true">Block next runtime action at the ceiling</option><option value="false">Track only</option></select></label><p>Counts provider-reported native totalTokens for this workspace. It is not billed money or account-wide quota. Use 0 to turn off the local ceiling.</p></>:<><label>Task<input name="subject" required maxLength={2000}/></label><label>Owner<select name="owner" defaultValue={snapshot?.team?.leaderName||''}><option value="">Unassigned</option>{members.map((m:RecordData)=><option key={m.name} value={m.name}>{name(m.name)}</option>)}</select></label><label>Expected result<textarea name="description" maxLength={12000}/></label></>}<footer><button type="button" className="small-button" onClick={()=>setDialog('')}>Cancel</button><button className="primary-button" disabled={busy}>{dialog==='workspace'?'Connect workspace':dialog==='message'?'Queue message':dialog==='budget'?'Save budget':'Create task'}</button></footer></form>}
    </dialog>
  </div>;
}
