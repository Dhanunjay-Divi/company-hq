import React from 'react';
import './connections-usage.css';

export type UsageWindow = { id?: string; bucketId?: string; bucketLabel?: string; limitId?:string; limitLabel?:string; usedPercent?: number; windowDurationMins?: number; resetsAt?: number | string };
type Account = { id?: string; label?: string; authentication?: string; usageWindows?: UsageWindow[] };
export function formatTokens(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString() : 'Not reported'; }
function resetText(value: unknown) { if(value===null||value===undefined||typeof value==='boolean')return 'Reset time not reported'; const milliseconds = typeof value === 'number' && value < 10_000_000_000 ? value * 1000 : typeof value === 'string' && !/^\d+(\.\d+)?$/.test(value) ? Date.parse(value) : Number(value) < 10_000_000_000 ? Number(value) * 1000 : Number(value); const date = new Date(milliseconds); return Number.isFinite(milliseconds) && !Number.isNaN(date.getTime()) ? `Resets ${date.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })}` : 'Reset time not reported'; }
function label(window: UsageWindow) { const prefix = window.limitLabel || window.bucketLabel || window.limitId || window.bucketId; const duration = window.windowDurationMins === 300 ? '5-hour account allowance' : window.windowDurationMins === 10080 ? 'Weekly account allowance' : 'Account allowance'; return prefix ? `${prefix} · ${duration}` : duration; }

export function AccountUsage({ account }: { account?: Account }) {
  const windows = (account?.usageWindows || []).filter(window => Number.isFinite(window.usedPercent));
  const rows = windows;
  if (!rows.length) return null;
  return <section className="account-usage" aria-label="Account allowance"><header><div><span className="usage-kicker">ACCOUNT ALLOWANCE</span><h3>{account?.label || account?.id || 'Provider'} account allowance</h3></div><small>Separate from this chat</small></header><div className="account-window-grid">{rows.map((row, index) => {
    const reportedUsed = Number(row.usedPercent), used = Math.max(0, Math.min(100, reportedUsed)), left = Math.round((100 - used) * 10) / 10;
    return <article className="account-window" key={row.id || `${row.bucketId || 'account'}-${index}`}><div className="usage-window-top"><span>{label(row)}</span><b>{left}% remaining</b></div><div className="usage-meter" aria-label={`${label(row)}: ${left}% remaining`}><i style={{ width: `${Math.min(100, left)}%` }} /></div><small>{reportedUsed}% used · {resetText(row.resetsAt)}</small></article>;
  })}</div>{!rows.length && <p className="allowance-explanation">{account?.authentication === 'signed_in' ? 'Signed in. This provider has not exposed an account allowance through its connected runtime. Session tokens, when reported, appear below.' : 'Check this provider’s connection to load the allowance it reports.'}</p>}{rows.length > 0 && <p className="allowance-explanation">Shared across this account’s models. Only provider-reported windows are shown.</p>}</section>;
}

export default function UsagePanel({ runtime, account, onRefresh, compact = false }: { runtime?: Record<string, any>; account?: Account; onRefresh?: () => void; compact?: boolean }) {
  const usage = runtime?.usageSummary || runtime || {};
  const budget = runtime?.budget;
  const limit = Number(budget?.limitTokens), used = Number(budget?.usedTokens);
  const hasBudget = Number.isFinite(limit) && limit > 0 && Number.isFinite(used);
  const usedPercent = hasBudget ? Math.round(used / limit * 100) : null;
  const hasUsage = ['inputTokens','cachedInputTokens','outputTokens','totalTokens','reportedTokens'].some(key => typeof usage[key] === 'number' && Number.isFinite(usage[key]));
  if (!hasBudget && !hasUsage && !(account?.usageWindows || []).some(w=>Number.isFinite(w.usedPercent))) return null;
  return <section className={`usage-panel ${compact ? 'is-compact' : ''}`} aria-label="Usage details">
    {account !== undefined && <AccountUsage account={account} />}
    {!compact && <>{hasBudget && <section className="chat-allowance" aria-label="Chat allowance"><header><div><span className="usage-kicker">THIS CHAT</span><h3>Chat allowance</h3></div><small>{hasBudget ? `${usedPercent}% used` : limit === 0 ? 'No local limit' : 'Not set'}</small></header>{hasBudget ? <><div className="usage-window-top"><span>{usedPercent}% used</span><b>{Math.max(0, 100 - usedPercent)}% remaining</b></div><div className="usage-meter"><i style={{ width: `${Math.max(0, Math.min(100, 100 - usedPercent))}%` }} /></div><p>{formatTokens(used)} of {formatTokens(limit)} reported tokens {budget.enforced ? '· action gate on' : '· tracking only'}</p></> : <p>{limit === 0 ? 'No local ceiling. Account limits still apply.' : 'This chat has not reported a local allowance yet.'}</p>}</section>}
      {hasUsage && <details className="raw-token-details"><summary>Raw runtime token counts</summary><dl>{typeof usage.inputTokens === 'number' && <div><dt>Input</dt><dd>{formatTokens(usage.inputTokens)}</dd></div>}{typeof usage.cachedInputTokens === 'number' && <div><dt>Cached input</dt><dd>{formatTokens(usage.cachedInputTokens)}</dd></div>}{typeof usage.outputTokens === 'number' && <div><dt>Output</dt><dd>{formatTokens(usage.outputTokens)}</dd></div>}<div><dt>Total</dt><dd>{formatTokens(usage.totalTokens ?? usage.reportedTokens)}</dd></div></dl><p>{typeof usage.eventCount === 'number' ? `${usage.eventCount} native report${usage.eventCount === 1 ? '' : 's'}` : typeof (usage.totalTokens ?? usage.reportedTokens) === 'number' ? 'Provider-reported session tokens · includes reused context.' : 'No native runtime usage report yet.'}</p></details>}
      {onRefresh && <button className="small-button usage-refresh" onClick={onRefresh}>Refresh usage</button>}</>}
  </section>;
}
