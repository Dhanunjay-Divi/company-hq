# Using Company HQ

Company HQ is the operating cockpit for a project, not a replacement for your IDE. Keep Cursor, VS Code, Xcode, the terminal, or GitHub open as usual. Use Company HQ to connect the project folder, describe the outcome, see the plan, approve execution, watch real runtime events, track tasks, and inspect usage signals.

## Everyday flow

1. Connect a local project folder. This creates Company HQ state outside the repo and does not edit project files.
2. Tell the overall supervisor what you want to build, who it is for, constraints, and what proof should count as done.
3. The first native supervisor turn is read-only planning. It should choose the smallest useful team, reuse code intelligence where available, define acceptance checks, and call out risks.
4. Approve execution only after the plan is acceptable. That separate approval switches the native session to workspace-write inside the approved project folder.
5. Review work in your IDE and in Company HQ together. Passing tests, reviewed diffs, screenshots, and recorded runtime events are evidence; task status alone is not.

A good first prompt is:

> We are building X for Y. The customer problem is Z. Inspect read-only, ask only material questions, propose the smallest useful team, acceptance checks, risks, budget limits, and first implementation slice. Do not edit files yet.

## Usage and cost

The run screen shows provider-reported token counts when the native runtime emits them: input, cached input, output, total, and report count. This is local run evidence. It is not account-wide quota, billed money, or a savings claim.

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
