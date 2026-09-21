# Chat-first acceptance checkpoint

Verified locally on 2026-09-21. This report separates deterministic tests, live observations, and unfinished product work. The reusable operating guidance is [agent-toolkit](../skills/agent-toolkit/SKILL.md); current source and user instructions take precedence.

## Product changes

- Start by typing, without choosing a folder. First send creates a private managed workspace outside product repositories.
- Central Markdown conversation, real recent chats, optional project attachment, clear model selection and secondary team/activity views.
- Dark neutral styling, consistent controls, CSS visual depth, mobile navigation and reduced-motion support. Heavy team views load on demand.
- Astra is the reviewed default supervisor. Native instructions prefer Terra/Sol leads when nested coordination is needed and Luna for bounded leaf tasks.
- Bounded private replay survives server restart; immediate completion/approval races and project-attachment races have regression coverage.

## Deterministic verification

Synthetic UI screenshots: [desktop chat](assets/chat-first/chat-home.png), [mobile chat](assets/chat-first/chat-home-narrow.png), [settings](assets/chat-first/settings.png).

`python3 scripts/hq.py check` passed 86 tests: 12 root, 28 evidence/frontend, 46 backend/integration, plus source bundle, portability and required capability checks. The frontend production build passed.

Browser acceptance uses the actual React UI and HTTP server with a synthetic JSONL provider, not real model outputs. It passed folderless first send, flagship selection, plan/execution/permission separation, fixture output, unchanged source files, cancellation, desktop/mobile layouts, reduced motion, saved-chat reload, server restart/resume, navigation during delayed creation, setup-check failure reporting, and retention during 600 streamed chunks. These are functional checks, not model-quality benchmarks.

Reviewer verified the previous crash-cursor reproduction: cursor 8 stays 8 offline, and resumed events begin at 9. A follow-up regression keeps the response within the configured cap when durable history fills it. Storage failures remain a best-effort recovery limitation.

## Actual model-backed checks through HQ

| Check | Observed result | Limits |
| --- | --- | --- |
| Small Luna requirements review | Completed through the HQ composer, with a real native reply and usage report | No UI inspection, tools, or project edits requested |
| Astra supervisor with Luna lead asked to delegate QA | Lead completed but reported no native collaboration tools; nested delegation failed | Preserved as a failed attempt, not rewritten as a pass |
| Astra supervisor with Terra lead and Luna QA | All three turns completed. A separate read-only review of only these native threads verified exact parent links and started/completed child activity | Thread metadata identifies configured/latest persisted models, not independent per-turn model telemetry; HQ currently surfaces the immediate child, not the whole nested tree |

The installed model metadata reports v2 collaboration for Astra/Sol/Terra and v1 for Luna. Combined with the bounded observation, this supports the current lead/leaf preference; it is not a universal claim about future models or versions. No global account or native configuration was changed to force delegation.

The respective root runtime token totals were 15,811, 77,549 and 96,060. These include reported cached input, do not aggregate all children, and are not billed prices or account quota. They do not prove that teams save tokens. Simple work should stay with one agent; quality/cost comparisons require matched tasks and complete accounting.

## Repository reuse and delivery boundary

The existing licensed Agent Teams AI graph remains in use. React Markdown 10.1.0 supplies reply formatting with raw HTML disabled; its MIT notice is retained. Ruflo and Codebase Memory remain the guarded memory/code tools. Other catalog repositories are not described as integrated merely because they were inventoried, reviewed or benchmarked.

The Company HQ source checkout and its own running backend were updated. Pinky and the separate shared toolkit were not deployed or changed. The GitHub repository was found public during verification and changed to private under the user's standing request; current visibility was verified. This does not establish whether earlier public contents were accessed.

## Still open

Full nested team graph/message synchronization, other-provider sign-in/adapters, desktop-hosted computer use and plugin parity, complete transcript and approval recovery, aggregate worker budgets, production Rust migration and a portable signed desktop package remain unfinished. The Tauri source wrapper exists; this checkpoint is not the final daily-ready whole-company product.

Official API reference: [native app-server items and thread reads](https://learn.chatgpt.com/docs/app-server). Local acceptance evidence is generated into the configured `HQ_EVIDENCE_DIR`; real conversations and account artifacts are not committed.
