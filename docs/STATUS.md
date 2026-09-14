# Verified baseline and limitations

Baseline source captured 2026-09-14 UTC. Historical verification documents are evidence from specific earlier iterations; this file is the current handoff summary.

## Working on the original Mac

- Actual Agent Teams AI canvas/React graph, avatars, hierarchy and click-through member/task details; custom responsive Company HQ shell and focus view.
- ClawTeam task create/update, owners and real file inboxes; loopback Host/Origin protections and private state directory.
- Project-scoped Ruflo note save/retrieve; codebase-memory MCP guard installed separately for structural queries.
- Native Codex app-server initialize/start/resume/steer/stop/approval bridge, preserving the existing account environment and bound project.
- Reviewed model catalog supplied to UI; kickoff/discovery utilities and update review procedure.
- Existing UI acceptance: isolated workspace, one Luna response through Start working, task moved to Done, Ruflo note round trip. Prior combined suite: 16 passing HTTP/bridge tests. This is evidence of these flows, not full autonomous-company validation.

## Not finished

1. **Portable setup.** Source was built around an existing Mac installation. Hard-coded toolkit/account-user paths remain in multiple wrappers, API adapters, sandbox profiles and docs. Fresh-clone startup must be made isolated and configurable before being called portable. Frontend production builds and pure tests are independently reproducible.
2. **Automatic worker visibility.** Live supervisor state is mapped; other nodes reflect registered metadata. Full native child lifecycle, cross-team communication and inbox wake/delivery acknowledgements are not synchronized end to end.
3. **Durable execution feed.** Native bindings resume a thread, but in-memory event history disappears after server restart. Bounded durable replay and retention are needed.
4. **Economy controls.** Reported token counts exist. No enforced project budget, comprehensive child usage aggregation, monetary bill or proven before/after savings exists. A tiny live acceptance reply still had 16,950 input tokens, of which 11,008 were cached, plus 21 output tokens. Short prompts do not imply low context overhead.
5. **Onboarding and UX.** User still does not clearly understand “talk to the supervisor, then follow the work.” Narrow board columns require horizontal scrolling, empty states can look inactive, and the graph needs stronger readable layout and clearer active/recorded states. Build a guided first-run example and test comprehension.
6. **Full company execution.** Research/product/design/engineering/QA/marketing/operations is the intended operating model; a complete idea-to-launch campaign has not been exercised. Do not create fake departments just to fill the graph.
7. **Provider independence.** Current execution is native Codex. Other vendors' subscriptions, CLIs, quotas and compatibility are not established by the model catalog.
8. **Automatic updates.** Metadata checks and a reviewed maintenance process exist in the original environment. No repository CI workflow or scheduler here installs updates automatically. The original local recurring automation is not transferred by this source snapshot.
9. **Separate Agent Teams AI app.** Its full opaque runtime remains disabled because of account-home/auth handling. Reusing its graph does not enable or endorse that runtime.

No production deployment or cross-platform runtime acceptance is claimed. Live task/message state and native receipts are intentionally not in this repository.

Additional portability findings from source inventory: the supervisor role template is preserved but the earlier configuration script installs only three other roles; Graft's arm64 Kotlin binding needed a manual build; generated Codex schemas are version-specific. These are implementation tasks, not finished installation features.
