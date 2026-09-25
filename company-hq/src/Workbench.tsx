import React, { useEffect, useRef, useState } from 'react';
import { Layers3, Network, LayoutGrid, Brain, Settings2, X, Menu, Scale, PanelRightOpen, SquarePen, MessageCircle, FolderPlus, ChevronDown, ArrowUp, Sparkles, CircleHelp, Activity, Files } from 'lucide-react';
const TeamGraph = React.lazy(() => import('./TeamGraph'));
const OfficeView=React.lazy(()=>import('./OfficeView'));
import {officeState,exampleOffice} from './office-state.mjs';
import RunOverview from './RunOverview';
const DecisionCenter = React.lazy(() => import('./DecisionCenter'));
const OperatingGuide = React.lazy(() => import('./OperatingGuide'));
import './run-overview.css';
import ChatView from './ChatView';
import Connections from './Connections';
import ModelPicker from './ModelPicker';
import NativeTasks from './NativeTasks';
import UsagePanel from './UsagePanel';
import useDrafts from './useDrafts';
import VoiceInput from './VoiceInput';
const ProjectFiles=React.lazy(()=>import('./ProjectFiles'));
const PlanPanel=React.lazy(()=>import('./PlanPanel'));
const WorkersPanel=React.lazy(()=>import('./WorkersPanel'));
import ImageAttachments, {readImageFiles, type ImageDraft} from './ImageAttachments';
import {nativeTeamView} from './native-team-view.mjs';
import {mergeRuntimeEvents} from './event-feed.mjs';
import {chatHierarchy,chatDescendants} from './chat-hierarchy.mjs';
import './chat-shell.css';
import ChatMenu from './ChatMenu';

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
  const [teamView,setTeamView]=useState('office');
  const [officeExample,setOfficeExample]=useState(false);
  const [chatLabels, setChatLabels] = useState<Record<string,string>>({});
  const [chatProfiles, setChatProfiles] = useState<Record<string,RecordData>>({});
  const [teammateStatuses, setTeammateStatuses] = useState<Record<string,RecordData>>({});
  const [teamModels, setTeamModels] = useState<{provider:string;model:string;label:string}[]>([]);
  const [teamChoice, setTeamChoice] = useState('');
  const composerInput = useRef<HTMLTextAreaElement>(null);
  const [teams, setTeams] = useState<RecordData[]>([]);
  const [deletedChats, setDeletedChats] = useState<string[]>([]);
  const [team, setTeam] = useState('');
  const [nativeRoster,setNativeRoster]=useState<RecordData>({workers:[]});
  const [graphWorker,setGraphWorker]=useState('');
  const [snapshot, setSnapshot] = useState<RecordData | null>(null);
  const [profile, setProfile] = useState<RecordData>({});
  const [health, setHealth] = useState<RecordData>({});
  const [runtimeSnapshot, setRuntime] = useState<RecordData>({state: 'offline'});
  const [runtimeTeam, setRuntimeTeam] = useState('');
  const runtime: RecordData = runtimeTeam === team ? runtimeSnapshot : {state:'loading'};
  const navigation = useRef(0);
  const [historyCursor,setHistoryCursor]=useState<number|null>(null);
  const [historyBusy,setHistoryBusy]=useState(false);
  const [events, setEvents] = useState<RecordData[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState('auto');
  const [provider,setProvider]=useState('codex');
  const [workMode, setWorkMode] = useState(() => {
    try { const saved=localStorage.getItem('hq.workMode'); return saved==='plan'||saved==='full'?saved:'auto'; } catch { return 'auto'; }
  });
  const [draftError,setDraftError]=useState('');
  const [drafts, setDrafts] = useDrafts(team,setDraftError);
  const [imageDrafts, setImageDrafts] = useState<Record<string,ImageDraft[]>>({});
  const uploadedImages = useRef<Record<string,string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [dialog, setDialog] = useState('');
  const activeDialog = useRef(dialog); activeDialog.current = dialog;
  const [folderPath, setFolderPath] = useState('');
  const [pickingFolder, setPickingFolder] = useState(false);
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
  useEffect(()=>{request('/api/routing').then(r=>{if(!selected.current&&r.settings?.preferredSupervisor){setProvider(r.settings.preferredSupervisor.provider);setModel(r.settings.preferredSupervisor.model)}}).catch(()=>{})},[]);
  const selectedProvider=(runtime.providerBound||runtime.threadId)?(runtime.provider||'codex'):provider;
  const missingCodex=selectedProvider==='codex'&&!health.capabilities?.codex?.available;
  const encoded = encodeURIComponent(team);
  const draft = drafts[team] || '';
  const images = imageDrafts[team] || [];
  async function addImages(files: FileList) {
    const target=team;
    try {const result=await readImageFiles(files, images.length);setImageDrafts(old=>({...old,[target]:[...(old[target]||[]),...result.items].slice(0,4)}));if(result.errors.length)setError(result.errors.join(' '))}catch(e:any){setError(e.message||'Could not read image')}
  }
  const graphData=nativeTeamView(snapshot,profile,nativeRoster);
  const childChats=chatDescendants(teams,chatProfiles,team,deletedChats).filter(t=>chatProfiles[t.name]?.projectRoot===profile.projectRoot);
  const childChatIds=childChats.map(child=>child.name).join('|');
  const baseOfficeData=officeExample?exampleOffice():officeState(snapshot,profile,nativeRoster,runtime,events);
  const officeData=officeExample?baseOfficeData:{...baseOfficeData,agents:[...baseOfficeData.agents,...childChats.map(child=>{
    const childProfile=chatProfiles[child.name]||{}, observed=!!teammateStatuses[child.name]?.sessionId||!!teammateStatuses[child.name]?.threadId;
    const state=teammateStatuses[child.name]?.state;
    const status=state==='running'?'working':state==='awaiting_approval'?'waiting':state==='idle'?'idle':state==='error'?'error':observed?'offline':'recorded';
    const labels:Record<string,string>={working:'Working',waiting:'Needs your input',idle:'Ready',error:'Needs attention',offline:'Needs refresh',recorded:'Not started'};
    return {id:`chat:${child.name}`,name:childProfile.projectLabel||child.name,role:childProfile.executionRole==='lead'?'Team lead':'Specialist',model:teammateStatuses[child.name]?.model||'',isSupervisor:false,delegated:false,conversation:true,observed,stale:status==='offline',status,statusLabel:labels[status],reportsTo:childProfile.supervisedBy===team?snapshot?.team?.leaderName:`chat:${childProfile.supervisedBy}`,assignment:childProfile.goal||''};
  })]};
  const orderedChats=chatHierarchy(teams,chatProfiles,deletedChats);
  const tasks = phases.flatMap(status => (snapshot?.tasks?.[status] || []).map((t: RecordData) => ({...t, status})));
  const members = snapshot?.members || [];
  const planReady = !demo && runtime.connected && runtime.state === 'idle' && runtime.mode === 'plan' && runtime.planReady;
  const running = ['starting','running','awaiting_approval','stopping'].includes(runtime.state);
  const name = (id: string) => profile.members?.[id]?.displayName || id || 'Unassigned';
  const approvalCount = (runtime.pendingApprovals || []).length;
  const completedTasks = tasks.filter(t => t.status === 'completed').length;
  const evidenceOpen = consoleOpen && (!!team || !!runtime.threadId || events.length > 0 || approvalCount > 0);

  async function loadHistory(){if(historyCursor===null||historyBusy)return;const target=team;setHistoryBusy(true);try{const value=await request(`/api/runtime/${encoded}/history?before=${historyCursor}`);if(selected.current===target){setHistoryCursor(value.before);setEvents(old=>mergeRuntimeEvents(old,value.events||[],10000).sort((a:RecordData,b:RecordData)=>a.seq-b.seq))}}catch(e:any){if(selected.current===target)setError(e.message)}finally{if(selected.current===target)setHistoryBusy(false)}}

  async function refreshList() {
    const [list, management] = await Promise.all([request('/api/overview'), request('/api/workspaces/chat-management')]);
    setTeams(list);
    setDeletedChats(management.deleted || []);
    await loadLabels(list);
  }
  useEffect(() => {
    let cancelled = false;
    Promise.all([request('/api/health'), request('/api/workspaces'), request('/api/overview'), request('/api/workspaces/chat-management')])
      .then(([h, w, list, management]) => { if (!cancelled) { setHealth(h); setModels(w.models || []); setTeams(list); setDeletedChats(management.deleted || []); loadLabels(list); } })
      .catch(e => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refreshList().catch(() => {});
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (dialog) modal.current?.showModal(); else modal.current?.close();
  }, [dialog]);
  useEffect(() => {
    setOfficeExample(false);setNativeRoster({workers:[]});setGraphWorker('');
    if (!team) { setRuntimeTeam(''); setSnapshot(null); setProfile({}); setRuntime({state:'offline'}); setEvents([]); setConsoleOpen(false); return; }
    setHistoryCursor(null);setHistoryBusy(false);setNativeRoster({workers:[]});setGraphWorker('');
    let cancelled = false, inFlight = false, cursor = 0;
    setSnapshot(null); setProfile({}); setRuntime({state: 'offline'}); setEvents([]); setMember(''); setConsoleOpen(false);
    request(`/api/runtime/${encoded}/history`).then(history=>{if(!cancelled){setHistoryCursor(history.before);setEvents(old=>mergeRuntimeEvents(old,history.events||[],10000).sort((a:RecordData,b:RecordData)=>a.seq-b.seq));}}).catch(()=>{});
    const poll = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const [s, p, r, feed] = await Promise.all([
          request(`/api/team/${encoded}`), request(`/api/company/${encoded}`),
          request(`/api/runtime/${encoded}/status`), request(`/api/runtime/${encoded}/events?after=${cursor}`),
        ]);
        if (cancelled) return;
        setSnapshot(s); setProfile(p); setRuntime(r); setRuntimeTeam(team);
        cursor = feed.nextSeq ?? cursor;
        setEvents(old => mergeRuntimeEvents(old, feed.events || [],10000).sort((a:RecordData,b:RecordData)=>a.seq-b.seq));
      } catch (e: any) { if (!cancelled) setError(e.message); }
      finally { inFlight = false; }
    };
    poll(); const timer = setInterval(poll, 900);
    return () => { cancelled = true; clearInterval(timer); };
  }, [team]);
  useEffect(()=>{
    if(view!=='map'||!childChatIds)return;
    let cancelled=false;
    const ids=childChatIds.split('|');
    const poll=async()=>{
      const rows=await Promise.allSettled(ids.map(async id=>[id,await request(`/api/runtime/${encodeURIComponent(id)}/status`)]));
      if(!cancelled)setTeammateStatuses(old=>({...old,...Object.fromEntries(rows.flatMap(row=>row.status==='fulfilled'?[row.value]:[]))}));
    };
    void poll();const timer=setInterval(poll,2000);
    return()=>{cancelled=true;clearInterval(timer)};
  },[view,childChatIds]);
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
  useEffect(() => {
    const keydown = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat(); } };
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, []);
  const chooseView = (next: string) => { setView(next); setMobileNav(false); };
  function contactAgent(id:string){
    if(officeExample||id===snapshot?.team?.leaderName){setOfficeExample(false);chooseView('run');requestAnimationFrame(()=>composerInput.current?.focus());return;}
    if(id.startsWith('chat:')){const target=id.slice(5);navigation.current++;selected.current=target;setTeam(target);chooseView('run');return;}
    const worker=(nativeRoster.workers||[]).find((w:RecordData)=>`native-${w.threadId}`===id||snapshot?.members?.some((m:RecordData)=>m.name===id&&m.agentId===w.threadId));
    if(worker){setGraphWorker('');requestAnimationFrame(()=>{setGraphWorker(worker.threadId);document.getElementById('office-worker-controls')?.scrollIntoView({block:'center',behavior:'instant'});});}
    else{setMember(id);setDialog('message');}
  }
  function openOfficeTask(id:string){
    if(officeExample){setNotice('Example assignment only. Start a conversation to plan real work.');return;}
    const value=tasks.find(t=>t.id===id);if(value){setTask(value);setDialog('task-detail');}
  }
  async function action(path: string, body: RecordData = {}) {
    if (busy) return;
    const startedTeam = team; setBusy(true); setError('');
    try { const result = await request(path, body); return result; }
    catch (e: any) { if (selected.current === startedTeam) setError(e.message); }
    finally { setBusy(false); }
  }
  async function loadLabels(list: RecordData[]) {
    const profiles = await Promise.allSettled(list.map(async t => [t.name, await request(`/api/company/${encodeURIComponent(t.name)}`)]));
    const loaded=Object.fromEntries(profiles.flatMap(p=>p.status==='fulfilled'?[p.value]:[]));
    setChatProfiles(old=>({...old,...loaded}));
    setChatLabels(old=>({...old,...Object.fromEntries(Object.entries(loaded).map(([name,value]:any)=>[name,value.projectLabel]))}));
  }
  function newChat() {
    navigation.current++; selected.current = ''; setTeam(''); chooseView('run'); setModel('auto'); setProvider('codex'); setError(''); setNotice('');
    const generation=navigation.current;request('/api/routing').then(r=>{if(navigation.current===generation&&!selected.current&&r.settings?.preferredSupervisor){setProvider(r.settings.preferredSupervisor.provider);setModel(r.settings.preferredSupervisor.model)}}).catch(()=>{});
    requestAnimationFrame(() => composerInput.current?.focus());
  }
  async function openTeammate(){
    if(!team||!profile.projectRoot)return;
    setError('');setTeamModels([]);setTeamChoice('');setDialog('teammate');
    try{
      const result=await request('/api/providers');
      const choices=(result.providers||[]).filter((row:RecordData)=>row.id!=='openai-compatible'&&row.runtimeReady&&row.authentication==='signed_in').flatMap((row:RecordData)=>(row.models||[]).map((id:string)=>({provider:row.id,model:id,label:`${row.label||row.id} · ${id.replace(/^account:[^/]+\//,'')}`})));
      setTeamModels(choices);
      const preferred=choices.find((item:{provider:string;model:string})=>item.provider==='codex'&&item.model==='gpt-5.6-terra')||choices[0];
      setTeamChoice(preferred?`${preferred.provider}\x1f${preferred.model}`:'');
    }catch(e:any){setError(e.message||'Could not load connected models.');}
  }
  async function chatAction(target: string, action: string) {
    try {
      const result = await request(`/api/workspaces/${encodeURIComponent(target)}/chat/${action}`, {});
      if (action === 'export-json' || action === 'export-markdown') {
        if (result.savedPath) {
          setNotice(result.revealed ? 'Export saved and shown in Finder.' : `Export saved: ${result.savedPath}`); return;
        }
        const blob = new Blob([result.content], {type: result.mimeType});
        const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = result.filename;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 30000);
        setNotice('Transcript export prepared. Check your downloads.'); return;
      }
      if (action === 'delete') {
        setDeletedChats(old => [...new Set([...old, target])]);
        if (team === target) newChat();
        setNotice('Chat moved to Trash. Restore it from the sidebar when you need it.');
      } else if (action === 'restore') {
        setDeletedChats(old => old.filter(name => name !== target));
        selected.current=target;setTeam(target);chooseView('run');setNotice('Chat restored.');
      } else if (action === 'reveal-folder') setNotice('Opened this chat’s bound folder in Finder.');
    } catch (e:any) { setError(e.message); }
  }
  async function send() {
    if (busy || (!draft.trim() && !images.length)) return;
    if (demo || missingCodex) { setError('Connect Codex in Settings to send messages. Your draft is kept.'); return; }
    if (selectedProvider === 'openai-compatible' && images.length) { setError('Custom API chats currently support text only. Remove the image attachments or choose a model with image support.'); return; }
    const sentDraft = draft; const sentImages = images; const prompt = draft.trim() || 'Please review the attached images.'; const sourceTeam = team;
    const sourceNavigation = navigation.current; const requestedModel = model;
    let target = team;
    setBusy(true); setError(''); setNotice('');
    try {
      if (!target) {
        const created = await request('/api/workspaces', {label: prompt.slice(0,80), goal: prompt.slice(0,2000)});
        target = created.team;
        // Move the draft before starting the provider so failures are recoverable.
        setDrafts(old => ({...old, '': old[''] === sentDraft ? '' : old[''], [target]: sentDraft}));
        if (navigation.current === sourceNavigation && selected.current === sourceTeam) { selected.current = target; setTeam(target); setProfile(created.company); }
        setImageDrafts(old => ({...old, '': (old['']||[]).filter(i=>!sentImages.some(s=>s.id===i.id)), [target]:sentImages}));
        setChatLabels(old => ({...old,[target]:created.company.projectLabel}));
        await refreshList();
      }
      const attachmentIds=[];
      for(const item of sentImages){
        const key=`${target}:${item.id}`;
        if(!uploadedImages.current[key]){const uploaded=await request(`/api/attachments/${encodeURIComponent(target)}`,{name:item.name,mimeType:item.mimeType,dataBase64:item.dataBase64});uploadedImages.current[key]=uploaded.id}
        attachmentIds.push(uploadedImages.current[key]);
      }
      // Select the action from this chat’s fresh status, never a previous chat’s render.
      const status = await request(`/api/runtime/${encodeURIComponent(target)}/status`);
      await request(`/api/runtime/${encodeURIComponent(target)}/${status.connected ? 'send' : 'start'}`, {prompt, provider:(status.providerBound||status.threadId)?status.provider||provider:provider, model: status.model || requestedModel, workMode: provider === 'openai-compatible' && workMode === 'full' ? 'auto' : workMode, attachmentIds});
      setDrafts(old => ({...old,[target]: old[target] === sentDraft ? '' : old[target]}));
      setImageDrafts(old=>({...old,[target]:(old[target]||[]).filter(i=>!sentImages.some(s=>s.id===i.id))}));
      setTeams(old=>old.map(chat=>chat.name===target?{...chat,lastActivityAt:Date.now()}:chat));
      void refreshList().catch(() => {});
      if (selected.current === target) chooseView('run');
    } catch (e: any) {
      if (selected.current === target) setError(e.message);
    } finally { setBusy(false); }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    let result;
    if (dialog === 'teammate') {
      const [chosenProvider,chosenModel]=teamChoice.split('\x1f');
      if(!chosenProvider||!chosenModel){setError('Choose a connected model for this teammate.');return;}
      const parent=team, assignment=String(data.goal||'').trim();
      result=await action('/api/workspaces',{label:String(data.label||'').trim()||'New teammate',project:profile.projectRoot,goal:assignment,executionRole:data.executionRole,supervisedBy:parent});
      if(result){
        const child=result.team;
        setChatProfiles(old=>({...old,[child]:result.company}));
        setChatLabels(old=>({...old,[child]:result.company.projectLabel}));
        await refreshList();
        const started=await action(`/api/runtime/${encodeURIComponent(child)}/start`,{prompt:assignment,provider:chosenProvider,model:chosenModel,workMode:'auto'});
        navigation.current++;selected.current=child;setTeam(child);chooseView('run');
        setNotice(started?'Teammate started. Its own conversation and status are linked to this project.':'Teammate chat was created, but its model did not start. Your assignment is retained.');
      }
    } else if (dialog === 'workspace' || dialog === 'attach') {
      result = await action(dialog === 'attach' ? `/api/workspaces/${encoded}/attach` : '/api/workspaces', data);
      if (result) {
        await refreshList();
        setTeam(result.team);
        if (dialog !== 'attach') setDrafts(old => ({...old, [result.team]: String(data.goal || drafts[''] || '')}));
        setProfile(result.company);
        setNotice('Project connected. Send a message whenever you’re ready.');
        chooseView('run');
      }
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
  const emptyChat = !events.some(e => ['message.user','message.completed','message.delta'].includes(e.type));
  const openProject = () => {setFolderPath('');setDialog(team && profile.workspaceKind === 'managed' && !runtime.threadId && !runtime.project ? 'attach' : 'workspace')};
  async function chooseFolder() {
    const requestedDialog=dialog; const requestedNavigation=navigation.current;
    setPickingFolder(true);setError('');
    const stillHere=()=>activeDialog.current===requestedDialog&&navigation.current===requestedNavigation;
    try {const choice=await request('/api/folders/pick',{});if(stillHere()&&!choice.cancelled&&choice.path)setFolderPath(choice.path)}
    catch(e:any){if(stillHere())setError(e.message || 'Folder picker is unavailable. You can paste a path.')}finally{setPickingFolder(false)}
  }
  const composer = <div className="chat-composer-wrap"><div className="chat-composer" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy&&!demo&&selectedProvider!=='openai-compatible')addImages(e.dataTransfer.files)}}>
    <ImageAttachments images={images} onChange={items=>setImageDrafts(old=>({...old,[team]:items}))} disabled={busy||demo||selectedProvider==='openai-compatible'} onError={setError}/>
    <textarea ref={composerInput} aria-label="Direction for the team" value={draft} maxLength={24000} onChange={e => setDrafts(old => ({...old,[team]:e.target.value}))}
      onPaste={e=>{if(e.clipboardData.files.length){e.preventDefault();if(!busy&&!demo&&selectedProvider!=='openai-compatible')addImages(e.clipboardData.files)}}}
      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }}
      placeholder="Ask anything, or describe what you want to build…" rows={3}/>
    <div className="chat-composer-tools">
      <button className="attach-button" title="Optional: work with an existing folder" onClick={openProject}><FolderPlus size={17}/><span>{profile.workspaceKind === 'project' ? 'Project attached' : 'Add project'}</span></button>
      <label className="work-mode-picker"><span className="sr-only">Work mode</span><select aria-label="Work mode" value={runtime.threadId ? (runtime.accessMode==='full'?'full':runtime.mode === 'execute' ? 'auto' : 'plan') : selectedProvider==='openai-compatible'&&workMode==='full'?'auto':workMode} disabled={busy || demo || (!!runtime.threadId && (!runtime.connected || running || runtime.mode==='plan'))} onChange={async e => {const next=e.target.value;if(runtime.threadId){const r=await action(`/api/runtime/${encoded}/access`,{accessMode:next==='full'?'full':'workspace'});if(r)setRuntime(r)}else{setWorkMode(next);try {localStorage.setItem('hq.workMode',next)} catch {}}}}><option value="auto">Work automatically</option><option value="full" disabled={selectedProvider==='openai-compatible'}>Full access</option><option value="plan" disabled={!!runtime.threadId}>Plan first</option></select></label>
      <VoiceInput key={team} onUseSystemDictation={()=>{chooseView('run');requestAnimationFrame(()=>composerInput.current?.focus())}} disabled={busy||demo} onError={setError} onTranscript={text=>setDrafts(old=>({...old,[team]:((old[team]||'')+' '+text).trim().slice(0,24000)}))}/>
      <div className="composer-spacer"/>
      <button className="model-trigger" aria-label="Choose model" onClick={() => setDialog('models')}><Sparkles size={13}/>{(runtime.model || model) === 'auto' ? 'Auto · Supervisor' : (runtime.model || model).replace('gpt-','GPT ').replaceAll('-',' ')}<ChevronDown size={12}/></button>
      {running && <button className="stop-button" onClick={() => action(`/api/runtime/${encoded}/stop`)}>Stop</button>}
      <button className="chat-send" aria-label={busy ? 'Sending message' : 'Send message'} disabled={busy || (!draft.trim() && !images.length) || demo || missingCodex || runtime.budget?.blocked} onClick={send}><ArrowUp size={19}/></button>
    </div>
  </div><p className="composer-hint">{demo ? 'Demo preview · sending is disabled' : runtime.budget?.blocked ? 'Budget reached. Adjust it in Activity to continue.' : missingCodex ? 'Codex is unavailable. Open Settings to check your connection.' : selectedProvider==='openai-compatible' ? 'Text-only conversation · no file, image, browser or worker tools · Enter to send' : runtime.accessMode==='full' || (!runtime.threadId&&workMode==='full') ? 'Full machine and network access for this chat · native account policies still apply' : ['claude','kimi','zai'].includes(selectedProvider) ? `${selectedProvider === 'zai' ? 'Z.ai' : selectedProvider === 'kimi' ? 'Kimi' : 'Claude'} uses its native permission controls · Enter to send` : runtime.mode === 'execute' || (!runtime.threadId && workMode === 'auto') ? 'Plans, builds and checks in this workspace · Enter to send' : 'Plan first · review the plan before file changes.'}</p></div>;
  return <div className="desktop-frame chat-app">
    <div className="app-shell workbench">
    {mobileNav && <button className="nav-scrim" aria-label="Dismiss navigation" onClick={() => setMobileNav(false)}/>}
    <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}>
      <div className="brand"><span className="brand-mark"><Layers3 size={21}/></span><b>Company HQ</b><button className="icon-btn close-nav" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X/></button></div>
      <button className="new-chat-button" onClick={newChat}><SquarePen size={17}/>New chat<span>⌘ N</span></button>
      <nav aria-label="Workspace tools">
        {([['run',MessageCircle,'Chat'],['map',Network,'Office'],['board',LayoutGrid,'Tasks'],['activity',Activity,'Activity'],['files',Files,'Files'],['provider-tasks',Layers3,'Provider tasks']] as const).map(([id,Icon,label]) => <button key={id} className={view === id ? 'active' : ''} disabled={!team && !['run','map','provider-tasks'].includes(id)} onClick={() => chooseView(id)}><Icon size={17}/>{label}{id==='board' && tasks.length>0 && <small>{tasks.length}</small>}</button>)}
      </nav>
      <div className="recent-label">Your chats</div>
      <div className="chat-history" aria-label="Recent chats">{orderedChats.length ? orderedChats.map(({team:t,depth}) => <div className={`chat-row ${depth?'is-child':''}`} style={{paddingLeft:depth*12}} key={t.name}><button title={chatLabels[t.name] || t.name} className={team===t.name ? 'selected' : ''} onClick={() => {navigation.current++;selected.current=t.name;setTeam(t.name);chooseView('run');setError('');setNotice('')}}>{depth?<MessageCircle size={14}/>:<Layers3 size={14}/>}<span>{chatLabels[t.name] || t.name.replace(/-[a-f0-9]{6}$/, '').replaceAll('-',' ')}</span></button><ChatMenu name={chatLabels[t.name] || t.name} onExport={kind=>chatAction(t.name,kind==='json'?'export-json':'export-markdown')} onReveal={()=>chatAction(t.name,'reveal-folder')} onDelete={()=>chatAction(t.name,'delete')} onRestore={()=>chatAction(t.name,'restore')}/></div>) : <p>Your conversations will appear here.<br/>Start anywhere.</p>}{teams.filter(t=>deletedChats.includes(t.name)).length>0&&<><div className="recent-label">Trash</div>{teams.filter(t=>deletedChats.includes(t.name)).map(t=><div className="chat-row" key={t.name}><button className="trashed-chat" title={chatLabels[t.name] || t.name} onClick={()=>chatAction(t.name,'restore')}><MessageCircle size={14}/><span>{chatLabels[t.name] || t.name.replace(/-[a-f0-9]{6}$/, '').replaceAll('-',' ')}</span></button><ChatMenu name={chatLabels[t.name] || t.name} trashed onExport={()=>{}} onReveal={()=>{}} onDelete={()=>{}} onRestore={()=>chatAction(t.name,'restore')}/></div>)}</>}</div>
      <div className="sidebar-bottom"><details><summary><Layers3 size={16}/>More tools<ChevronDown size={14}/></summary><nav>{[['memory',Brain,'Shared memory'],['decisions',Scale,'Why this stack']].map(([id,Icon,label]:any) => <button key={id} onClick={() => chooseView(id)}><Icon size={16}/>{label}</button>)}</nav></details><button onClick={() => chooseView('guide')}><CircleHelp size={17}/>How to use</button><button onClick={() => chooseView('system')}><Settings2 size={17}/>Settings<span className={`connection-dot ${health.capabilities?.codex?.available ? 'available' : ''}`}/></button></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><button className="icon-btn mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu/></button><div className="chat-title">{team&&chatProfiles[team]?.supervisedBy&&chatProfiles[chatProfiles[team].supervisedBy]&&<button className="chat-parent-link" onClick={()=>{const parent=chatProfiles[team].supervisedBy;navigation.current++;selected.current=parent;setTeam(parent);chooseView('run')}}>{chatLabels[chatProfiles[team].supervisedBy]||'Project'} /</button>}<b>{view === 'provider-tasks' ? 'Provider tasks' : view === 'system' ? 'Settings' : team ? chatLabels[team] || profile.projectLabel || 'Chat' : 'New chat'}</b>{team && view === 'run' && <span>{profile.executionRole==='lead'?'Team lead':profile.executionRole==='worker'?'Specialist':profile.workspaceKind === 'managed' ? 'Just a conversation' : 'Project supervisor'}</span>}</div><div className="top-controls">{demo && <span className="demo-badge">Demo</span>}{team && <>{profile.executionRole!=='worker'&&<button className="subtle-button" onClick={openTeammate}><SquarePen size={16}/><span>New teammate</span></button>}<button className="subtle-button" onClick={() => chooseView('map')}><Network size={16}/><span>Office</span></button><button className={`icon-btn ${evidenceOpen ? 'is-selected' : ''}`} aria-label="Toggle activity panel" onClick={() => setConsoleOpen(!consoleOpen)}><PanelRightOpen size={18}/></button></>}</div></header>
      {error && <div className="error-banner" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X/></button></div>}
      {(notice||draftError) && <div className="notice-banner" role="status">{draftError||notice}</div>}
      {runtime.routingStatus?.message&&<div className="notice-banner" role="status">{runtime.routingStatus.message}</div>}
      {runtime.budget?.blocked && <div className="approval-bar"><div><b>Chat allowance reached</b><p>{runtime.budget.limitTokens > 0 ? `${Math.round(runtime.budget.usedTokens / runtime.budget.limitTokens * 100)}% used · 0% remaining.` : 'Local allowance reached.'} This chat is paused for new actions. Check Settings for your separate account limits.</p></div><button className="small-button" onClick={() => setDialog('budget')}>Adjust budget</button></div>}
      {planReady && <div className="approval-bar"><div><b>Your plan is ready</b><p>Happy with the plan? Let the team start working.</p></div><button className="primary-button" disabled={busy || runtime.budget?.blocked} onClick={() => { action(`/api/runtime/${encoded}/execute`); chooseView('run'); }}>Approve plan & start execution</button></div>}
      <div className={`work-area ${evidenceOpen ? 'with-inspector' : ''}`}>
        <section className={`stage ${view === 'map' ? 'map-stage' : ''}`}><React.Suspense fallback={<div className="view-loading" role="status">Opening {view==='map'?'team':view}…</div>}>
          {view === 'run' && <ChatView assignment={{...profile,supervisedBy:chatLabels[profile.supervisedBy]||profile.supervisedBy}} onFullAccess={runtime.provider==='zai' && runtime.accessMode!=='full' && runtime.mode!=='plan' ? async(id)=>{const access=await action(`/api/runtime/${encoded}/access`,{accessMode:'full'});if(access){setRuntime(access);await action(`/api/runtime/${encoded}/approve`,{requestId:id,decision:'approve'})}} : undefined} historyControl={historyCursor!==null?<button className="small-button" disabled={historyBusy} onClick={loadHistory}>{historyBusy?'Loading…':'Load earlier messages'}</button>:null} key={team || 'new'} events={events} runtime={runtime} empty={emptyChat} composer={composer} onDraft={text => {setDrafts(old => ({...old,[team]:text}));composerInput.current?.focus()}} busy={busy} demo={demo}
            onApproval={(requestId,decision) => action(`/api/runtime/${encoded}/approve`,{requestId,decision})} onRespond={(requestId,response) => action(`/api/runtime/${encoded}/respond`,{requestId,response})}/>}
          {view === 'provider-tasks' && <NativeTasks demo={demo}/>}
          {view === 'files' && team && <ProjectFiles key={team} team={team} runtime={runtime} demo={demo}/>}
          {view === 'activity' && <RunOverview runtime={runtime} events={events as any} demo={demo} connectedProject={!!team} registeredCount={members.length} completedCount={completedTasks} taskCount={tasks.length} onConnect={openProject} onConsole={() => chooseView('run')} onSystem={() => chooseView('system')} onBudget={() => setDialog('budget')} onDraft={text => {setDrafts(old => ({...old,[team]:text}));chooseView('run')}}/>}
          {view === 'guide' && <OperatingGuide demo={demo} health={health} runtime={runtime}/>}
          {view === 'map' && <><div className="office-switcher"><button aria-pressed={teamView==='office'} onClick={()=>setTeamView('office')}><Layers3 size={15}/>Office</button><button aria-pressed={teamView==='graph'} disabled={!snapshot||officeExample} onClick={()=>setTeamView('graph')}><Network size={15}/>Team map</button>{officeExample&&<button className="office-return" onClick={()=>setOfficeExample(false)}>Leave example</button>}{!officeExample&&<button className="office-return" onClick={()=>{setTeamView('office');setOfficeExample(true)}}>Preview example</button>}</div>{teamView==='office'?<OfficeView key={`${team}-${officeExample}`} {...officeData} title={officeExample?'Good work happens together.':team?profile.projectLabel||'Your team, together.':'Your next idea starts here.'} connected={!!runtime.connected} example={officeExample} onChat={()=>{setOfficeExample(false);chooseView('run');requestAnimationFrame(()=>composerInput.current?.focus())}} onExample={()=>setOfficeExample(true)} onContact={contactAgent} onTask={openOfficeTask}/>:snapshot&&<div className="graph-host"><TeamGraph snapshot={graphData.snapshot as any} company={graphData.company} runtime={{...runtime,children:nativeRoster.workers||[]}} onSelectMember={contactAgent} onSelectTask={openOfficeTask}/></div>}{team&&!officeExample&&<div id="office-worker-controls"><WorkersPanel key={team} team={team} connected={!!runtime.connected} onData={setNativeRoster} selectedThread={graphWorker} onBackToChat={()=>chooseView('run')}/></div>}</>}
          {view === 'board' && <div className="board-view"><div className="view-heading"><div><h2>Tasks</h2><p>Assignments, progress, and what comes next.</p></div><button className="small-button" onClick={() => setDialog('task')}>Add task</button></div><PlanPanel key={team} team={team} currenttasks={tasks} currentmembers={members.map((m:RecordData)=>m.name)} onDraft={text=>{setDrafts(old=>({...old,[team]:text}));chooseView('run')}}/><div className="kanban">{phases.map(status => <section className="column" key={status}><header><h3>{phaseNames[status]}</h3></header>{tasks.filter(t=>t.status===status).map(t=><button className="task-card" key={t.id} onClick={()=>{setTask(t);setDialog('task-detail')}}><h4>{t.subject}</h4><p>{t.description}</p><footer>{name(t.owner)}</footer></button>)}</section>)}</div></div>}
          {view === 'decisions' && <DecisionCenter data={decisions} loading={decisionsLoading} error={decisionError}/>}
          {view === 'memory' && <div className="memory-view"><h2>Shared project memory</h2><p>{demo ? 'Synthetic fixtures; no memory server is called.' : 'Scoped Ruflo decisions, not your entire chat history.'}</p>{memoryError && <p role="status">{memoryError}</p>}{notes.map(n=><article className="note" key={n.key}><h3>{n.value?.title || n.key}</h3><pre>{typeof n.value === 'string' ? n.value : n.value?.content || JSON.stringify(n.value,null,2)}</pre></article>)}</div>}
          {view === 'system' && <Connections health={health} runtime={runtime} events={events} onRefresh={async()=>{setHealth(await request('/api/health'))}} onModels={()=>setDialog('models')}/>}
        </React.Suspense></section>
        {evidenceOpen && <aside className="inspector"><header className="inspector-header"><h2>Activity</h2><button className="icon-btn" aria-label="Close activity" onClick={() => setConsoleOpen(false)}><X size={18}/></button></header><div className="inspector-scroll"><p className="activity-caption">{running ? 'The supervisor is working.' : runtime.connected ? 'Connected. Ready for your next message.' : 'Activity appears when you send a message.'}</p>{(runtime.children || []).map((child:RecordData) => <article className="runtime-event" key={child.threadId}><header>Teammate</header><pre>{child.threadId}</pre><p>{child.state || 'State not reported'}</p></article>)}{events.filter(e => !['message.delta','message.completed','message.user'].includes(e.type)).map(e => <article className="runtime-event" key={e.seq}><header>{e.type.replaceAll('.',' · ')}</header>{e.type==='usage' ? <p>Usage updated. Open Usage & details for percentages.</p> : <pre>{e.data?.text || [e.data?.title || e.data?.message, e.data?.status].filter(Boolean).join(' · ') || 'Recorded runtime event'}</pre>}</article>)}<button className="small-button" onClick={() => {chooseView('activity');setConsoleOpen(false)}}>Usage & details</button></div></aside>}
      </div>
      {view !== 'run' && team && <div className="back-to-chat"><button onClick={() => chooseView('run')}><MessageCircle size={16}/>Back to conversation</button></div>}
    </main>
    <dialog ref={modal} className="modal" onCancel={()=>setDialog('')}><p className="dialog-error" role={error?'alert':undefined}>{error}</p><button className="modal-close icon-btn" aria-label="Close dialog" onClick={()=>setDialog('')}><X/></button>
      {dialog==='models'?<ModelPicker models={models} model={model} provider={provider} runtime={runtime} demo={demo} onChoose={(engine,id)=>{setProvider(engine);setModel(id);if(engine==='openai-compatible'&&workMode==='full')setWorkMode('auto');setDialog('')}} onSettings={()=>{setDialog('');chooseView('system')}}/>:dialog==='help'?<><h2>One workspace for the whole team</h2><p>Start chatting → optionally attach a project or images → choose Work automatically, Full access, or Plan first → follow the work → review the result.</p><p>Ruflo memory and code indexes are optional capabilities. Registered roles are not proof that workers are running. No model, billing plan or quota is invented.</p><p>The licensed Munder Difflin procedural characters, Agent Teams AI graph, Beads task engine, scoped Ruflo memory and native Codex or Claude Code adapters are reused. Each provider exposes its own capabilities.</p><a href="/api/source">Application source and retained upstream licenses</a></>:dialog==='task-detail'?<><h2>{task?.subject}</h2><p>{task?.description}</p><label>Task status<select aria-label="Task status" value={task?.status||'pending'} onChange={async e=>{const next=e.target.value;const r=await action(`/api/task/${encoded}/${encodeURIComponent(task?.id)}`,{status:next});if(r)setTask(t=>({...t,status:next}))}}>{phases.map(p=><option value={p} key={p}>{phaseNames[p]}</option>)}</select></label><p>Manual status changes do not claim that tests passed.</p></>:<form key={dialog} onSubmit={submit}><h2>{dialog==='workspace'?'Chat with a project':dialog==='attach'?'Add project':dialog==='teammate'?'Start a teammate':dialog==='message'?`Message ${name(member)}`:dialog==='budget'?'Set usage budget':'Add a task'}</h2>{dialog==='teammate'?<><p>Give this teammate a focused assignment. Their work appears as a separate conversation under this project.</p><label>Teammate or task name<input name="label" required maxLength={120} placeholder="For example, review the provider adapter"/></label><label>Role<select name="executionRole" defaultValue="lead"><option value="lead">Team lead</option><option value="worker">Specialist</option></select></label><label>Available model<select name="engine" required value={teamChoice} onChange={event=>setTeamChoice(event.target.value)}>{teamModels.length?teamModels.map(item=><option key={`${item.provider}:${item.model}`} value={`${item.provider}\x1f${item.model}`}>{item.label}</option>):<option value="">No connected models found</option>}</select></label><label>Assignment<textarea name="goal" required maxLength={2000} placeholder="What should they deliver and how will you know it is done?"/></label><p>HQ starts this model after you create the teammate. Its native tools and permissions still apply. A listed model can still be unavailable on your account; HQ reports that when it starts. Open Office to follow real status.</p></>:(dialog==='workspace'||dialog==='attach')?<><label>Chat name (optional)<input name="label" maxLength={120} placeholder="A name for this project"/></label><label>Project folder<div className="folder-input-row"><input name="project" required value={folderPath} onChange={e=>setFolderPath(e.target.value)} placeholder="Choose a folder, or paste its path"/><button type="button" className="small-button" onClick={chooseFolder} disabled={pickingFolder || demo}>{pickingFolder ? 'Choosing…' : 'Choose folder…'}</button></div></label><label>First message (optional)<textarea name="goal" maxLength={2000} defaultValue={draft} placeholder="What would you like to work on?"/></label><p>{team && runtime.threadId ? 'This opens a separate project chat. Your current conversation stays here.' : 'A project is optional. This connects its files for your next message.'}</p></>:dialog==='message'?<><label>Direction<textarea name="content" required maxLength={12000}/></label><p>This stores an inbox message; it does not promise wake-up or acknowledgement.</p></>:dialog==='budget'?<><UsagePanel runtime={runtime}/><label>Chat allowance (tokens)<input name="limitTokens" type="number" min="0" max="20000000" required defaultValue={runtime.budget?.limitTokens ?? 0}/></label><label>Action gate<select name="enforced" defaultValue={String(runtime.budget?.enforced ?? false)}><option value="true">Block next runtime action at the ceiling</option><option value="false">Track only</option></select></label><p>This optional chat allowance counts reported tokens, including reused context. Your 5-hour and weekly account limits are shown in Settings and cannot be changed here. Use 0 for no local ceiling.</p></>:<><label>Task<input name="subject" required maxLength={2000}/></label><label>Owner<select name="owner" defaultValue={snapshot?.team?.leaderName||''}><option value="">Unassigned</option>{members.map((m:RecordData)=><option key={m.name} value={m.name}>{name(m.name)}</option>)}</select></label><label>Expected result<textarea name="description" maxLength={12000}/></label></>}<footer><button type="button" className="small-button" onClick={()=>setDialog('')}>Cancel</button><button className="primary-button" disabled={busy}>{dialog==='teammate'?'Create & assign':(dialog==='workspace'||dialog==='attach')?'Connect project':dialog==='message'?'Queue message':dialog==='budget'?'Save budget':'Create task'}</button></footer></form>}
    </dialog>
    </div>
  </div>;
}
