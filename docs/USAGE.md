# Using Company HQ

Company HQ is the operating cockpit for a project, not a replacement for your IDE. Keep Cursor, VS Code, Xcode, the terminal, or GitHub open as usual. Use Company HQ to connect the project folder, describe the outcome, see the plan, approve execution, watch real runtime events, track tasks, and inspect usage signals.

## Quick start

From the Company HQ repo:

```sh
cd /Users/uno/Projects/company-hq
python3 scripts/hq.py bootstrap --demo
```

Use demo mode first. It opens a local URL with fake fixture data, does not call a model, and does not edit any project. When the page opens, try the flow: **Run overview → Connect project → Discuss & plan → Approve plan & start execution**.

For real local use after demo works:

```sh
cd /Users/uno/Projects/company-hq
python3 scripts/hq.py bootstrap
```

Open the URL printed by the command. Connect the project folder you want Company HQ to help with, describe the goal, and keep the first turn as planning. Execution starts only after the plan finishes and you approve it.

Useful commands:

```sh
python3 scripts/hq.py status
python3 scripts/hq.py stop
python3 scripts/hq.py check
```

`status` tells you whether the local app is running. `stop` closes it. `check` runs the model-free validation suite.

## Codex and Claude

Codex is the live runtime wired today. Company HQ reuses your existing authorized Codex app/runtime, keeps its state outside product repos, starts with a read-only planning turn, then asks you before switching into execution. Opening Company HQ by itself does not consume model tokens; tokens are used only when you send work to a provider-backed supervisor or worker.

Claude can be reused the same way once a verified adapter exists for your authorized Claude runtime or CLI. The rule is the same: no copied credentials, no hidden account switching, no provider proxy unless you explicitly choose it, and no claim that Claude is running until Company HQ can show real started sessions, messages, approvals and usage evidence.

The simple default is: use Codex now, keep the supervisor model on automatic policy, set a workspace token budget, and let Company HQ choose smaller workers only when the task truly benefits from them.

## Everyday flow

1. Connect a local project folder. This creates Company HQ state outside the repo and does not edit project files.
2. Tell the overall supervisor what you want to build, who it is for, constraints, and what proof should count as done.
3. The first native supervisor turn is read-only planning. It should choose the smallest useful team, reuse code intelligence where available, define acceptance checks, and call out risks.
4. Approve execution only after the plan is acceptable. That separate approval switches the native session to workspace-write inside the approved project folder.
5. Review work in your IDE and in Company HQ together. Passing tests, reviewed diffs, screenshots, and recorded runtime events are evidence; task status alone is not.

A good first prompt is:

> We are building X for Y. The customer problem is Z. Inspect read-only, ask only material questions, propose the smallest useful team, acceptance checks, risks, budget limits, and first implementation slice. Do not edit files yet.

## Usage and cost

The run screen shows provider-reported token counts when the native runtime emits them: input, cached input, output, total, and report count. Each workspace also has a reported-token ceiling. The default is 200,000 tokens and the Run overview lets you raise, lower, disable, or switch it to tracking-only mode. Once reported native totalTokens reaches the enforced ceiling, Company HQ blocks the next start, send, execute, or approval action for that workspace. This is local run evidence and an action gate. It is not account-wide quota, billed money, or a savings claim, and it cannot guarantee a provider-side mid-turn hard stop.

Company HQ stays frugal by default:

- Use one agent for simple changes.
- Use bounded teams only for independent work streams.
- Start with smaller capable models and escalate only for complexity, risk, failure recovery, architecture, security review, or final synthesis.
- Use code intelligence before broad repeated file reads.
- Use output reduction only when raw evidence is retained and the reducer passes gates.

## Python, Rust, and C

Python is the current control plane because it integrates quickly with native Codex, ClawTeam, browser acceptance tests, evidence scripts, and the existing setup. A rewrite in Rust or C is not automatically better while the product contract is still changing.

Rust is a strong candidate for narrower runtime pieces once benchmarks justify the port: process supervision, cancellation, file watching, sandboxed command execution, high-volume indexing, IPC, and packaged desktop helpers. A Rust component should pass the same lifecycle, permission, recovery, account-boundary, and browser acceptance tests before replacing the Python path.

## Repository adoption

The **Why this stack** screen separates integrated, default-off, benchmarked, doc-reviewed, and inventoried repositories. Useful code from upstream projects is adopted behind Company HQ contracts only after license, state, startup-write, dependency, permission, security, and acceptance checks. Bulk installing every framework would create duplicate schedulers, hidden cost, and unclear authority.
