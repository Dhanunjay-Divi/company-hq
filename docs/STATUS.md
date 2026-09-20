# Verified baseline and limitations

Baseline source captured 2026-09-14 UTC. Historical verification documents are evidence from specific earlier iterations; this file is the current handoff summary.

## Working on the original Mac

- Actual Agent Teams AI canvas/React graph, avatars, hierarchy and click-through member/task details; custom responsive Company HQ shell and focus view.
- ClawTeam task create/update, owners and real file inboxes; loopback Host/Origin protections and private state directory.
- Project-scoped Ruflo note save/retrieve; codebase-memory MCP guard installed separately for structural queries.
- Native Codex app-server initialize/start/resume/steer/stop/approval bridge, preserving the existing account environment and bound project.
- Reviewed model catalog supplied to UI; kickoff/discovery utilities and update review procedure.
- Existing UI acceptance: isolated workspace, one Luna response through Start working, task moved to Done, Ruflo note round trip. Prior combined suite: 16 passing HTTP/bridge tests. This is evidence of these flows, not full autonomous-company validation.

## Implemented in the current PR stack, pending reviewer acceptance

- **Portable source/runtime split (PR #1):** configurable external Company HQ state, one-command setup/demo, capability health and active-source portability checks. The original live installation is not migrated by these source changes.
- **Plan-first onboarding (PR #2):** the first supervisor turn is read-only and project writes begin only after explicit user approval.
- **Observed worker communication (PR #3):** native child thread IDs/states are shown only from provider collaboration events; direct worker delivery has requested/sending/delivered evidence; bounded non-delta runtime evidence replays after restart.
- **Economy controls (PR #4):** Auto routes deterministically to the smallest reviewed available Codex tier and supported reasoning effort; provider-reported supervisor/child token totals are aggregated by latest thread totals; a warning/checkpoint blocks new model input after the user-selected threshold without killing the active turn.

These items are **implemented source, not fresh-clone/live acceptance claims**. The original Codex supervisor still needs to run the documented model-free suite, frontend build, restart tests and justified native acceptance before marking them verified.

## Remaining limitations

1. **Cross-platform acceptance.** Model-free setup is designed to be portable, but native Codex and Ruflo sandbox acceptance remains macOS-specific. Ruflo deliberately fails closed without its reviewed sandbox.
2. **Measured savings.** The prior tiny live acceptance reply still recorded 16,950 input tokens, 11,008 cached input and 21 output. The new controls avoid double-counting and stop new input at a checkpoint, but no before/after percentage or dollar savings is claimed until matched tasks are measured.
3. **Full worker lifecycle coverage.** Observed Codex children and correlated delivery are implemented, but cross-team wake/orphan/retry behavior still needs broader live acceptance. No synthetic liveness is shown.
4. **Full company execution.** Research/product/design/engineering/QA/marketing/operations remains the intended operating model; a complete idea-to-launch scenario has not been exercised. Do not create idle departments just to fill the graph.
5. **Provider independence.** Current execution is native Codex. Claude, Kimi, GLM, Grok and other subscriptions need separate reviewed official adapters that preserve their own account/auth boundaries and expose live catalogs/usage before Auto can route to them.
6. **Automatic updates.** Metadata checks and reviewed maintenance exist, but no repository CI/scheduler installs upstream updates automatically.
7. **Agent Teams AI runtime.** Its graph/UI assets are reused; its separate opaque runtime remains disabled because Company HQ owns the current account/project/permission boundary.
8. **Optional code/skill tools.** Graft, codebase-memory, Agency Agents and candidate skill packs remain on-demand. OpenMontage, Diagram Design, Scientific Agent Skills and extra graph/memory systems should not become startup context without a task-specific reason and review.

No production deployment or cross-platform runtime acceptance is claimed. Live task/message state and native receipts are intentionally not in this repository.

Additional portability findings from source inventory: the supervisor role template is preserved but the earlier configuration script installs only three other roles; Graft's arm64 Kotlin binding needed a manual build; generated Codex schemas are version-specific. These are implementation tasks, not finished installation features.
