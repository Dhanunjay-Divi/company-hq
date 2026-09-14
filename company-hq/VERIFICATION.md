# Company HQ verification — 2026-09-13

Uses the shared agent-toolkit operating skill at /Users/uno/.codex/skills/agent-toolkit/SKILL.md.

- Actual Agent Teams AI graph package and six upstream avatar assets reused; AGPL license, attribution and corresponding source available through /api/source. Camera fit has one documented local cap; adapter supplies actual ClawTeam records.
- Production frontend build passed. Browser tested at desktop 1280x800 and narrow 433px: map, focus map, node inspector with owned tasks and real conversation, new workspace, note form, task creation/status. Tooltip provider and registered-member opacity were corrected after initial browser failures; these were not counted as passes.
- Real Ruflo note saved and read through the dashboard, scoped to the shared toolkit. Structured memory rendered as readable text.
- New isolated acceptance workspace connected through UI; a Luna goal was submitted through Start working, its actual answer streamed back, state returned to Ready. Actual native receipt is ui-execution-receipt.json (excluded from source archive). No tools or product writes were requested in that turn. Reported usage: 16,950 input tokens, 11,008 cached input, 21 output; no monetary estimate is claimed. Native setup has context overhead even for short requests.
- Task created with overall-head owner through UI and changed to Done; persisted board showed 1/1 complete.
- Combined HTTP/native-bridge suite: 16 tests pass with ResourceWarning treated as error. Prior isolated native bridge smoke and handshake also passed. No duplicate smoke was run.
- Same loopback URL retained: http://127.0.0.1:50188/. Existing host/origin checks, CSP, project binding, native approval controls and existing account context retained. SIGTERM closes native child processes.
- 1,888 Pinky baseline paths checked: 1,887 hashes unchanged; mistakes.md has a separate 50-line addition observed during final verification. This task did not edit it or revert it. All implementation/source/runtime state is external to product repositories.

## Practical limits

The graph displays registered team structure and ClawTeam assignments/messages. Only the native supervisor has live runtime state mapped; workers are explicitly marked with unknown runtime rather than fabricated activity. Worker inbox messages do not auto-wake agents. Native execution events are bounded live-session history and reset on server restart; the native thread binding is durable for resume. Full Agent Teams AI runtime remains separately disabled. Other providers require separately available and reviewed runtime/account access. Approval behavior is covered by bridge tests; no real privileged approval was requested during the UI acceptance test. No production deploy or cross-platform runtime test occurred.
