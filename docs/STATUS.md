# Verified baseline and current gaps

Updated 2026-09-21 UTC.

## Complete and merged

### Portable isolated baseline

Milestone 1 is merged to main.

- Portable external runtime state and account/project boundaries.
- Model-free synthetic demo.
- Truthful capability/status UI.
- Public model-free CI on standard GitHub-hosted runners.
- Loopback/Host/Origin protections.
- Existing provider account home preserved.
- Cross-platform state/root checks and Windows-safe integration paths.

Baseline merge:
7c62305b27cd18ed49ce45399c0c6c85157e3ccd

Post-merge readiness fixes:
c903e6ad569efb7aa6e4e959a25467736b8ec330

The final post-merge reviewer reported no major issues on the reviewed head.

### Best-of-all bakeoffs

The architecture branch contains reproducible public model-free tests.

- Code intelligence: run 35553804431.
- Token efficiency: run 35553431498.
- Beads task store: run 35554136836.

The resulting target architecture is in [BEST-STACK.md](BEST-STACK.md).

## Working today

- Company HQ React/Vite control UI and Agent Teams graph adapter.
- Workspace creation and local project binding.
- Native Codex app-server start/resume/steer/stop/approval bridge.
- Current task/inbox compatibility through ClawTeam.
- Guarded project-scoped Ruflo memory path, installed by setup with lifecycle scripts disabled.
- Guarded Codebase Memory capability path, installed by setup from checksum-verified pinned release binary into ignored local state.
- Demo mode that blocks provider/model execution.
- Health/status view that disables unavailable runtime actions.
- Source/build/portability checks via the documented launcher.
- Per-workspace reported-token action gate in the native Codex bridge and Run overview.
- IDE-style app shell slice with desktop frame, command bar, status bar, supervisor evidence dock and visible capability/budget indicators.

## Architecture decisions now locked

- Company HQ remains the only orchestration/control authority.
- Beads is the target canonical task/DAG store.
- Codebase Memory MCP is primary warm code intelligence.
- Graphify is second-stage broad/cross-asset graph retrieval.
- Graft leaves the default path.
- RTK is first-stage command/test/log compression.
- Headroom is conditional second-stage structured-context compression.
- Supermemory local is the target cross-provider long-term memory backend, but
  migration waits for an isolated acceptance fixture.
- Ruflo remains important for selected goals/workflows/intelligence/cost/
  observability/security capabilities, not provider auth or competing scheduling.
- Provider-native subscription/coding runtimes are preferred over gateways.
- Model routing starts with the smallest capable tier and escalates.
- Rust is the target machine/runtime core; TypeScript remains the UI/control
  policy layer; Python is transitional/optional tooling rather than the desired
  permanent launch dependency.

## Not finished yet

1. **Desktop packaging.** Current source serves a loopback web UI; it is not yet
   packaged as the final Tauri-style desktop application.
2. **Founder onboarding polish.** Read-only planning and explicit execution
   approval are wired, but the founder-friendly idea intake and visual plan
   explanation still need the next UX pass.
3. **Beads migration.** Current UI/API task routes still use ClawTeam. Beads has
   passed its external-state bakeoff but is not yet wired into Company HQ.
4. **Provider-neutral runtime adapters.** Live execution is still Codex-only.
   Claude/Kimi/GLM/Grok/etc. require separate verified adapters and authorized
   account/quota acceptance.
5. **Real worker lifecycle and messaging.** Child IDs, queued/delivered/
   acknowledged states, wake behavior and cross-team messages are not yet
   synchronized end to end.
6. **Durable execution replay.** Native thread binding exists, but bounded event
   history/replay across Company HQ restart is incomplete.
7. **Budget scope beyond the local gate.** Company HQ now enforces a
   per-workspace reported-token action gate for start/send/execute/approval
   boundaries. Account-wide quota, billed spend, guaranteed mid-turn hard stops,
   child aggregation and provider-neutral escalation budgets remain separate
   work.
8. **RTK integration.** The bakeoff passed, but production command interception
   and raw-evidence recall are not yet wired into the runtime.
9. **Graphify stage-two integration.** Measured and selected, not yet wrapped by
   the Company HQ context builder.
10. **Supermemory local acceptance/migration.** Selected as target, but no
    provider/account memory is moved until isolation, recall and correctness
    tests pass.
11. **Rust runtime sidecar.** Architecture is decided; implementation has not
    begun.
12. **End-to-end daily-ready acceptance.** A full idea -> plan -> dependency DAG
    -> parallel isolated execution -> tests -> conditional independent review ->
    merge proposal has not yet passed as one bounded scenario.

## Meaning of "ready"

Do not call Company HQ daily-ready merely because each subsystem starts.

Daily-ready requires:
- one-command desktop launch;
- provider/account health visible before execution;
- plan/execute separation;
- task DAG and worker ownership visible;
- crash/restart recovery;
- budget/escalation enforcement beyond the current local reported-token action gate;
- compact context/evidence with raw recall;
- deterministic checks;
- conditional cross-model review;
- no product/account pollution;
- one bounded end-to-end acceptance pass.
