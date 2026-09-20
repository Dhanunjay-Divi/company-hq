# Shared coding-agent toolkit

Applies to ongoing and future projects. Runtime state is outside product repositories and the Company HQ source checkout. Native subagents for useful independent
parts of authorized project tasks are enabled by the user's team preference.
Installation alone does not authorize product initialization, deployments,
authentication changes, hooks, schedulers, external model runtimes or services.
For Pinky work, also use the `pinky-ops` skill and canonical project runbooks.

## Your reusable team setup

For a clean Company HQ source checkout, use `python3 scripts/hq.py bootstrap --demo` for a model-free first run or `python3 scripts/hq.py bootstrap` for normal local use. These commands keep Company HQ state external and preserve provider account homes.

For a product idea, the overall head owns a shared customer-focused plan through
research, design, engineering, QA, marketing and launch. Each functional team
has a supervisor who assigns and reviews specialist work. Teams share findings
and coordinate dependencies. Read `OPERATING-MODEL.md` for this standing policy;
`agency-agents/USE.md` routes to the installed upstream specialist library.

Ruflo and codebase-memory-mcp are registered globally for future Codex tasks.
Their real MCP handshakes and tool calls have been tested. If an already-running
client does not expose them, reload its MCP connections or start a new task;
installation does not inject tools into an already-created model context.
Ruflo stores project task/decision state; codebase-memory supplies structural
code knowledge. Read their integration runbooks before first use. Neither makes
model calls in the enabled paths. Token savings have not been benchmarked.


The preferred UI is **Company HQ**. It reuses the actual Agent Teams AI graph
package while ClawTeam supplies task columns and real inboxes, Ruflo supplies
shared decision memory, and native Codex supplies supervisor execution. Read
`clawteam/integration/README.md` for its safe launcher and CLI. Run `team-ui` to
start or reuse it and open the printed local URL; `team-ui status` reports it and
`team-ui stop` stops it. After attaching an approved workspace, Company HQ can
start, send follow-up work to, and stop the native Codex supervisor, and it shows
runtime approval requests for an explicit user decision. Inbox delivery waits
for the recipient's next checkpoint; it does not automatically wake an idle task.
ClawTeam owns tasks for board workflows.
`agent-team view` remains the original optional macOS summary viewer.

You do not need to repeat the team request in ordinary Codex project tasks.
The global user instructions and `agent-toolkit` skill request bounded native
delegation when useful, and board recording for those team workflows. Simple
work stays with one agent. New tasks can load these instructions; running tasks
or explicit model overrides can retain older settings. This covers Codex on
this Mac; other agent apps must be configured separately.

For a terminal session in any existing project:

```sh
agent-team work --project /absolute/project "Build the requested feature"
```

This launches native Codex using its existing login and permissions. That task
can edit the selected project as instructed; the toolkit installation itself
does not. `agent-team start` only creates an external activity journal.
Recorder instructions: `skills/agent-toolkit/references/team-board.md`.

Model defaults are GPT-6 Astra / high as the supervising lead, Terra / medium for
supporting agents, with at most three concurrent supporting agents. Personal
roles are Scout (Luna/low), Builder (Terra/medium), and Reviewer (Sol/high).
`--model gpt-5.5` is supported. Astra plans, delegates, synthesizes and performs
final review; routine execution stays with smaller workers. Department supervisors use economical capable models by default; the overall head selects their model for the assignment. `--reason` is optional model-selection context.
These are today's reviewed choices. The user's final policy is the best
reviewed available supervisor, across providers when their integration is
available and worthwhile, rather than a permanent Astra requirement.

`agent-team work` now defaults to `--model auto`, reading the available model
catalog and `routing.json`. `kickoff.py --project /absolute/project` refreshes
cached tool/model metadata and can update a previously managed supervisor
default for future tasks. It preserves a manually changed default and does
not start workers or initialize product files. New team creation remains
task-driven. See `MAINTENANCE.md` for automatic reviewed updates and the weekly
maintenance check; useful changes are staged and tested before activation.

Codex is the verified executor here today. Other named providers are discovery
or future integration candidates, not installed cross-provider workers. Grok
Bot is currently desktop-only for this toolkit. Use `PROVIDERS-RESEARCH.md`
when a concrete project need justifies adding another client.

## What to use

| Tool | Use / disposition |
| --- | --- |
| Native Codex agents + Team Board | Enabled: native agents and communication, model-pinned personal roles, economical defaults, external recorder and native macOS viewer. |
| Ruflo 3.41.2 + CLI 3.33.0 | Enabled narrow sandboxed MCP for project task/decision memory and coordination. See `ruflo-integration/README.md`; general CLI startup remains disabled. |
| Agent Teams AI 2.14.2 | Its actual graph package is reused in Company HQ. The separate full upstream app and compatibility build remain blocked because the bundled runtime replaces account-home state and manages auth artifacts. See its BUILD-AND-SAFETY.md. |
| Orkas | Alternative desktop orchestrator with provider/runtime usage; not needed alongside native Codex now. Not installed. |
| ClawTeam 0.3.0 + Company HQ | Enabled local UI with the Agent Teams graph, ClawTeam tasks/inboxes, Ruflo memory, and native Codex start/send/stop plus user-reviewed approvals. Inbox delivery does not wake idle agents. |
| DSH Agent Teams | Plugin for DeepSeek Harness, not a Codex upgrade. Not installed. |
| Squad | Copilot-centered workflow; consider if adopting Copilot intentionally. Not installed. |
| Agent Squad | Application-level multi-agent SDK, not a developer-task dashboard. Not installed globally. |
| MeshClaw | LoRa/OpenClaw hardware connectivity; not relevant to ordinary app projects. Not installed. |
| Graft 0.18.0 | Installed and fixture-tested through `graft.py`. Deterministic local code navigation; external graph directories, telemetry off. See `GRAFT.md`. |
| codebase-memory-mcp 0.10.8 | Installed, registered and fixture-tested primary code graph. Twelve guarded tools, durable external state, watcher/autoindex off, repository writes prevented. |
| agency-agents | Actual pinned upstream role/playbook library installed; load relevant specialist guidance through `agency-agents/USE.md`. Department-supervisor native role also installed. |
| ECC / gstack | Adopt compact review handoffs and reproducible QA/regression records as methods, not unreviewed installers/hooks. Track both upstreams. |

Catalog references are review snapshots, not guarantees of security or complete
feature support. Licenses still apply; attribution alone does not replace their
terms. Agent Teams uses AGPL-3.0; keep its code separate from proprietary products
unless the applicable obligations are addressed.

### Ruflo integration boundary

The enabled MCP invokes only reviewed upstream memory/task/coordination handlers
under an OS sandbox; network is denied and writes stay in hashed external project
state. Cross-process task and memory persistence passed real tests. The pinned
AgentDB bridge split its public write/read stores, so the supported bridge-off
setting is used. Hash/mock similarity is not exposed as semantic search.
General CLI init/startup, hooks, daemons and model workers remain outside the
enabled surface. Existing dependency-audit findings are recorded in the pinned
installation receipt; there is no claim the full framework is security-cleared.

## Upstream checks

Run `python3 -B check_updates.py`.
It queries public GitHub metadata for the fixed catalog repositories and
caches the result for 24 hours. `--refresh` checks again at a new project kickoff
or on explicit request. It does not download/execute upstream code, install
updates, touch project files or use a model. A missing/network-limited result is
reported as unavailable, not up to date.

The global `agent-toolkit` skill and `the current provider's user instructions` tell future
agents to do this at project kickoff and first adoption in ongoing projects.
This is instruction-driven at task start, with a weekly Codex maintenance
heartbeat; there is no OS daemon or guarantee that
every already-running task has refreshed its instructions. New skills normally
appear in a later turn; restart the client if discovery has not refreshed.
Explicit `$agent-toolkit` is optional. Other clients must read the same guidance;
this does not silently configure every coding product on the machine.

## Same project across accounts

- Keep project files, commits, tests and concise handoff notes as the durable
  source of truth. Both authorized accounts can work on those local files.
- Shared user skills and project instructions provide reusable procedures; they
  do not merge account-specific quotas, cloud chats, connectors or memory.
- Use supported sign-in controls. Do not copy/swap authentication files or
  share active session databases just to merge accounts. This setup does not
  change the current login or configure a second account.
- If two agents write simultaneously, use separate Git worktrees and explicit
  ownership; reconcile reviewed changes. One writer can continue the same
  checkout after the previous writer stops. Never assume a new login already
  knows an earlier conversation: load the current handoff.
- Do not automatically rotate accounts on rate limits or start extra paid
  workers. Each account/runtime keeps its own actual entitlements and usage.
- Only share project notes across accounts/workspaces that are authorized to
  access that project's information. Keep credentials, customer data and raw
  transcripts out of this global toolkit.

## Cost and scope

No framework guarantees token savings. Small review packets, scoped agents,
saved test evidence and avoiding repeated broad audits are the default savings
strategy. Installation is not proof that all optional features work. The board
and structural graph operations make no model calls. This setup used Sol implementation leads, a Terra review supervisor and a
Luna specialist delegated by that supervisor, under the overall head. Actual
agents use your existing account's entitlement; model labels alone do not
establish prices, and more agents can increase usage. No new paid provider
subscription, production promotion or GitHub Actions run is part of this setup.

## Files, rebuild and rollback

Board files live under `teamboard/`, with a command symlink at
the optional legacy `agent-team` launcher. The app reads local run JSON, has no network server
and does not read login files. Run files are private, writes are serialized and
atomic, and each run retains its latest 500 events with an explicit trim count.

`bash teamboard/macos/build.sh` rebuilds the app from local Swift source.
`python3 teamboard/configure_codex.py` reapplies economical defaults and roles.
The installer backs up changed config, preserves unrelated parsed settings,
refuses symlinked config or conflicting roles, and serializes its own installs.
Avoid simultaneous Codex Settings/file edits while explicitly rerunning it;
arbitrary editors do not honor its advisory lock. See `teamboard/VERIFICATION.md`.

To stop visibility, quit Agent Team Board; no startup service was installed.
To reverse the extension, preserve desired journals, remove the `agent-team`
symlink and the three added `~/.codex/agents/team-*.toml` files, and revert only
the added model/team settings and instruction paragraphs. Original files are
backed up in `teamboard/backups/2026-09-13/`, with a separate immediate config
backup in a timestamped folder. Compare before restoring whole files so later
user changes are retained. Product repos need no rollback.

Sources: https://developers.openai.com/codex/skills/ and
https://learn.chatgpt.com/docs/auth (official Codex behavior); project source
links and pinned review refs are in `catalog.json`. The read-only comparison
was completed 2026-09-13; recheck upstream before expanding integrations.
