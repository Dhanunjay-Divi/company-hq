import React from 'react';
import './connections-usage.css';

export type UsageWindow = { id?: string; bucketId?: string; bucketLabel?: string; limitId?:string; limitLabel?:string; usedPercent?: number; windowDurationMins?: number; resetsAt?: number | string };
type Account = { usageWindows?: UsageWindow[] };
export function formatTokens(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString() : 'Not reported'; }
function resetText(value: unknown) { if(value===null||value===undefined||typeof value==='boolean')return 'Reset time not reported'; const milliseconds = typeof value === 'number' && value < 10_000_000_000 ? value * 1000 : Number(value); const date = new Date(milliseconds); return Number.isFinite(milliseconds) && !Number.isNaN(date.getTime()) ? `Resets ${date.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })}` : 'Reset time not reported'; }
function label(window: UsageWindow) { const prefix = window.limitLabel || window.bucketLabel || window.limitId || window.bucketId; const duration = window.windowDurationMins === 300 ? '5-hour account allowance' : window.windowDurationMins === 10080 ? 'Weekly account allowance' : 'Account allowance'; return prefix ? `${prefix} · ${duration}` : duration; }

export function AccountUsage({ account }: { account?: Account }) {
  const windows = (account?.usageWindows || []).filter(window => Number.isFinite(window.usedPercent));
  const fiveHour = windows.filter(window => window.windowDurationMins === 300);
  const weekly = windows.filter(window => window.windowDurationMins === 10080);
  const remaining = windows.filter(window => window.windowDurationMins !== 300 && window.windowDurationMins !== 10080);
  const rows: Array<UsageWindow | { missing: string }> = [fiveHour[0] || { missing: '5-hour account allowance' }, weekly[0] || { missing: 'Weekly account allowance' }, ...fiveHour.slice(1), ...weekly.slice(1), ...remaining];
  return <section className="account-usage" aria-label="Account allowance"><header><div><span className="usage-kicker">ACCOUNT ALLOWANCE</span><h3>Remaining account allowance</h3></div><small>Separate from this chat</small></header><div className="account-window-grid">{rows.map((row, index) => {
    if ('missing' in row) return <article className="account-window account-window-unknown" key={row.missing}><div className="usage-window-top"><span>{row.missing}</span><b>Not reported</b></div><small>Provider did not return this window.</small></article>;
    const used = Number(row.usedPercent), left = Math.max(0, 100 - used);
    return <article className="account-window" key={row.id || `${row.bucketId || 'account'}-${index}`}><div className="usage-window-top"><span>{label(row)}</span><b>{left}% remaining</b></div><div className="usage-meter" aria-label={`${label(row)}: ${left}% remaining`}><i style={{ width: `${Math.min(100, left)}%` }} /></div><small>{used}% used · {resetText(row.resetsAt)}</small></article>;
  })}</div></section>;
}

export default function UsagePanel({ runtime, account, onRefresh, compact = false }: { runtime?: Record<string, any>; account?: Account; onRefresh?: () => void; compact?: boolean }) {
  const usage = runtime?.usageSummary || runtime || {};
  const budget = runtime?.budget;
  const limit = Number(budget?.limitTokens), used = Number(budget?.usedTokens);
  const hasBudget = Number.isFinite(limit) && limit > 0 && Number.isFinite(used);
  const usedPercent = hasBudget ? Math.round(used / limit * 100) : null;
  const children = Array.isArray(runtime?.children) ? runtime.children : [];
  return <section className={`usage-panel ${compact ? 'is-compact' : ''}`} aria-label="Usage details">
    {account !== undefined && <AccountUsage account={account} />}
    {!compact && <><section className="chat-allowance" aria-label="Chat allowance"><header><div><span className="usage-kicker">THIS CHAT</span><h3>Chat allowance</h3></div><small>{hasBudget ? `${usedPercent}% used` : 'Not reported'}</small></header>{hasBudget ? <><div className="usage-window-top"><span>{usedPercent}% used</span><b>{Math.max(0, 100 - usedPercent)}% remaining</b></div><div className="usage-meter"><i style={{ width: `${Math.max(0, Math.min(100, 100 - usedPercent))}%` }} /></div><p>{formatTokens(used)} of {formatTokens(limit)} reported tokens {budget.enforced ? '· action gate on' : '· tracking only'}</p></> : <p>{limit === 0 ? 'No local ceiling. Account limits still apply.' : 'This chat has not reported a local allowance yet.'}</p>}</section>
      <details className="raw-token-details"><summary>Raw runtime token counts</summary><dl><div><dt>Input</dt><dd>{formatTokens(usage.inputTokens)}</dd></div><div><dt>Cached input</dt><dd>{formatTokens(usage.cachedInputTokens)}</dd></div><div><dt>Output</dt><dd>{formatTokens(usage.outputTokens)}</dd></div><div><dt>Total</dt><dd>{formatTokens(usage.totalTokens)}</dd></div></dl><p>{typeof usage.eventCount === 'number' ? `${usage.eventCount} native report${usage.eventCount === 1 ? '' : 's'}` : 'No native runtime usage report.'}</p></details>
      <section className="agent-usage"><h3>Individual agent share</h3>{children.length ? <p>Not reported. Runtime child records do not include independent usage totals.</p> : <p>Not reported.</p>}</section>{onRefresh && <button className="small-button usage-refresh" onClick={onRefresh}>Refresh usage</button>}</>}
  </section>;
}
