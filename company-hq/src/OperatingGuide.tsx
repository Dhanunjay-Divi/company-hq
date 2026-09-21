import React from 'react';
import { BookOpenCheck, Code2, Gauge, GitBranch, Network, ShieldCheck, Wrench } from 'lucide-react';

type RecordData = Record<string, any>;

interface Props {
  demo: boolean;
  health: RecordData;
  runtime: RecordData;
}

const steps = [
  ['1', 'Bring the idea', 'Describe the customer, outcome, constraints, and what “done” must prove. A vague idea is okay; the supervisor turns it into questions and a plan.'],
  ['2', 'Connect a local project', 'Company HQ attaches to a folder and creates team/task state outside that repo. Connecting alone does not edit files or start workers.'],
  ['3', 'Plan before writes', 'The first native supervisor turn is read-only. It should inspect, choose the smallest useful team, estimate risk, and define verification.'],
  ['4', 'Approve execution', 'Only after the plan completes can you approve workspace-write execution. Permission prompts still show the exact action before it runs.'],
  ['5', 'Review evidence', 'Use the IDE, tests, run events, task board, and usage signal together. A task status is not proof; passing checks and reviewed diffs are proof.'],
];

const modelPolicy = [
  ['Simple or narrow', 'one supervisor, usually a smaller capable model'],
  ['Independent streams', 'department lead plus bounded workers, only when parallel work helps'],
  ['High-risk architecture/review', 'escalate the supervisor or reviewer tier for that decision'],
  ['Unclear capability', 'benchmark or run a model-free fixture before promoting a tool'],
];

export default function OperatingGuide({ demo, health, runtime }: Props) {
  const codexReady = Boolean(health?.capabilities?.codex?.available);
  return <div className="operating-guide">
    <header className="guide-hero">
      <div>
        <span className="eyebrow">HOW TO WORK WITH COMPANY HQ</span>
        <h2>Use it like a small operating company beside your IDE</h2>
        <p>Company HQ is the control room. Your IDE is still where you inspect files, review diffs, run manual checks and understand the code. The dashboard coordinates the plan, workers, approvals, memory, usage signals and evidence.</p>
      </div>
      <aside>
        <span><ShieldCheck size={16}/>{demo ? 'Model-free demo mode' : codexReady ? 'Native Codex runtime ready' : 'Execution runtime unavailable'}</span>
        <span><Gauge size={16}/>{runtime?.usageSummary?.eventCount ? 'Runtime usage is reporting' : 'Usage appears after a native runtime report'}</span>
      </aside>
    </header>

    <section className="guide-steps" aria-label="Company HQ workflow">
      {steps.map(([number, title, body]) => <article key={number}>
        <span>{number}</span><div><h3>{title}</h3><p>{body}</p></div>
      </article>)}
    </section>

    <section className="guide-grid">
      <article><Code2 size={22}/><h3>How it fits with the IDE</h3><p>Keep coding tools open normally. Give Company HQ the repo folder, then let the supervisor produce a plan, spawn real Codex workers when useful, and surface approval requests. Use your IDE to inspect exact diffs, unresolved files, build output, and local behavior before shipping.</p></article>
      <article><Network size={22}/><h3>When a team is useful</h3><p>Simple changes should stay with one agent. A real team appears when work can split cleanly, such as product research, UI, backend, QA, launch copy, and review. Registered roles are planning records; only native runtime child IDs prove live workers.</p></article>
      <article><Gauge size={22}/><h3>Usage discipline</h3><p>The run screen shows provider-reported token counts when the native runtime emits them, plus a per-workspace action gate. Account-wide quota, credits and billed money are separate. Use smaller models first, reuse code intelligence before broad reads, compress noisy command output only when evidence is preserved, and stop or raise the ceiling only after reviewing why the budget was reached.</p></article>
      <article><GitBranch size={22}/><h3>How repos are reused</h3><p>The stack screen separates integrated, default-off, benchmarked, doc-reviewed and inventoried candidates. Useful code is adopted behind Company HQ contracts only after license, state, security, and acceptance checks. Bulk-installing every framework would create duplicate schedulers and hidden cost.</p></article>
      <article><Wrench size={22}/><h3>Python now, Rust where it wins</h3><p>Python is the current control plane because it integrates quickly with Codex, ClawTeam, browser tests and evidence scripts. Rust is a good target for a packaged process supervisor, file watcher, command runner, sandbox helper, or high-volume indexer once benchmarks show the Python path is the bottleneck.</p></article>
      <article><BookOpenCheck size={22}/><h3>What to type first</h3><p>“We are building X for Y. The customer problem is Z. Please inspect read-only, ask only material questions, propose the smallest team, acceptance checks, risks, budget limits, and first implementation slice. Do not edit files yet.”</p></article>
    </section>

    <section className="guide-policy">
      <div><span className="eyebrow">MODEL AND TEAM POLICY</span><h2>Frugal by default, stronger only when justified</h2><p>The supervisor chooses from available, reviewed runtimes at the time of work. Top models are reserved for coordination, architecture, hard debugging, security review, or final synthesis.</p></div>
      <div>{modelPolicy.map(([need, route]) => <article key={need}><b>{need}</b><span>{route}</span></article>)}</div>
    </section>
  </div>;
}
