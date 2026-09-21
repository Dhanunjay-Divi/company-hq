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
  ['2', 'Add a project when useful', 'You can chat without a folder. Add project starts a project conversation when you need to work on existing files.'],
  ['3', 'Choose how to work', 'Work automatically lets the supervisor plan, build and test in the workspace. Plan first keeps the first turn read-only. Full access explicitly permits broader machine and network access.'],
  ['4', 'Follow the work', 'The supervisor creates useful teams and reports progress. Plan first asks before implementation; automatic workspace work can still request specific native permissions. Full access uses the native runtime’s broader access policy.'],
  ['5', 'Review evidence', 'Use the IDE, tests, run events, task board, and usage signal together. A task status is not proof; passing checks and reviewed diffs are proof.'],
];

const modelPolicy = [
  ['Overall supervisor', 'Astra by default: plans, assigns useful work, and reviews results'],
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

    <section className="role-guide" aria-label="Team roles"><article><span>01 / DIRECTION</span><h3>Supervisor</h3><p>Owns your goal, decides which teams are useful, and reviews the final result.</p><small>Talk to this role first.</small></article><article><span>02 / COORDINATION</span><h3>Team lead</h3><p>Owns one area, breaks it into assignments, and checks the specialists’ work.</p><small>Created when coordination helps.</small></article><article><span>03 / DELIVERY</span><h3>Worker</h3><p>Completes a specific assignment, tests it, and reports evidence to the lead.</p><small>A focused task and suitable model.</small></article></section>
    <p className="role-disclaimer">A bounded supervisor → lead → worker test passed with Astra, Terra, and Luna. Full nested messaging and graph synchronization are still being completed. A role description is not an active agent.</p>
    <section className="guide-steps" aria-label="Company HQ workflow">
      {steps.map(([number, title, body]) => <article key={number}>
        <span>{number}</span><div><h3>{title}</h3><p>{body}</p></div>
      </article>)}
    </section>

    <section className="guide-grid">
      <article><Code2 size={22}/><h3>How it fits with the IDE</h3><p>Keep coding tools open normally. Give Company HQ the repo folder, then let the supervisor produce a plan, spawn real Codex workers when useful, and surface approval requests. Use your IDE to inspect exact diffs, unresolved files, build output, and local behavior before shipping.</p></article>
      <article><Network size={22}/><h3>When a team is useful</h3><p>Simple changes should stay with one agent. A real team appears when work can split cleanly, such as product research, UI, backend, QA, launch copy, and review. Registered roles are planning records; only native runtime child IDs prove live workers.</p></article>
      <article><Gauge size={22}/><h3>Usage discipline</h3><p>Activity shows this chat’s allowance percentage. Settings shows remaining 5-hour and weekly account percentages when reported; missing windows stay unknown. Raw tokens, account quota and billed money stay separate. Use smaller models first, reuse code intelligence before broad reads, compress noisy command output only when evidence is preserved, and stop or raise the ceiling only after reviewing why the budget was reached.</p></article>
      <article><GitBranch size={22}/><h3>How repos are reused</h3><p>The stack screen separates integrated, default-off, benchmarked, doc-reviewed and inventoried candidates. Useful code is adopted behind Company HQ contracts only after license, state, security, and acceptance checks. Bulk-installing every framework would create duplicate schedulers and hidden cost.</p></article>
      <article><Wrench size={22}/><h3>Python now, Rust where it wins</h3><p>Python is the current control plane because it integrates quickly with Codex, ClawTeam, browser tests and evidence scripts. Rust is a good target for a packaged process supervisor, file watcher, command runner, sandbox helper, or high-volume indexer once benchmarks show the Python path is the bottleneck.</p></article>
      <article><BookOpenCheck size={22}/><h3>What to type first</h3><p>“We are building X for Y. The customer problem is Z. Ask only material questions, use the smallest useful team, build the first useful version, and show the checks and results.”</p></article>
    </section>

    <section className="guide-policy">
      <div><span className="eyebrow">MODEL AND TEAM POLICY</span><h2>A capable head. A focused team.</h2><p>Automatic uses the reviewed flagship supervisor. The supervisor delegates suitable bounded work to smaller models. One person can fill several roles when a task is simple.</p></div>
      <div>{modelPolicy.map(([need, route]) => <article key={need}><b>{need}</b><span>{route}</span></article>)}</div>
    </section>
  </div>;
}
