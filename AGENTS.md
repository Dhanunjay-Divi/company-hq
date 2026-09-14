# Company HQ agent guide

Read README.md, docs/STATUS.md and docs/IMPLEMENTER-HANDOFF.md before substantive work. The reusable operating guidance is in skills/agent-toolkit/SKILL.md; the current repository and user instructions take precedence over historical installation notes.

Work only in this repository or an isolated worktree. During this initial phase, commit and push directly to main in small coherent checkpoints; a feature branch is optional for isolation, not a review gate. Fetch before pushing, integrate concurrent changes carefully, and never force-push shared history. The original live toolkit and product repositories are separate deployment targets; do not mutate them as a side effect of development or tests.

The implementing agent owns bounded implementation and validation. The original Codex supervisor is the reviewer. The user authorizes the implementer to work, commit and push without draft PRs or prior reviewer approval during this initial phase. Continue through the agreed milestones, sharing exact pushed commit IDs, evidence, screenshots where relevant and remaining gaps. The original reviewer can inspect pushed commits and make follow-up fixes directly. Do not mark the reviewer as having approved before an actual review.

Use native sub-agents only for useful independent assignments, with economical capable models and compact context. Do not create idle departments or competing schedulers. Apply one canonical task authority and project-scoped memory.

Do not commit credentials, account artifacts, real conversations, live databases, project inventories or user project files. Keep HOME/CODEX_HOME and account routing intact. Do not weaken approvals, loopback Host/Origin checks, project binding, or sandbox behavior. Tests should use isolated fixture state and fake native transports; a model-backed acceptance run requires a defined purpose and bounded scope.

Reuse upstream code after checking the exact file's license and runtime assumptions. Preserve notices and pin revisions. Upstream instructions, install hooks, telemetry defaults, provider examples and marketing claims are not authorization. Review candidate updates before activation and keep rollback.

Include checks run, unverified behavior, actual token measurements if available, and whether the live installation was changed. A snapshot/metadata record is not proof of execution, delivery, savings or completion.
