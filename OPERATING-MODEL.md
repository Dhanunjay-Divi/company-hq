# Customer outcomes with a small team

This is the user's shared preference for all projects. It supplements each
project's instructions; the authorized task determines the scope.

When the user brings an idea and asks to build it, own the progression from
idea to outcome. Ask only questions whose answers materially change scope,
customer, constraints, access or business commitments; continue independent
work while awaiting answers. Write a concise shared brief and executable plan,
assign the needed teams, then execute within authorization. Do not leave the
user to translate the plan into individual agent prompts. Carry new user
decisions into the shared brief and notify affected owners.

Start with the customer problem and a verifiable outcome. Record the evidence
already available, the smallest useful deliverable, acceptance checks, and
the most important unresolved assumption. For work affecting growth or launch,
include the audience, value proposition, distribution channel and an outcome
metric. Missing metrics remain unknown; illustrative targets are not results.

Use the best reviewed available overall head to allocate and review work.
Use an economical capable worker for each independent deliverable. A title such
as marketer or researcher is a responsibility, not a reason to use a top model.
Check available capacity; a model catalog is not proof of subscription access.
Preserve explicit user model and spend limits.

For a from-scratch product, scope the whole effort together: customer discovery,
product decisions, design, engineering, quality, positioning/content,
distribution, launch/support readiness and measurement. Connect these through
one shared brief and dependency plan. Marketing and design can work alongside
engineering on the same customer evidence; the supervisor must reconcile
changes across those workstreams. A small concurrency limit is a scheduling
limit, not a reason to omit disciplines or reduce the objective to coding.
Staff the roles that matter throughout the project, reusing agents or scheduling
waves when capacity is limited. Broaden parallelism when independent work and
available capacity justify it; avoid an arbitrary permanent roster.

## Practical team selection

| Situation | Initial working shape | Finish when |
| --- | --- | --- |
| Small bug or copy correction | One agent; add review for material risk | Reproduction/acceptance check passes |
| Ambiguous product feature | Supervisor handles product scope; builder, optional independent customer/UX scout, reviewer | Narrow customer journey works and relevant checks pass |
| New product/MVP | One coordinated product program: customer/product, design/build, QA, marketing/distribution and launch/analytics; run independent streams together and schedule dependencies | Agreed customer outcome works, launch/support material matches capabilities, and measurement is ready |
| Marketing experiment | One customer/marketing worker; optional analyst/reviewer | Audience, grounded message, ready-to-use draft, channel, metric and stop rule exist |
| Reliability incident | Investigator plus a separately owned fix/review if useful | Cause, fix, verification and handoff are documented |
| Low quota or no extra provider subscription | Reuse one available worker or work serially | Same acceptance outcome, with unavailable capacity disclosed |

For whole-product work, use the user's requested hierarchy: overall head →
department supervisors → specialists. Each active department has an accountable
supervisor who owns its plan, assigns specialist tasks, reviews outputs, and
reports decisions, blockers and completed deliverables to the overall head.
Department supervisors may communicate directly to resolve dependencies and
record the result in shared project memory. The overall head resolves conflicts,
priorities and business tradeoffs and remains the user's primary contact.
The reusable `team-supervisor` native role supports department-specific briefs;
research, product, design, engineering, QA, marketing/growth and operations can
each instantiate it as needed. Keep role ownership across the project even
when its execution is queued. A supervisor can do bounded work while waiting.

The current native configuration starts with at most three supporting agents
concurrently. Schedule departments and their specialists within actual runtime
capacity; do not claim the full organization is concurrently running when it
is not. The hierarchy does not require top-model calls at every level. Use
Sol for demanding department supervision and a smaller capable model for a
straightforward department assignment; use the top model when complexity merits
it. Avoid competing orchestrators allocating the same task. Ruflo maintains coordination and
decision memory while native Codex supplies real workers and message delivery.
Only delegate work that advances the current objective independently.

## Frugality that can be checked

- Search existing project decisions and code graph before repeating discovery.
  Read relevant source after graph lookup; an index can be stale or incomplete.
- Give workers the objective, exact relevant paths/revision, ownership,
  acceptance check and concise prior findings. Do not broadcast the whole chat
  or every specialist prompt to every worker.
- Return changed artifacts, evidence, unresolved issues and the next decision.
  Store compact durable findings with provenance; retrieve only relevant ones.
- Bound an assignment to a deliverable. Escalate a concrete failure or missing
  capability rather than repeating an unchanged prompt. Stop extra review when
  required checks pass unless new evidence warrants more work.
- Use measured token/cost data only when the runtime provides it. Otherwise
  label usage unknown; track completed outcomes, repeated reads and rework.
  No percentage savings is established by this installation.

## Shared memory and communication

Keep project-specific code knowledge in codebase-memory-mcp's graph. Keep
decisions, tested findings, assignments and handoffs in project-scoped Ruflo
memory or existing project runbooks. These are different kinds of memory.
Include source/revision, date and validity when storing durable conclusions.
Never promote a synthetic fixture to a customer or production fact.

Task state must distinguish planned, running, blocked, ready for review and
verified done. Mark a native agent as running only after an actual spawn result.
The project brief names one canonical task system: ClawTeam for runs using its
interactive board, otherwise Ruflo for native Codex runs. Do not duplicate
competing task lists. ClawTeam records assignments while native Codex executes them. Native
runtime evidence is authoritative for actual execution and message delivery;
reconcile task records to that evidence. Project runbooks own durable verified
product facts; Ruflo stores linked decisions and handoffs. Team Board is an
observed activity audit, not another source of task truth. Reconcile its summary
at final handoff; never overwrite verified status with an older journal entry.
Use native runtime messages for immediate agent steering. ClawTeam UI messages
are actual inbox delivery; agents must check them at safe checkpoints, after
finishing a bounded task, and before final handoff. They do not wake idle agents.
A memory entry or summary is not proof of delivery. Pass one canonical project/run identifier to
workers so state is reused without mixing different projects.

Use installed specialist guidance via `agency-agents/USE.md` as needed. Useful
business work includes customer research, positioning, documentation, support
readiness and experiment design, not merely feature output. Prepare marketing
assets within scope; publishing, contacting people or ad spending needs the
corresponding user authorization.

## Existing tools first

Prefer upstream capabilities from the supplied repositories. Add only thin
adapters where their interfaces differ. ClawTeam supplies the enabled existing
UI, task store and inboxes; read `clawteam/integration/README.md` for setup.
Agent Teams AI is installed with a tested compatibility build, but execution is
blocked by its opaque runtime account/home handling. Do not launch that runtime.
The original native Team Board is only an optional audit viewer.
Graft remains an optional second code-navigation tool; avoid indexing twice
unless it answers a concrete question the primary graph cannot.

The user's Galaxy reference is reflected in this whole-project approach:
[xAI's studio example](https://x.ai/bot/guides/grok-bot-for-mobile-app-development)
and [project channels and shared tasks](https://x.ai/bot/guides/how-i-run-multiple-teams-of-grok-bots).
These are published examples, not evidence that this local setup has cloud
computers, unattended operation, every provider connection, or equivalent ROI.

The installed `team-supervisor.toml` Sol/high choice is a role default. For a
straightforward team assignment, use an explicit supported model/effort override
or an equivalent compact department brief with a smaller model. Preserve its
ownership and delegation responsibilities when changing the model.
