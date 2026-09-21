import React from 'react';
import {Brain, Code2, Cpu, Check, RefreshCw, ChevronRight, PlugZap} from 'lucide-react';
type Data = Record<string,any>;
export default function Connections({health,runtime,onRefresh,onModels}:{health:Data;runtime:Data;onRefresh:()=>Promise<void>;onModels:()=>void}) {
  const [refreshing,setRefreshing]=React.useState(false);
  const [checked,setChecked]=React.useState(()=>new Date());
  const [error,setError]=React.useState('');
  const caps=health.capabilities||{};
  const tools=[{id:'rufloMemory',name:'Shared memory',description:'Keeps useful decisions organized for each project.',icon:Brain},{id:'codebaseMemory',name:'Code understanding',description:'Helps agents navigate code when a project is attached.',icon:Code2}];
  async function refresh(){setRefreshing(true);setError('');try{await onRefresh();setChecked(new Date())}catch(e:any){setError(e.message||'Could not check setup. Try again.')}finally{setRefreshing(false)}}
  return <div className="connections-view"><header><span className="eyebrow">SETTINGS</span><h1>Your workspace, connected.</h1><p>The essentials for your team. Setup is checked when the app opens.</p></header>
    <section className="connection-engine"><div className="engine-tile"><Cpu size={24}/></div><div><h2>Codex</h2><p>{health.mode==='demo'?'Demo mode · model calls disabled':runtime.connected?'Connected in this chat':caps.codex?.available?'Installed · sign-in is checked when you send':'Not found · install or connect the native Codex runtime'}</p></div><span className={`setup-badge ${caps.codex?.available?'ok':''}`}>{runtime.connected?'Connected':caps.codex?.available?'Installed':'Needs setup'}</span></section>
    <button className="supervisor-setting" onClick={onModels}><span><b>Supervisor model</b><small>{runtime.model || 'Automatic · Astra supervisor'}</small></span><span>Choose model<ChevronRight size={15}/></span></button>
    <div className="connections-heading"><h2>Tools your team can use</h2><span>Available when needed</span></div>
    <div className="connection-tools">{tools.map(({id,name,description,icon:Icon})=><article key={id}><span className="tool-tile"><Icon size={20}/></span><div><h3>{name}</h3><p>{description}</p>{!caps[id]?.available&&<small>{caps[id]?.reason||'Not installed'}</small>}</div><span className={`setup-badge ${caps[id]?.available?'ok':''}`}>{caps[id]?.available?<><Check size={12}/>Installed</>:'Unavailable'}</span></article>)}</div>
    <section className="provider-note"><PlugZap size={19}/><div><h3>How connection works</h3><p>Codex uses your existing sign-in. Sending your first message opens the connection for that chat. Checking setup does not start model work or import old chats.</p><h3>More engines</h3><p>Claude, Grok, Kimi, GLM, and Cursor cannot connect here yet. Each needs its own sign-in flow and tested adapter. Their models will appear as usable only after connection is verified.</p></div></section>
    {error&&<p role="alert">{error}</p>}<footer className="setup-footer"><span>Local setup checked · {checked.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span><button onClick={refresh} disabled={refreshing}><RefreshCw size={13} className={refreshing?'refreshing':''}/>{refreshing?'Checking…':'Check again'}</button></footer>
    <details className="technical-details"><summary>Technical details</summary><p>Local checks inspect installed components. They do not send model prompts or measure account quota. Provider permissions and sign-in are verified on connection.</p>{['frontend','routing','codex','rufloMemory','codebaseMemory'].map(id=><div key={id}><b>{id}</b><span>{caps[id]?.available?'Present':caps[id]?.reason||'Unavailable'}</span><code>{caps[id]?.path}</code></div>)}<p>Private app data: {health.stateRoot}</p></details>
  </div>;
}
