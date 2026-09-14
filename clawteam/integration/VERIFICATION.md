# Verification

- Package: ClawTeam 0.3.0, installed as a wheel from the pinned local checkout
  into `/Users/uno/.local/share/agent-toolkit/clawteam/venv`.
- Attribution: upstream HKUDS ClawTeam source and MIT `LICENSE` remain in the
  pinned checkout; the local board HTML is a derivative of that shipped UI.
- Fixture scope: temporary directories named `clawteam-fixture-*`; fixture team,
  task, messages, and acknowledgement are labeled `Verification fixture`.
- Tested real upstream stores: team definition, task creation, inbox delivery,
  consuming receive/acknowledgement, persistent message event history, and board
  aggregation.
- Tested HTTP boundary: loopback URL, exact Host enforcement, same-origin POST,
  no wildcard CORS, CSP response, and disabled proxy.
- Tested execution boundary: `clawteam-meta spawn` returns exit status 64 and does
  not launch a worker.
- `team-ui` records an exact PID and URL, reuses a healthy board, and only stops
  a PID whose command line identifies this secure-board script.
- Production state is not populated by the test override.

## Live acceptance — 2026-09-13

The actual `toolkit-integration` team was registered with six current Codex
participants and six current assignments. The overall head sent a message from
the browser UI to `coordination-lead`; the recipient consumed it through
`clawteam-meta inbox receive` and replied through `clawteam-meta inbox send`.
Both messages rendered in the upstream-derived board and the recipient inbox
returned to zero pending. This verifies durable delivery and acknowledgement,
not automatic worker wakeup.

## Dashboard usability update — 2026-09-13

- Added validated per-team presentation metadata for actual reporting lines,
  readable roles, project goal and recorded model labels; no inferred agents.
- Real inbox test verifies a user-attributed message reaches a registered
  recipient and can be consumed. Invalid recipients and malformed payloads fail.
- New task requests validate team and owner and return `starts_agent: false`.
- Company profile checks reject reporting cycles and cross-team references.
- Three backend/lifecycle tests passed with ResourceWarning treated as error.
- One intermediate verification failed because the frontend file was temporarily
  absent during a replacement. Restored the existing page, requested atomic
  frontend replacement, and reran successfully. This was a local integration
  process failure, not a product-repository failure.

- Final browser acceptance: desktop 1440x900 hierarchy and actual narrow Codex
  panel checked; narrow cards remain readable with labeled navigation.
- Actual UI task creation produced task 90489b4a with Overall head ownership.
- Fixed-user UI message reached the lead, was consumed, and the real reply was
  visible in the inspector. The unsent draft retained its value and AX focus
  through repeated live updates, then was cleared without sending.
- Intermediate UI failures (tiny narrow graph and replaced textarea DOM) were
  reproduced and fixed before acceptance. Final page uses a vertical compact
  hierarchy and persistent composer elements.
- Final graph shows actual blocked task status and parent-first specialist order.
- Pinky: all 1888 baseline file hashes unchanged; Git working tree clean.

- A test-harness assertion initially treated the valid lowercase HTML doctype as
  a failure. Corrected it to accept HTML case-insensitivity and reran the suite.
- Final acceptance caught a stale graph preview: task/activity panels refreshed
  on SSE but the map did not. Added graph-signature change detection and a map
  update that preserves pan/zoom. Browser verified in-progress → completed
  disappeared from the map without reloading; blocked task stayed correctly labeled.
