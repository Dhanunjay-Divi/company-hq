# Using Company HQ

Open Company HQ and type what you want to discuss or build. No folder or project name is required. Company HQ provides the conversation and team views; the connected native Codex engine performs model work. You can keep your normal IDE open to inspect files and changes.

## Quick start

From the Company HQ repo:

```sh
cd /path/to/company-hq
python3 scripts/hq.py bootstrap --demo
```

Demo mode shows synthetic data without calling models. Open a demo chat from Your chats, then explore Team, Tasks, and Activity. Sending is disabled in demo mode.

For real local use after demo works:

```sh
cd /path/to/company-hq
python3 scripts/hq.py bootstrap
```

Open the printed URL, type in the central composer, and press Enter or the arrow. Shift+Enter adds a line. The first send creates a private app-managed workspace automatically. For existing code, use **Add project**. Adding a project after a chat is bound starts a separate project chat; the old conversation remains available. Execution starts after the plan finishes and you approve it.

To run the native desktop shell from the source checkout:

```sh
cd /path/to/company-hq/company-hq
npm run app:dev
```

The desktop shell starts or reuses the same guarded local backend under the hood. This is the developer app wrapper, not the final signed distributable package yet.

Useful commands:

```sh
python3 scripts/hq.py status          # real local app
python3 scripts/hq.py stop            # stop real local app
python3 scripts/hq.py status --demo   # demo app
python3 scripts/hq.py stop --demo     # stop demo app
python3 scripts/hq.py check           # model-free validation
```

`status` tells you whether the local app is running. `stop` closes it. `check` runs the model-free validation suite.

## Codex and Claude

Codex is the live runtime wired today. Company HQ reuses your existing authorized Codex app/runtime, keeps its state outside product repos, starts with a read-only planning turn, then asks you before switching into execution. Opening Company HQ by itself does not consume model tokens; tokens are used only when you send work to a provider-backed supervisor or worker.

Claude can be reused the same way once a verified adapter exists for your authorized Claude runtime or CLI. The rule is the same: no copied credentials, no hidden account switching, no provider proxy unless you explicitly choose it, and no claim that Claude is running until Company HQ can show real started sessions, messages, approvals and usage evidence.

Automatic follows the configured supervisor tier: currently Astra, as requested by the user. The five native-catalog models checked on 2026-09-21 are Astra, Sol, Terra, Luna, and GPT-5.5. The selected model is fixed for the native conversation; start a new chat to choose another. Smaller models are available for bounded worker tasks. Additional provider adapters and full nested team messaging are still incomplete.

## Everyday flow

1. Start a New chat and send your idea. A project folder is optional; app-managed working space lives outside your repositories.
2. Tell the overall supervisor what you want to build, who it is for, constraints, and what proof should count as done.
3. The first native supervisor turn is read-only planning. It should choose the smallest useful team, reuse code intelligence where available, define acceptance checks, and call out risks.
4. Approve execution only after the plan is acceptable. That separate approval switches the native session to workspace-write inside the approved project folder.
5. Review work in your IDE and in Company HQ together. Passing tests, reviewed diffs, screenshots, and recorded runtime events are evidence; task status alone is not.

A good first prompt is:

> We are building X for Y. The customer problem is Z. Inspect read-only, ask only material questions, propose the smallest useful team, acceptance checks, risks, budget limits, and first implementation slice. Do not edit files yet.

## Usage and cost

The Activity screen shows provider-reported token counts when the native runtime emits them: input, cached input, output, total, and report count. Each workspace also has a reported-token ceiling. The default is 200,000 tokens and the Activity view lets you raise, lower, disable, or switch it to tracking-only mode. Once reported native totalTokens reaches the enforced ceiling, Company HQ blocks the next start, send, execute, or approval action for that workspace. This is local run evidence and an action gate. It is not account-wide quota, billed money, or a savings claim, and it cannot guarantee a provider-side mid-turn hard stop.

Company HQ stays frugal by default:

- Use one agent for simple changes.
- Use bounded teams only for independent work streams.
- Use Astra for overall supervision as requested, Terra/Sol for useful department coordination, and smaller capable leaf workers. Escalate worker assignments only when complexity or evidence requires it.
- Use code intelligence before broad repeated file reads.
- Use output reduction only when raw evidence is retained and the reducer passes gates.

## Python, Rust, and C

Python is the current control plane because it integrates quickly with native Codex, ClawTeam, browser acceptance tests, evidence scripts, and the existing setup. A rewrite in Rust or C is not automatically better while the product contract is still changing.

Rust is a strong candidate for narrower runtime pieces once benchmarks justify the port: process supervision, cancellation, file watching, sandboxed command execution, high-volume indexing, IPC, and packaged desktop helpers. A Rust component should pass the same lifecycle, permission, recovery, account-boundary, and browser acceptance tests before replacing the Python path.

## Repository adoption

The **Why this stack** screen separates integrated, default-off, benchmarked, doc-reviewed, and inventoried repositories. Useful code from upstream projects is adopted behind Company HQ contracts only after license, state, startup-write, dependency, permission, security, and acceptance checks. Bulk installing every framework would create duplicate schedulers, hidden cost, and unclear authority.

## Roles and expectations

- Supervisor: owns the goal, chooses useful teams, reviews results.
- Team lead: coordinates one discipline and its specialists.
- Worker: completes a bounded assignment and returns evidence.

A role description is not a running agent. A bounded live Astra → Terra → Luna test completed, with parent links verified through the native API. The earlier Luna-lead attempt could not spawn its own worker. The current graph uses registered ClawTeam members; Activity shows observed immediate native child IDs. Nested worker messages, live graph synchronization, and provider-neutral routing still require further integration. One successful chat test does not establish that teams outperform one agent.

## Where data lives

Default app root: `~/.local/state/company-hq` (or `COMPANY_HQ_STATE_ROOT` / XDG override).

- `clawteam/managed-workspaces/<chat-id>/`: private working folder for a chat without an attached project.
- `clawteam/company-profiles/`: chat labels and project bindings.
- `clawteam/runtime/events/`: bounded recent chat/event snapshots (owner-only files, up to 500 events and 4 MiB per chat). Saved events are replay, not proof of a live worker.
- `clawteam/runtime/bindings/`: references used to resume native tasks.
- `clawteam/runtime/budgets/`: local reported-token policies and counters.

Native Codex continues to own its own account and thread storage; HQ does not copy auth files or scan native session databases. Unsent drafts currently live in the open UI and survive chat switching, but not a full page reload.

Streaming chunks no longer evict finalized messages from the replay budget. A private sequence watermark prevents event IDs from being reused after a restart during streaming. Disk-write failures still make replay best effort; this is not an unlimited transcript archive.

## Tools and settings

Settings checks the local installation on app load and on **Check again**, with no model prompt. It shows the active engine, shared memory, and code understanding. File paths and internal checks are under Technical details. Graft is off the default path. Engine sign-in and tool permission are verified when connecting/using that engine.

The intended additional-provider flow is native sign-in, verified connection, model/tool discovery, then selection from reviewed available models. That flow is not implemented for other providers today. A connection must not silently import old chats, copy passwords, change billing routes, or make all desktop-hosted plugins available without their own integration.

Codex app-server supports native tools and MCP events, but HQ has not verified every desktop capability. Desktop-hosted computer use, plugin management, rich attachments, voice, and all-provider parity are not claimed. [Official app-server event documentation](https://learn.chatgpt.com/docs/app-server#items).
