import React from 'react';
import { Brain, Check, ChevronRight, CircleAlert, Code2, Cpu, ExternalLink, PlugZap, RefreshCw, X } from 'lucide-react';
import RuntimeTools from './RuntimeTools';
import AccessGuide from './AccessGuide';
import RoutingSettings from './RoutingSettings';
import UsagePanel, { AccountUsage, type UsageWindow } from './UsagePanel';

type Data = Record<string, any>;
type Provider = { id: string; label?: string; installed?: boolean; cliInstalled?: boolean; desktopInstalled?: boolean; runtimeReady?: boolean; authentication?: string; verification?: string; reason?: string; helpUrl?: string; activity?: { message?: string; status?: string; time?: string }[]; models?: string[]; usageWindows?: UsageWindow[]; balances?: {currency:string;total_balance:string}[]; message?: string; authUrl?: string };
type Props = { health: Data; runtime: Data; events?: Data[]; onRefresh: () => Promise<void>; onModels: () => void };
const supported = new Set(['deepseek', 'openai-compatible', 'codex', 'claude', 'kimi', 'zai', 'cursor', 'grok', 'ollama']);
function safeAuthUrl(url?: string) { try { const value = new URL(url || ''); const hosts = new Set(['auth.openai.com', 'chatgpt.com', 'auth0.openai.com','claude.ai','console.anthropic.com','platform.claude.com','auth.anthropic.com','kimi.com','www.kimi.com','auth.kimi.com','code.kimi.com','kimi.ai','www.kimi.ai','auth.kimi.ai','code.kimi.ai','chat.z.ai','zcode.z.ai']); return value.protocol === 'https:' && !value.username && !value.password && !value.port && hosts.has(value.hostname) ? value.href : ''; } catch { return ''; } }
function status(provider: Provider) { if (provider.id==='openai-compatible') return provider.verification==='generation'?'Generation verified':provider.verification==='model_listing'?'Model listed':provider.authentication==='model_unavailable'?'Model not listed':'Configure endpoint'; if (provider.id==='deepseek') return provider.authentication==='signed_in'?'Connected':'API key needed'; if (provider.authentication === 'signed_in' && provider.runtimeReady) return 'Connected'; if (provider.authentication === 'signing_in') return 'Sign-in in progress'; if (['codex','claude','kimi','zai'].includes(provider.id) && !provider.runtimeReady) return provider.desktopInstalled ? 'Setup needed for HQ' : 'Runtime not found'; if (provider.authentication === 'sign_in_required') return 'Sign in required'; return provider.runtimeReady ? 'Check sign-in' : provider.installed ? 'App detected' : 'Not installed'; }
const nativeProviders = new Set(['codex', 'claude', 'kimi', 'zai']);
const setupGuides: Record<string, {url:string; label:string; instruction:string}> = {
  codex: {url:'https://developers.openai.com/codex/quickstart', label:'Set up Codex', instruction:'HQ needs the official Codex runtime on this device before it can use your account.'},
  claude: {url:'https://code.claude.com/docs/en/setup', label:'Set up Claude Code', instruction:'Claude Desktop is separate from Claude Code. HQ needs the Claude Code runtime to work with this account.'},
  kimi: {url:'https://moonshotai.github.io/kimi-code/en/guides/getting-started', label:'Set up Kimi Code', instruction:'HQ needs the Kimi Code runtime. Signing in to the desktop app alone does not connect coding tasks.'},
  zai: {url:'https://zcode.z.ai/en/docs/install', label:'Review Z Code setup', instruction:'HQ needs a compatible Z Code runtime. If the app was updated, its adapter may need a compatibility review.'},
};
function connectionStep(provider: Provider) {
  if (provider.authentication === 'signed_in' && provider.runtimeReady) return 'Ready for HQ tasks. Model access is confirmed when a task starts.';
  if (nativeProviders.has(provider.id) && !provider.runtimeReady) return provider.cliInstalled ? (provider.message || provider.reason || 'The installed runtime needs attention before HQ can use it.') : setupGuides[provider.id]?.instruction || 'Install the provider runtime, then check again.';
  if (provider.authentication === 'signing_in') return 'Finish the provider’s sign-in in your browser, then return to HQ.';
  if (nativeProviders.has(provider.id)) return 'Sign in with the provider’s official login. HQ will verify the connection afterward.';
  return provider.message || provider.reason || 'This provider is not connected to HQ yet.';
}
function toolActivity(events: Data[], tool: string) { const terms = tool === 'rufloMemory' ? ['ruflo', 'memory'] : ['codebase', 'code']; return events.filter(event => { const reported = String(event.data?.tool || event.data?.title || '').toLowerCase(); return (event.type === 'tool.started' || event.type === 'tool.completed' || event.type === 'tool.activity') && terms.some(term => reported.includes(term)); }).slice(-8).reverse(); }

export default function Connections({ health, runtime, events = [], onRefresh, onModels }: Props) {
  const [providers, setProviders] = React.useState<Provider[]>([]), [checked, setChecked] = React.useState<Date | null>(null), [refreshing, setRefreshing] = React.useState(false), [error, setError] = React.useState(''), [selected, setSelected] = React.useState<Provider | null>(null), [selectedTool, setSelectedTool] = React.useState<string | null>(null);
  const [apiKey,setApiKey]=React.useState('');
  const [customBaseUrl,setCustomBaseUrl]=React.useState(''),[customModel,setCustomModel]=React.useState(''),[customContext,setCustomContext]=React.useState('32768'),[customTemperature,setCustomTemperature]=React.useState('0.2');
  const dialogRef = React.useRef<HTMLDialogElement>(null); const caps = health?.capabilities || {};
  const tools = [{ id: 'rufloMemory', name: 'Shared memory', description: 'Keeps useful decisions organized for each project.', icon: Brain }, { id: 'codebaseMemory', name: 'Code understanding', description: 'Helps agents navigate code when a project is attached.', icon: Code2 }];
  const loadProviders = React.useCallback(async (check = false) => {
    const response = await fetch('/api/providers'), data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.error || 'Could not load provider status.');
    const list: Provider[] = Array.isArray(data.providers) ? data.providers : [];
    setProviders(list); setChecked(new Date());
    if (check && health?.mode !== 'demo') {
      await Promise.allSettled(list.filter(p=>(p.runtimeReady||p.id==='openai-compatible')&&['codex','claude','kimi','zai','openai-compatible'].includes(p.id)).map(async provider=>{
        const result=await fetch(`/api/providers/${provider.id}/check`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const update=await result.json().catch(()=>({}));
        setProviders(current=>current.map(p=>p.id===provider.id?{...p,...(result.ok?update:{authentication:'not_checked',usageWindows:[],message:'Connection check failed. Open this provider to retry.'})}:p));
        setChecked(new Date());
      }));
    }
  }, [health?.mode]);
  React.useEffect(() => { loadProviders(true).catch((e: Error) => setError(e.message)); }, [loadProviders]); React.useEffect(() => { if (selected) dialogRef.current?.showModal(); else dialogRef.current?.close(); }, [selected]);
  async function refresh() { setRefreshing(true); setError(''); try { await Promise.all([onRefresh(), loadProviders(true)]); } catch (e: any) { setError(e.message || 'Could not check setup.'); } finally { setRefreshing(false); } }
  async function action(kind: 'connect' | 'check' | 'open' | 'cancel' | 'test-generation') {
    if (!selected || !supported.has(selected.id) || health?.mode === 'demo') return;
    setRefreshing(true); setError('');
    try {
      const payload = selected.id === 'openai-compatible' && kind === 'connect'
        ? {baseUrl:customBaseUrl.trim(),model:customModel.trim(),apiKey:apiKey.trim(),contextHint:Number(customContext),temperature:Number(customTemperature)}
        : selected.id === 'deepseek' && kind === 'connect' ? {apiKey} : {};
      const response=await fetch(`/api/providers/${selected.id}/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(data.error||'Provider action failed.');
      setApiKey('');setSelected({...selected,...data});await loadProviders(false);
    } catch(e:any){setError(e.message||'Provider action failed.');}
    finally {setRefreshing(false);}
  }
  React.useEffect(()=>{if(selected?.authentication!=='signing_in')return;let active=true;const timer=setInterval(async()=>{try{const response=await fetch('/api/providers');const value=await response.json();const row=value.providers?.find((p:Provider)=>p.id===selected.id);if(active&&row)setSelected(current=>current?.id===row.id?row:current)}catch{}},1500);return()=>{active=false;clearInterval(timer)}},[selected?.id,selected?.authentication]);
  const codex = providers.find(provider => provider.id === 'codex');
  const activeProvider = providers.find(provider => provider.id === runtime.provider) || codex;
  return <div className="connections-view"><header><span className="eyebrow">SETTINGS</span><h1>Connections and allowance</h1><p>See the provider status for this device and the usage signals it reports. A connection does not start a model turn.</p></header>
    <section className="connection-engine"><div className="engine-tile"><Cpu size={24} /></div><div><h2>{activeProvider?.label || runtime.provider || 'Codex'}</h2><p>{activeProvider ? status(activeProvider) : runtime.connected ? 'Connected in this chat' : 'Provider status is loading'}</p></div><span className={`setup-badge ${activeProvider?.authentication === 'signed_in' ? 'ok' : ''}`}>{activeProvider ? status(activeProvider) : 'Checking'}</span></section>
    <button className="supervisor-setting" onClick={onModels}><span><b>This chat’s supervisor</b><small>{runtime.model || 'Default supervisor for a new chat'}</small></span><span>Choose model<ChevronRight size={15} /></span></button>
    <RoutingSettings demo={health?.mode === 'demo'} catalogRevision={checked?.getTime()}/>
    <UsagePanel runtime={runtime} account={activeProvider} /><div className="connected-provider-usage">{providers.filter(p=>p.id!==activeProvider?.id && p.authentication==='signed_in').map(p=><AccountUsage key={p.id} account={p}/>)}</div>
    <div className="connections-heading"><h2>Providers</h2><span>Click a provider for its status and actions</span></div><div className="provider-cards">{providers.map(provider => <button className="provider-card" key={provider.id} onClick={() => {setApiKey('');setSelected(provider)}}><span className="provider-monogram">{(provider.label || provider.id).slice(0, 1)}</span><span><b>{provider.label || provider.id}</b><small>{status(provider)}</small></span><span className={`setup-badge ${provider.authentication === 'signed_in' ? 'ok' : ''}`}>{provider.id==='openai-compatible'&&!provider.runtimeReady?'Configure':provider.runtimeReady ? (provider.authentication === 'signed_in' ? 'Connected' : 'Connect') : provider.desktopInstalled ? 'Desktop installed' : provider.cliInstalled ? 'CLI installed' : 'Unavailable'}</span><ChevronRight size={16} /></button>)}</div>
    <RuntimeTools team={runtime.team} connected={runtime.connected}/>
    <div className="connections-heading"><h2>Workspace tools</h2><span>Click for reported activity</span></div><div className="connection-tools">{tools.filter(tool=>caps[tool.id]?.available).map(({ id, name, description, icon: Icon }) => { const activity = toolActivity(events, id); return <article key={id} className={selectedTool === id ? 'is-open' : ''}><button onClick={() => setSelectedTool(selectedTool === id ? null : id)}><span className="tool-tile"><Icon size={20} /></span><span><h3>{name}</h3><p>{description}</p></span><span className={`setup-badge ${caps[id]?.available ? 'ok' : ''}`}>{caps[id]?.available ? <><Check size={12} />Installed</> : 'Unavailable'}</span></button>{selectedTool === id && <div className="tool-activity">{!caps[id]?.available && <p>{caps[id]?.reason || 'Setup check has not finished.'}</p>}<b>Reported activity</b>{activity.length ? activity.map((event, index) => <p key={index}>{event.data?.status || (event.type === 'tool.completed' ? 'Completed' : 'Started')} · {event.data?.tool || event.data?.title}</p>) : <p>Not reported.</p>}</div>}</article>; })}</div>
    <AccessGuide demo={health?.mode === 'demo'}/>

    {error && <p className="connection-error" role="alert"><CircleAlert size={15} />{error}</p>}<footer className="setup-footer"><span>{checked ? `Provider status checked · ${checked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Checking provider status…'}</span><button onClick={refresh} disabled={refreshing}><RefreshCw size={13} className={refreshing ? 'refreshing' : ''} />{refreshing ? 'Checking…' : 'Check again'}</button></footer>
    <dialog className="provider-dialog" ref={dialogRef} onCancel={() => {setSelected(null);setApiKey('')}} onClick={event => { if (event.target === dialogRef.current) setSelected(null); }}>{selected && <><button className="provider-dialog-close" aria-label="Close provider details" onClick={() => {setSelected(null);setApiKey('')}}><X size={18} /></button><span className="eyebrow">PROVIDER CONNECTION</span><h2>{selected.label || selected.id}</h2>{selected.id==='deepseek'&&<div className="deepseek-connect"><p>Connect a DeepSeek API key. Requests use your DeepSeek API balance; a chat website subscription is separate.</p><label>API key<input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} autoComplete="off" spellCheck={false} maxLength={512} placeholder="Paste your DeepSeek API key"/></label><small>The key stays in memory for this app session and is cleared when HQ quits.</small><button className="primary-button" disabled={refreshing||!apiKey.trim()||health?.mode==='demo'} onClick={()=>action('connect')}>{refreshing?'Checking…':'Verify API key'}</button>{selected.balances?.map((balance,i)=><p key={i}>{balance.currency} {balance.total_balance} available · provider reported</p>)}</div>}{selected.id==='openai-compatible'&&<div className="deepseek-connect"><p>Connect any OpenAI-compatible text endpoint. This adapter cannot edit files, use tools, or read images. Model listing checks are free only if your server makes them free; the optional generation test uses its quota.</p><label>Base URL<input type="url" value={customBaseUrl} onChange={e=>setCustomBaseUrl(e.target.value)} spellCheck={false} placeholder="https://host.example/v1 or http://localhost:8099/v1"/></label><label>Model ID<input value={customModel} onChange={e=>setCustomModel(e.target.value)} spellCheck={false} maxLength={200} placeholder="Model ID reported by your server"/></label><label>API key (optional)<input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} autoComplete="off" spellCheck={false} maxLength={4096} placeholder="Only if your endpoint requires a key"/></label><div className="custom-endpoint-numbers"><label>Context hint<input type="number" min="1024" max="262144" value={customContext} onChange={e=>setCustomContext(e.target.value)}/></label><label>Temperature<input type="number" min="0" max="2" step="0.1" value={customTemperature} onChange={e=>setCustomTemperature(e.target.value)}/></label></div><small>The key stays in this app process only. HTTPS is required except for localhost. A model listing proves discovery, not generation.</small><div className="custom-endpoint-actions"><button className="primary-button" disabled={refreshing||!customBaseUrl.trim()||!customModel.trim()||health?.mode==='demo'} onClick={()=>action('connect')}>{refreshing?'Checking…':'Verify endpoint'}</button><button className="small-button" disabled={refreshing||health?.mode==='demo'||!['signed_in','not_checked','model_unavailable'].includes(selected.authentication||'')} onClick={()=>action('test-generation')}>Test one response</button></div></div>}<div className="provider-connection-status" role="status">
      <span className={`setup-badge ${selected.authentication === 'signed_in' && selected.runtimeReady ? 'ok' : ''}`}>{status(selected)}</span>
      <p>{connectionStep(selected)}</p>
    </div>
    {error && <p className="connection-error" role="alert"><CircleAlert size={15} />{error}</p>}
    <div className="provider-connection-actions">
      {nativeProviders.has(selected.id) && selected.runtimeReady && selected.authentication !== 'signed_in' && selected.authentication !== 'signing_in' && <button className="primary-button" onClick={() => action('connect')} disabled={refreshing || health?.mode === 'demo'}>{refreshing ? 'Working…' : `Sign in with ${selected.label || selected.id}`}</button>}
      {nativeProviders.has(selected.id) && !selected.runtimeReady && setupGuides[selected.id] && <a className="primary-button" href={setupGuides[selected.id].url} target="_blank" rel="noreferrer">{setupGuides[selected.id].label} <ExternalLink size={14} /></a>}
      {safeAuthUrl(selected.authUrl) && <a className="primary-button" href={safeAuthUrl(selected.authUrl)} target="_blank" rel="noreferrer">Continue in browser <ExternalLink size={14} /></a>}
      {['codex','claude','kimi','zai','deepseek','openai-compatible'].includes(selected.id) && <button className="small-button" onClick={() => action('check')} disabled={refreshing || health?.mode === 'demo'}>{refreshing ? 'Checking…' : 'Check connection'}</button>}
      {selected.authentication === 'signing_in' && <button className="small-button" onClick={() => action('cancel')} disabled={refreshing || health?.mode === 'demo'}>Cancel sign-in</button>}
      {!nativeProviders.has(selected.id) && selected.helpUrl && <a className="small-button" href={selected.helpUrl} target="_blank" rel="noreferrer">Provider help <ExternalLink size={13} /></a>}
    </div>
    <UsagePanel account={selected} compact />
    <details className="provider-connection-details"><summary>Connection details and activity</summary>
      <dl>{!['deepseek','openai-compatible'].includes(selected.id)&&<div><dt>Desktop app</dt><dd>{selected.desktopInstalled ? 'Installed' : 'Not detected'}</dd></div>}<div><dt>HQ task runtime</dt><dd>{selected.runtimeReady ? 'Ready' : 'Not ready'}</dd></div><div><dt>Account</dt><dd>{status(selected)}</dd></div><div><dt>Models</dt><dd>{selected.models?.length ? selected.models.join(', ') : 'Not reported'}</dd></div></dl>
      {selected.message && <p>{selected.message}</p>}
      <div className="provider-activity"><h3>Recent activity</h3>{selected.activity?.length ? <ul>{selected.activity.slice(-5).reverse().map((item, index) => <li key={`${item.time || index}-${index}`}>{item.message || item.status || 'Provider activity reported'}<small>{item.time ? new Date(item.time).toLocaleString() : ''}</small></li>)}</ul> : <p>Not reported.</p>}</div>
      <div className="provider-extra-actions">{selected.desktopInstalled && selected.id !== 'codex' && <button className="small-button" onClick={() => action('open')} disabled={refreshing || health?.mode === 'demo'}>Open desktop app</button>}{selected.helpUrl && nativeProviders.has(selected.id) && <a className="small-button" href={selected.helpUrl} target="_blank" rel="noreferrer">Provider help <ExternalLink size={13} /></a>}</div>
    </details></>}</dialog>
  </div>;
}
