import React from 'react';

interface Worker { threadId: string; state?: string; source?: string; model?: string }
interface Runtime {
  state?: string; mode?: string; planReady?: boolean; connected?: boolean;
  threadId?: string; model?: string; children?: Worker[];
  usageSummary?: { inputTokens?: number; cachedInputTokens?: number; outputTokens?: number; coverage?: string };
  limits?: { remainingTurns?: number; maxTurns?: number; blockedReason?: string };
}
interface Event { seq: number; type: string; data?: { text?: string; status?: string } }
interface Props {
  runtime: Runtime; events: Event[]; demo: boolean; connectedProject: boolean;
  registeredCount: number; completedCount: number; taskCount: number;
  onConsole: () => void; onSystem: () => void; onDraft: (text: string) => void;
}
const names: Record<string, string> = {
  offline: 'Not connected', starting: 'Connecting', running: 'Working', idle: 'Ready',
  awaiting_approval: 'Needs your permission', stopping: 'Stopping', error: 'Needs attention',
};
function formatNumber(value: unknown) {
  return typeof value === 'number' ? value.toLocaleString() : 'Unknown';
}

/** A view of backend evidence, not another scheduler or a fabricated agent roster. */
export default function RunOverview(p: Props) {
  const r = p.runtime;
  const usage = r.usageSummary || {};
  const completed = [...p.events].reverse().find(e => e.type === 'turn.completed');
  const result = [...p.events].reverse().find(e => e.type === 'message.completed');
  const executionFinished = r.mode === 'execute' && r.state === 'idle' && completed?.data?.status === 'completed';
  const phase = !p.connectedProject ? 0 : !r.threadId ? 1 : r.mode !== 'execute' ? (r.planReady ? 2 : 1) : executionFinished ? 4 : 3;
  const steps = ['Connect', 'Plan', 'Approve', 'Execute', 'Review'];
  const action = p.demo ? 'Explore this synthetic workspace. No model calls are enabled.'
    : !p.connectedProject ? 'Connect a project folder to begin.'
    : !r.threadId ? 'Describe your outcome below. The first turn is read-only.'
    : r.state === 'error' ? 'Open the supervisor console to inspect the error before retrying.'
    : r.state === 'awaiting_approval' ? 'Review the specific permission request. You can decline it.'
    : r.mode !== 'execute' ? (r.planReady ? 'Read the plan, then use the separate execution approval.' : 'Discuss scope and constraints with the supervisor. Project writes remain disabled.')
    : executionFinished ? 'Inspect the result and test evidence. A finished turn is not proof that every task passed.'
    : 'Follow the work here. Send direction or stop from the composer below.';
  const workers = (r.children ?? []).filter(w => typeof w.threadId === 'string');
  return <div className="run-overview" data-testid="run-overview">
    <header className="view-heading"><div><span className="eyebrow">ONE CONVERSATION. VISIBLE WORK.</span>
      <h2>Your project, step by step</h2><p>Plan first. Approve deliberately. Review the evidence.</p></div>
      <button className="small-button" onClick={p.onSystem}>Connections & capabilities</button></header>
    {p.demo && <p className="fixture-notice" role="note">Synthetic demo — this screen does not demonstrate a live provider connection.</p>}
    <ol className="run-steps" aria-label="Project workflow">{steps.map((step, i) =>
      <li key={step} aria-current={i === phase ? 'step' : undefined}><span>{i + 1}</span>{step}</li>)}</ol>
    <section className="next-action" aria-label="Your next action"><h3>Your next action</h3><p>{action}</p>
      <button className="primary-button" onClick={p.onConsole}>Open supervisor conversation</button></section>
    <div className="run-metrics">
      <article><span>Supervisor</span><strong>{names[r.state ?? 'offline'] ?? 'Unknown'}</strong><small>{r.model || 'No model selected yet'}</small></article>
      <article><span>Execution access</span><strong>{p.demo ? 'Disabled' : r.mode === 'execute' ? 'Approved workspace' : 'Read-only planning'}</strong><small>Provider permissions still apply</small></article>
      <article><span>Recorded tasks</span><strong>{p.completedCount} / {p.taskCount}</strong><small>Task status is separate from test evidence</small></article>
    </div>
    <section className="usage-section" aria-label="Usage and budget signal"><div><h3>Usage and budget signal</h3>
      <p>{usage.eventCount ? usage.coverage : 'No native runtime usage report has arrived yet. Account quota and billed cost are checked outside this local project dashboard.'}</p></div>
      <div className="usage-grid">
        <article><span>Input</span><strong>{formatNumber(usage.inputTokens)}</strong><small>runtime tokens</small></article>
        <article><span>Cached</span><strong>{formatNumber(usage.cachedInputTokens)}</strong><small>reported cache</small></article>
        <article><span>Output</span><strong>{formatNumber(usage.outputTokens)}</strong><small>runtime tokens</small></article>
        <article><span>Total</span><strong>{formatNumber(usage.totalTokens)}</strong><small>{usage.eventCount ? `${usage.eventCount} report${usage.eventCount === 1 ? '' : 's'}` : 'no report'}</small></article>
      </div>
    </section>
    <section className="worker-section"><h3>Observed runtime workers</h3>
      <p>{p.registeredCount} registered team record{p.registeredCount === 1 ? '' : 's'}. Only provider-reported worker IDs appear below.</p>
      {!workers.length ? <p className="quiet-state">No child worker has been reported. Simple work does not need a whole team.</p>
        : <ul className="worker-list">{workers.map(w => <li key={w.threadId}><code>{w.threadId}</code>
          <span>{r.connected ? w.state || 'Unknown state' : 'Last observed; reconnect to verify'}</span>
          <small>{w.model || 'Model not reported'} · {w.source || 'Runtime event'}</small></li>)}</ul>}
    </section>
    <section className="result-section"><h3>Latest supervisor result</h3>
      {result?.data?.text ? <pre>{result.data.text}</pre> : <p className="quiet-state">The supervisor's latest completed reply will appear here. No result is invented from task status.</p>}
    </section>
    {!r.threadId && !p.demo && <section className="goal-examples"><h3>Start with a bounded goal</h3>
      <button className="small-button" onClick={() => p.onDraft('Inspect this project and propose the smallest safe plan to add customer invitations. Do not edit files yet. Reuse existing code and include tests and rollback.')}>Plan a small feature</button>
      <button className="small-button" onClick={() => p.onDraft('Investigate the reported bug, find the root cause, and propose a bounded fix with a regression test. Do not edit files yet.')}>Investigate a bug</button>
    </section>}
  </div>;
}
