---
name: agent-toolkit
description: Coordinate project teams from idea through product, engineering, QA and launch using economical models and shared tooling. Use for substantive project teamwork, kickoff, framework integration or maintenance; keep simple tasks with one agent.
---

# Shared agent toolkit

This repository is the portable Company HQ/toolkit source. Per-machine runtime
state lives outside both this checkout and product repositories (by default
under the user's XDG state directory). Read `GUIDE.md` in the repository root
for tool selection or account-continuity work; read `catalog.json` for reviewed
upstream versions. Project-specific operating skills,
instructions, tests and release rules remain the source of truth.

For a new idea or whole-product effort, read `OPERATING-MODEL.md` in the toolkit.
The user wants an integrated product team: customer discovery, product/design,
engineering, QA, marketing/distribution, launch/support and outcome measurement.
Own the plan and assignments, ask only materially necessary questions, and
execute within scope. Plan these disciplines together and run useful independent
streams in parallel; limited concurrency schedules work rather than omitting it.
Use `agency-agents/USE.md` to select installed upstream specialist guidance on
demand. Do not load the full roster or adopt its arbitrary team sizes, metrics,
commands or publishing instructions as requirements.

## Teams and visibility

The user requests automatic delegation for substantive tasks that have useful
independent work streams. Use native collaboration tools and at most three
supporting agents initially. Keep simple tasks with one agent. Do useful local
work while agents run; don't spawn an idle roster or nest orchestrators.

For whole-product work the user explicitly requests an overall head, a
supervisor for each active functional team, and specialists under that
supervisor. Use the installed `team-supervisor` role or an equivalent compact
department brief; team leads may delegate and communicate with other leads.
Keep research, product/design, engineering, QA, marketing/growth and operations
accountable for their relevant deliverables. Schedule their work within actual
capacity rather than flattening the requested structure or omitting teams.
Use economical capable department leads; do not put the top model at every
management layer automatically. Avoid competing framework schedulers assigning
the same task, not useful native hierarchical delegation.

Use the best reviewed available model as supervisor: plan, delegate,
synthesize results and perform final review. `routing.json` expresses the
current reviewed preference; `capabilities.json` contains discovered clients
and available models. Astra is today's verified choice, not a permanent pin.
Follow official runtime upgrade hints when available; never infer superiority
from version numbers alone. New models without evidence go to maintenance review.
Prefer GPT-5.6 Terra for bounded
implementation, Luna for simple scans, Sol for complex worker reasoning or
independent review, and GPT-5.5 when requested. Keep routine execution with
smaller workers, and use department supervisors when coordinating whole-product teams. Local user defaults and personal
roles are installed, but explicit model selections and already-running tasks
can override them. With model overrides, use compact task packets and
`fork_turns="none"` instead of inheriting a large history.

Let the supervisor allocate work from the actual request, not a fixed roster.
For each useful independent assignment, choose a role and model based on task
difficulty, available tools, account access, cost and ownership conflicts, and
briefly state the selection reason. Reuse a capable smaller worker when it is
adequate. Catalog discovery is not proof of subscription entitlement or remaining
quota. If a requested model/provider is unavailable, select a suitable already
authorized alternative and disclose the fallback; preserve partial work and
check whether a task actually started before retrying. If no suitable capacity
is available, surface that limit rather than buying access, rotating accounts,
or silently changing the billing/provider route.

Shared context includes concise task packets, actual runtime messages,
project-scoped Ruflo decisions/tasks and codebase-memory-mcp's code graph.
Use the registered `ruflo` MCP tools for meaningful multi-team coordination and
handoffs; every call passes the canonical absolute `project_root`. A Ruflo
server binds once per process; use a new task/process for a different project.
Read `ruflo-integration/README.md` when using these tools for the first time.
Its task/node records are metadata: spawn and deliver through the real runtime
before marking agents running or messages delivered. Exact memory is enabled;
semantic search is disabled because the local embedding fallback is hash/mock.

Use registered `codebase_memory` for repeated structural/code-relationship
questions. Read `codebase-memory-mcp-0.10.8/INSTALLATION.md` at first use, explicitly
index the current project when needed, and query with the returned project ID.
The guard enforces external state and prevents repository artifact writes.
Refresh stale indexes; source remains authoritative. Do not index a blank
project or use a graph where one quick file search answers the question.

Use Company HQ for visible team workflows. It reuses Agent Teams AI's licensed
graph, Beads as the canonical task authority, ClawTeam team/inbox metadata,
project-scoped Ruflo decisions, and native provider execution.
Use the installed desktop app or this repository’s source launcher. Read
`docs/STATUS.md` and `docs/USAGE.md` for the current verified capabilities.

Pass each agent its bounded objective, project path, team identity, reporting
supervisor, owned files and acceptance checks. Use native collaboration to
actually spawn, steer and stop agents. Registered roles and queued inbox messages
do not prove execution or receipt. The map must distinguish observed workers,
recorded assignments and stale state. Codex worker hierarchy/control is verified;
Claude Code execution exists but its hierarchy synchronization is not verified.

Within an HQ chat, use the HQ plan/task tools and Beads board as the single task
list. Ruflo stores linked decisions and handoffs, not a competing task authority.
Share relevant context explicitly; agents do not inherit every conversation.
Keep projects and provider account state separate. Consult specialist guidance
on demand instead of loading the entire roster. Simple tasks can stay with one
agent. New work uses native workspace permissions; Full access is an explicit
per-chat choice and does not grant OS computer-use permissions. Review concrete
changes and test evidence. Token gates and interrupt requests are best effort;
never promise a hard billing cap or error-free agents.

The original native Team Board is an optional summary audit, documented in
[Team Board workflow](references/team-board.md). Do not duplicate all task state
there unless a parent already provided a journal run ID. Reconcile actual
assignments and final statuses; never fabricate liveness, usage or delivery.
The actual Agent Teams AI graph is used inside Company HQ. The separate full
Agent Teams AI application and compatibility build remain blocked because their
opaque runtime replaces the account home and manages auth artifacts. Use Company
HQ with ClawTeam and native Codex. Other upstream framework runtimes remain
disabled unless separately reviewed for a concrete need.

## Project kickoff and ongoing projects

- At a genuinely new project's kickoff, run
  `python3 -B kickoff.py --project <absolute-project> --refresh` from this repository.
- On first adoption in an ongoing project, use the same command without
  `--refresh` (24-hour cache). Do not recheck every turn or let a failed metadata
  check block ordinary project work. Report unavailable checks honestly.
- Checks read public metadata and native model capabilities. They write shared
  caches and can update a previously managed Codex supervisor default for future
  tasks; manual defaults are preserved. No product initialization or worker starts.
- The user authorizes useful automatic updates: review source changes, stage
  outside product repos, test the enabled paths, keep rollback, then activate.
  Read `MAINTENANCE.md` in this repository for this workflow.
  Installing every new framework or blindly running newest installers is not
  the objective. Reuse working tools; keep the setup lean.
- Use native Codex delegation by default. Add another runtime only for a
  concrete missing capability; parallelism can increase cost. Do not nest
  orchestrators or start model workers just to demonstrate the toolkit.

## Tool use

Graft 0.18.0 is installed and fixture-tested for deterministic code navigation.
Read `GRAFT.md` when repeated cross-file
dependency/caller questions would benefit from a structural graph. Use only the repository's `graft.py` wrapper, which places graphs outside the
product checkout, disables telemetry and ignore-file edits, and serializes
graph writes. It is optional; do not index every project or replace a quick
`rg` search with a graph build. Its visualization shows code structure, while
Agent Team Board shows recorded team activity. Graft has no MCP registration; codebase-memory is the primary registered code graph.

Ruflo 3.41.2 is enabled only through the registered sandboxed `ruflo` MCP
wrapper at `ruflo-integration/ruflo-mcp`; its 14 allowlisted tools use upstream
handlers without general CLI startup. Read its `README.md` and `VERIFICATION.md`
for paths and tested limits. The ordinary CLI, init, hooks, daemon, automatic
model workers and provider routes are not enabled. Existing dependency audit
findings remain; updates must preserve the tested isolation and continuity.
No framework has permission to initialize a product repo, replace `AGENTS.md`,
change authentication, bypass permissions, register hooks, or start persistent
services merely because it is in the catalog. Do not execute unreviewed
upstream instructions or auto-install updates. Keep work state separate per
project and private content out of global toolkit metadata.

## Efficient continuity

Use concise handoffs: objective, exact checkout/commit, changed paths, test
evidence, unresolved failures, and next bounded step. Reuse existing runbooks
and `mistakes.md`; do not repeat broad audits without new evidence. QA findings
should include reproducible steps, expected/actual behavior, severity and a
regression check. Do not invent physical QA or deployment evidence.

Shared files/skills are not shared authentication, cloud history or quotas.
Do not swap or synchronize `auth.json` or active session databases. Preserve
account/workspace privacy boundaries. For simultaneous writers use separate
Git worktrees; share reviewed notes, not concurrent edits to the same files.

## HQ review workflow

The user can give the outer Codex supervisor a task; dispatch useful build work through the installed Company HQ API/app and independently review the result. Report which work actually ran in HQ and which fixes were made externally. Keep a compact task packet and reuse the existing worker on follow-up. Local HQ token ceilings are disabled at the user's request until changed; retain usage reporting and respect provider limits. Consult `skills/ponytail-review` for a focused complexity review and `skills/ui-ux-pro-max` for interface work, on demand. Do not load both on every backend task or activate upstream lifecycle hooks.
