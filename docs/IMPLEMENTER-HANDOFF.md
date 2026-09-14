# Implementer handoff

## Assignment

Turn this existing prototype into a clear, reliable, economical workspace where a nontechnical founder can explain an idea, answer necessary questions, see a plan, and let an overall supervisor organize useful functional teams through a verified result. This is shared tooling for any project, not a Pinky feature. Reuse the existing code and useful upstream components. The original Codex supervisor is your reviewer.

Read README.md, STATUS.md, ARCHITECTURE.md, UPSTREAM-REVIEW.md and REVIEWER.md first. Historical root guides describe the original installation and must not be interpreted as permission to modify it. For this initial phase, work, commit and push directly to main in small coherent checkpoints; no draft PR or prior reviewer approval is required. Fetch before pushing, reconcile concurrent changes without force-pushing, and continue through the agreed milestones. The original reviewer will inspect pushed commits afterward and may make corrections directly. Changing the user's running installation remains a separate deployment action.

## Milestone 1: portable, isolated development baseline

- Inventory every hard-coded original installation path. Add explicit app/runtime/state configuration with safe defaults; keep source checkout, project workspace and account home separate. Do not overwrite HOME/CODEX_HOME or copy authentication.
- Provide one documented setup/start command and a model-free demo mode using clearly labeled synthetic fixtures. Pin dependencies and preserve licenses. A clean clone must not read or write the original toolkit's state or a product repository merely by starting.
- Reproduce existing tests; fix any packaging/portability issues with meaningful regression coverage. Add a health/status page that names unavailable capabilities honestly.
- Acceptance: clean temporary checkout and empty state work; no project artifacts/global config changes; original local installation keeps working; required dependency versions and platform limits are documented.

## Milestone 2: an understandable goal-to-work flow

- Add a first-run walkthrough and an example goal. Make “discuss/plan” versus “start execution” unmistakable. Ask only material questions and preserve user drafts.
- Keep one primary conversation with the overall head. Show a concise proposed plan with deliverables, assigned owner, model choice/reason, current phase, blockers and the user's next action.
- Show research, product/design, engineering, QA, marketing/growth and operations when the goal benefits from them. Use an economical department supervisor only when coordinating actual specialist work. Queue work within real concurrency; don't invent an active roster.
- Improve graph readability, tasks, message threads, approvals, empty states and narrow layouts. The user must be able to understand what's happening without knowing framework names.
- Acceptance: a person can connect a fixture project, discuss an idea, approve a plan, follow work, answer a question, stop/resume and find the result. Capture actual desktop and narrow UI evidence. Do not substitute a colorful graph for functional controls.

## Milestone 3: real worker execution and durable communication

- Project native child thread IDs, lifecycle, ownership and reporting relationships into the map. Use real runtime events and one canonical ClawTeam task list.
- Deliver supervisor/worker and lead/lead direction through the real runtime. Distinguish queued, delivered, acknowledged and unread messages. Implement wake behavior explicitly rather than relabeling inbox storage as delivery.
- Persist bounded execution history with sequence IDs, replay cursors, retention and per-project boundaries. Resume after restart, avoid duplicate work/replies, and reconcile orphaned or failed workers.
- Acceptance: one bounded fixture goal with useful independent work; actual IDs and events visible; reply routing correct; stop/approval races and restart recovery tested. Use fake transports for broad tests and only one justified, economical live acceptance when needed.

## Milestone 4: frugality and selective upstream adoption

- Measure baseline context, cached input, output and child usage. Aggregate without double counting and distinguish estimated cost from billed usage. Implement configurable budgets/checkpoints and show when usage is unknown. A prompt asking for thrift is not a hard budget.
- Load compact role/task packets and selected memories on demand. Use existing code graph lookups when they save repeated exploration. Keep simple work with one agent; no automatic all-department fan-out.
- Select models using reviewed capabilities and actual account access. New model names do not establish quality or entitlement. Surface unavailable capacity without buying access or silently switching billing routes.
- Prioritize ECC's context/verification patterns, gstack's product/design/browser QA roles, and Superpowers' bounded plans/debugging/review techniques. Review exact source files and adapt conflicts; do not run all setup scripts or import every skill/hook. The full 40-repo candidate catalog is a menu to assess, not an installation queue.
- Benchmark any RTK/headroom/context-compression candidate against equivalent acceptance tasks and preserved error evidence before adoption. Avoid provider proxy/auth changes for speculative savings.
- Acceptance: measured cost/quality tradeoffs, budget enforcement tests, fallback behavior and clear usage UI. Do not claim percentage savings without matched evidence.

## Final operating behavior

For a new idea: clarify customer/outcome/constraints, research proportionately, plan, choose useful teams, execute, review, verify and prepare launch materials. Marketing and external outreach drafts are deliverables; sending/publishing/spending require appropriate user authorization. Keep reusable decisions and results in scoped memory. For an existing project: preserve its instructions and release gates. Avoid duplicate initialization and product-file pollution.

## Return to reviewer

At each meaningful checkpoint, push the commit and report its exact SHA/link, changed behavior, tests and actual results, UI evidence, usage measurements when available, upstream files/pins adopted, remaining gaps, and whether any live installation changed. Start with milestone 1 and continue through the remaining milestones without waiting for PR approval. Keep checkpoints bounded and do not call a milestone complete until its acceptance criteria pass.
