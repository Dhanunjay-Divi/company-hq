import React from 'react';
import { CheckCircle2, ChevronDown, CircleAlert, LoaderCircle, Save, ShieldCheck } from 'lucide-react';
import './routing-settings.css';

type Model = { provider: string; model: string; enabled: boolean; sharePercent: number };
type Settings = { autoFallback: boolean; models: Model[]; preferredSupervisor?: { provider: string; model: string }; tokenPool?: { limitTokens: number }; reportedUsage?: Record<string, number> };
type UsageWindow = { id?: string; bucketId?: string; bucketLabel?: string; limitId?: string; limitLabel?: string; usedPercent?: number; windowDurationMins?: number; resetsAt?: number | string };
type CatalogModel = { provider: string; model: string; accountId?: string; label?: string; verified?: boolean; authenticated?: boolean; available?: boolean; usageWindows?: UsageWindow[] };
type ApiResponse = { settings?: Settings; catalog?: CatalogModel[]; selection?: unknown; error?: string };

export default function RoutingSettings({ disabled = false, demo = false, catalogRevision }: { disabled?: boolean; demo?: boolean; catalogRevision?: number }) {
  const [settings, setSettings] = React.useState<Settings>({ autoFallback: true, models: [] });
  const [catalog, setCatalog] = React.useState<CatalogModel[]>([]);
  const [loading, setLoading] = React.useState(true), [saving, setSaving] = React.useState(false), [error, setError] = React.useState(''), [success, setSuccess] = React.useState('');
  const readOnly = disabled || demo;
  const load = React.useCallback(async () => {
    setLoading(true); setError('');
    try {
      const response = await fetch('/api/routing'); const body: ApiResponse = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(body.error || 'Could not load routing settings.');
      const next = body.settings || { autoFallback: true, models: [] };
      setSettings({ autoFallback: next.autoFallback !== false, models: Array.isArray(next.models) ? next.models : [], preferredSupervisor: next.preferredSupervisor, tokenPool: next.tokenPool, reportedUsage: next.reportedUsage || {} });
      setCatalog(Array.isArray(body.catalog) ? body.catalog : []);
    } catch (cause: any) { setError(cause?.message || 'Could not load routing settings.'); }
    finally { setLoading(false); }
  }, []);
  React.useEffect(() => { load(); }, [load]);
  React.useEffect(()=>{if(!catalogRevision)return;let active=true;fetch('/api/routing').then(r=>r.ok?r.json():null).then(body=>{if(active&&body){setCatalog(body.catalog||[]);setSettings(current=>({...current,reportedUsage:body.settings?.reportedUsage||current.reportedUsage}));}}).catch(()=>{});return()=>{active=false}},[catalogRevision]);

  const rows = React.useMemo(() => {
    const configured = new Map(settings.models.map(model => [key(model.provider, model.model), model]));
    const connected = catalog.filter(item => item.verified === true && item.authenticated === true);
    const merged = new Map<string, CatalogModel>();
    for (const item of connected) merged.set(key(item.provider, item.model), item);
    for (const model of settings.models) if (!merged.has(key(model.provider, model.model))) merged.set(key(model.provider, model.model), { ...model, available: false });
    return [...merged.values()].map(item => ({ item, config: configured.get(key(item.provider, item.model)) }));
  }, [catalog, settings.models]);
  const supervisorOptions = rows.filter(row => row.config || (row.item.verified && row.item.authenticated && row.item.available));
  const selectedRows = rows.filter(row => row.config);
  const unselectedRows = rows.filter(row => !row.config);
  const selectedGroups = groupSelectedModels(selectedRows);
  const preferredKey = settings.preferredSupervisor ? key(settings.preferredSupervisor.provider, settings.preferredSupervisor.model) : '';
  const pool = validPool(settings.tokenPool?.limitTokens) ? settings.tokenPool!.limitTokens : 0;

  const reportedTotal=Object.values(settings.reportedUsage||{}).filter(v=>Number.isFinite(v)&&v>=0).reduce((sum,v)=>sum+v,0);
  const poolUsed=pool>0?Math.round(reportedTotal/pool*100):null;
  function updateModels(change: (models: Model[]) => Model[]) { setSettings(current => ({ ...current, models: change(current.models) })); setSuccess(''); }
  function setSupervisor(value: string) {
    const selected = rows.find(row => key(row.item.provider, row.item.model) === value)?.item; if (!selected) return;
    updateModels(models => models.some(model => key(model.provider, model.model) === value) ? models.map(model => key(model.provider, model.model) === value ? { ...model, enabled: true, sharePercent: 100 } : model) : [...models, { provider: selected.provider, model: selected.model, enabled: true, sharePercent: 100 }]);
    setSettings(current => ({ ...current, preferredSupervisor: { provider: selected.provider, model: selected.model } }));
  }
  function toggle(item: CatalogModel, enrolled: boolean) {
    const modelKey = key(item.provider, item.model);
    updateModels(models => enrolled ? models.filter(model => key(model.provider, model.model) !== modelKey) : [...models, { provider: item.provider, model: item.model, enabled: true, sharePercent: 100 }]);
  }
  async function save() {
    if (readOnly || saving) return;
    setSaving(true); setError(''); setSuccess('');
    const outgoing: Settings = { autoFallback: settings.autoFallback, models: settings.models, ...(settings.preferredSupervisor ? { preferredSupervisor: settings.preferredSupervisor } : {}), ...(pool > 0 ? { tokenPool: { limitTokens: pool } } : {}) };
    try {
      const response = await fetch('/api/routing', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(outgoing) });
      const body: ApiResponse = await response.json().catch(() => ({})); if (!response.ok) throw Error(body.error || 'Could not save routing settings.');
      if (body.settings) setSettings({ ...body.settings, reportedUsage: body.settings.reportedUsage || settings.reportedUsage || {} });
      setSuccess('Routing settings saved.');
    } catch (cause: any) { setError(cause?.message || 'Could not save routing settings.'); }
    finally { setSaving(false); }
  }

  return <section className="routing-settings" aria-labelledby="routing-settings-title" aria-busy={loading}>
    <header className="routing-settings-header"><div><span className="routing-kicker">LOCAL ROUTING POLICY</span><h2 id="routing-settings-title">Supervisor &amp; routing</h2><p>Choose a stable supervisor and optional, approved continuation after a provider quota limit.</p></div><button type="button" className="routing-save" onClick={save} disabled={readOnly || loading || saving}>{saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}{saving ? 'Saving…' : 'Save'}</button></header>
    {demo && <p className="routing-notice"><CircleAlert size={15} aria-hidden="true" />Routing controls are unavailable in demo mode.</p>}
    {loading ? <p className="routing-loading"><LoaderCircle className="spin" size={15} />Loading routing settings…</p> : <>
      <div className="routing-grid"><label className="routing-field">Default supervisor<select value={preferredKey} disabled={readOnly} onChange={event => setSupervisor(event.target.value)}><option value="">Choose an enrolled model</option>{supervisorOptions.map(({ item }) => <option key={key(item.provider, item.model)} value={key(item.provider, item.model)}>{providerName(item.provider)} · {modelName(item)}</option>)}</select><small>Set explicitly. It stays stable; sign-in order and model names do not rank providers.</small></label></div>
      <label className="routing-toggle"><input type="checkbox" checked={settings.autoFallback} disabled={readOnly} onChange={event => { setSettings(current => ({ ...current, autoFallback: event.target.checked })); setSuccess(''); }} /><span><b>Continue on another enrolled model after a quota limit</b><small>Only after a stopped checkpoint. Active tools and workers must stop before another model continues the same task.</small></span></label>
      <section className="routing-selected"><header><div><span>SELECTED CONTINUATION MODELS</span><h3>Fallback uses these models</h3></div><small>Provider allowances are shared by account, not assigned to individual models.</small></header><p>Smaller workers take bounded tasks and report results for review and tests. Company HQ does not choose a cheaper model or infer quality automatically.</p><div className="routing-provider-groups">{selectedRows.length ? selectedGroups.map(group => <section className="routing-provider-group" key={group.id}><div className="routing-models">{group.rows.map(({ item, config }) => <ModelRow key={key(item.provider, item.model)} item={item} config={config} pool={pool} reported={settings.reportedUsage?.[key(item.provider, item.model)]} disabled={readOnly} required={preferredKey===key(item.provider,item.model)} onToggle={toggle} onChange={(changes) => updateModels(models => models.map(model => key(model.provider, model.model) === key(item.provider, item.model) ? { ...model, ...changes } : model))} />)}</div><AccountAllowance provider={group.provider} windows={group.windows} /></section>) : <p className="routing-empty">Choose a supervisor and any continuation models you approve.</p>}</div></section>
      <details className="routing-manage"><summary>Manage models <ChevronDown size={16} aria-hidden="true" /></summary><p>Add verified models to the continuation list. Other connected models remain available for deliberate manual worker selection.</p><div className="routing-models">{unselectedRows.map(({ item, config }) => <ModelRow key={key(item.provider, item.model)} item={item} config={config} pool={pool} reported={settings.reportedUsage?.[key(item.provider, item.model)]} disabled={readOnly} onToggle={toggle} onChange={()=>{}} />)}</div></details>
      <details className="routing-budgets"><summary>Advanced limits <ChevronDown size={16} aria-hidden="true" /></summary><p>Optional local reported-token limits. Unlimited is the default. These controls do not represent provider account allowances.</p><label className="routing-field routing-pool">Local reported token pool<input type="number" min="0" step="1" inputMode="numeric" value={pool || ''} disabled={readOnly} placeholder="Unlimited" onChange={event => { const value = Math.max(0, Math.floor(Number(event.target.value) || 0)); setSettings(current => ({ ...current, tokenPool: value ? { limitTokens: value } : undefined })); setSuccess(''); }} /><small>0 means unlimited. It uses only native reported tokens.</small></label>{poolUsed!==null&&<div className="routing-pool-meter"><span>Overall local pool <b>{Math.max(0,100-poolUsed)}% remaining</b></span><progress max={100} value={Math.min(100,poolUsed)} aria-label="Local token pool used"/><small>{poolUsed}% reported used · {reportedTotal.toLocaleString()} / {pool.toLocaleString()} tokens.</small></div>}<div className="routing-models advanced-models">{selectedRows.map(({ item, config }) => <ModelRow key={key(item.provider, item.model)} item={item} config={config} pool={pool} reported={settings.reportedUsage?.[key(item.provider, item.model)]} disabled={readOnly} required={preferredKey===key(item.provider,item.model)} advanced onToggle={toggle} onChange={(changes) => updateModels(models => models.map(model => key(model.provider, model.model) === key(item.provider, item.model) ? { ...model, ...changes } : model))} />)}</div></details>
      {error && <p className="routing-message routing-error" role="alert"><CircleAlert size={15} aria-hidden="true" />{error}</p>}{success && <p className="routing-message routing-success" role="status"><CheckCircle2 size={15} aria-hidden="true" />{success}</p>}
    </>}
  </section>;
}

function ModelRow({ item, config, pool, reported, disabled, required = false, advanced = false, onToggle, onChange }: { item: CatalogModel; config?: Model; pool: number; reported?: number; disabled: boolean; required?: boolean; advanced?: boolean; onToggle: (item: CatalogModel, enrolled: boolean) => void; onChange: (changes: Partial<Model>) => void }) {
  const enrolled = Boolean(config); const online = item.verified && item.authenticated && item.available;
  const reportedPercent = pool > 0 && typeof reported === 'number' && Number.isFinite(reported) ? Math.round(reported / pool * 100) : null;
  return <article className={`routing-model ${online ? '' : 'is-unavailable'}`}><div className="routing-model-top"><label className="routing-enroll"><input type="checkbox" checked={enrolled} disabled={disabled || required || (!online && !enrolled)} onChange={() => onToggle(item, enrolled)} /><span><b>{providerName(item.provider)}</b><strong>{modelName(item)}{required && <em>Supervisor</em>}</strong></span></label><span className={`routing-status ${online ? 'ready' : 'unavailable'}`}>{online ? <><ShieldCheck size={13} aria-hidden="true" />Signed in</> : 'Unavailable'}</span></div>{advanced && enrolled && <div className="routing-ceiling"><label><span>{config!.sharePercent}% ceiling</span><input type="range" min="0" max="100" step="1" value={config!.sharePercent} disabled={disabled} onChange={event => onChange({ sharePercent: Number(event.target.value) })} /></label><label className="routing-enabled"><input type="checkbox" checked={config!.enabled} disabled={disabled} onChange={event => onChange({ enabled: event.target.checked })} />Enabled</label>{reportedPercent !== null && <small>{reportedPercent}% of local pool reported</small>}</div>}</article>;
}

function groupSelectedModels(rows: { item: CatalogModel; config?: Model }[]) {
  const groups = new Map<string, { id: string; provider: string; rows: { item: CatalogModel; config?: Model }[]; windows: UsageWindow[] }>();
  for (const row of rows) {
    const id = `${row.item.provider}\x1f${row.item.accountId || 'native-account'}`;
    const group = groups.get(id) || { id, provider: row.item.provider, rows: [], windows: Array.isArray(row.item.usageWindows) ? row.item.usageWindows : [] };
    group.rows.push(row); groups.set(id, group);
  }
  return [...groups.values()];
}

function AccountAllowance({ provider, windows }: { provider: string; windows: UsageWindow[] }) {
  const reported = windows.filter(window => typeof window.usedPercent === 'number' && Number.isFinite(window.usedPercent));
  if (!reported.length) return null;
  return <section className="routing-account-allowance" aria-label={`${providerName(provider)} shared account allowances`}><header><span>{providerName(provider)} account allowance</span><small>Shared by the selected models above</small></header>{reported.map((window, index) => {
    const used = Math.round(window.usedPercent!); const remaining = Math.max(0, 100 - used); const label = allowanceLabel(window);
    return <div className="routing-allowance-window" key={window.id || window.bucketId || `${label}-${index}`}><div><span>{label}</span><b>{remaining}% remaining</b></div><progress max={100} value={Math.max(0, Math.min(100, used))} aria-label={`${label}: ${remaining}% remaining`} /><small>{used}% used{resetText(window.resetsAt)}</small></div>;
  })}</section>;
}

function key(provider: string, model: string) { return `${provider}\x1f${model}`; }
function modelName(item: CatalogModel) { const name=item.model.split('/').pop() || item.model; return name.startsWith('gpt-')?name.replace('gpt-','GPT ').split('-').map((part,i)=>i?part.charAt(0).toUpperCase()+part.slice(1):part).join(' '):name; }
function providerName(provider: string) { return provider ? provider.slice(0, 1).toUpperCase() + provider.slice(1) : 'Provider'; }
function allowanceLabel(window: UsageWindow) { const name = window.limitLabel || window.bucketLabel || window.limitId || window.bucketId; const duration = window.windowDurationMins === 300 ? '5-hour allowance' : window.windowDurationMins === 10080 ? 'Weekly allowance' : 'Account allowance'; return name ? `${name} · ${duration}` : duration; }
function resetText(value: UsageWindow['resetsAt']) { const timestamp = typeof value === 'number' ? value * 1000 : typeof value === 'string' ? Date.parse(value) : Number.NaN; return Number.isFinite(timestamp) ? ` · resets ${new Date(timestamp).toLocaleString()}` : ''; }
function validPool(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) && value > 0; }
