# Connections, images and access acceptance

Verified 2026-09-21. Operating guidance: [agent-toolkit](../skills/agent-toolkit/SKILL.md).

## Delivered behavior

- New chats default to **Work automatically** (native workspace write). **Plan first** preserves read-only planning and explicit execution approval. **Full access** is an explicit composer choice mapped to native `danger-full-access` / `dangerFullAccess` with approval policy `never`; native account/admin restrictions still apply. The chosen default is remembered on this device. Existing thread bindings retain their access mode on resume. An idle execution chat can switch workspace/full access; a running chat must first finish or stop. No global Codex configuration changes.
- Upload, paste or drop up to four PNG/JPEG/WebP images (6 MiB each). Previews are removable; sent files persist privately per chat. Native inputs use server-resolved localImage paths, never client-supplied paths. Legacy attachment files remain readable. Per-chat storage caps are 100 files / 100 MiB; aggregate retention/cleanup is still a gap.
- Add project offers the macOS native folder chooser and a manual path fallback. Cancel leaves the draft intact. Dialogs no longer reuse the budget amount as the next chat name.
- Connections distinguishes installed desktop apps, CLI availability and executable runtime adapters. Codex has native account check/sign-in, reviewed models and reported quota windows. Other provider apps can be opened; HQ execution adapters are still absent.
- Remaining account percentages and reset times are separate from the local chat allowance and individual worker usage. Missing 5-hour/weekly windows and missing worker attribution remain **Not reported**, never assumed zero.
- Skills & tools shows the connected runtime's reported MCP tools, apps and skills. Browser availability counts only connected tool sources. 279 pinned specialist reference files and strategy playbooks are vendored with MIT license and SHA-256 manifest, loaded on demand; they are not 279 running agents.
- Repeated supervisor bylines are grouped. Settings uses expandable tool activity instead of exposing installation paths by default. Loopback URLs are reused after restart when the port is free.

## Evidence

`python3 scripts/hq.py check` passed: 23 root, 28 supporting, and 89 integration tests. Source-artifact and portability checks passed. The integration suite covers full-access persistence/downgrade, default read-only API compatibility, per-chat boundaries, token gates, provider-auth races and credential redaction, image validation/symlinks/legacy files, native picker behavior and loopback lifecycle.

`npm run build --prefix company-hq` passed. The synthetic browser suite passed with no page errors. It checks remaining-window percentages, absent windows, overspent allowance, provider dialogs, folder cancel/select, image preview/reload/byte preservation, automatic workspace native approvals, explicit plan-first behavior, Full access native transport parameters, managed workspace isolation and desktop/narrow layouts. Synthetic screenshots and result are under `/tmp/company-hq-connections-evidence` on the verification machine; they contain fixture data.

### Real HQ runs (not synthetic)

1. Provider-detection run exposed a real failure: workers spawned during planning kept read-only access after the supervisor moved to execution. It produced no implementation. Reported gross native tokens: **1,257,345**, including **1,200,512 cached input**. The outer bounded worker supplied/reviewed the detection implementation. Supervisor guidance now defers implementation workers until execution, using fresh compact task packets when needed. This is not evidence of cost savings or automatic permission propagation.
2. HQ's Astra supervisor delegated the native folder-picker implementation to one Terra worker in an isolated checkout. It produced the two owned source/test files and passed 11 focused tests. The supervisor reviewed them. Git commit hit the worktree metadata permission boundary; no claim of a successful native commit. The outer reviewer integrated the files. Reported gross native tokens: **407,533**, including **333,824 cached input**. This overhead is substantial for this scope.
3. A separate HQ image turn received a synthetic red PNG through the attachment API and native localImage input and replied **Red.** Reported gross native tokens: **19,184**. No product files or tools were requested.
4. Native Codex account verification returned signed-in state and a weekly window at the observed check: **59% used / 41% remaining**. It did not return a 5-hour window. These are historical observations; the UI refreshes native reports.
5. Actual read-only runtime inventory returned 9 MCP servers, 6 connected, including cua_repl, Ruflo and codebase_memory, plus 10 apps and 55 skills. This proves exposure, not universal successful execution. A separate product's MCP failed and desktop-only servers were disabled; HQ reports those statuses rather than claiming parity.

## Limits and failures retained

Native folder-dialog interaction could not be completed by the available UI automation surface; that attempt timed out. Mocked chooser success/cancellation and unit behavior pass, but manual macOS selection is still a verification gate. OAuth completion was fixture-tested; no account was signed out to force a live re-login. Full access was verified through the native transport fixture, not used to broaden permissions for a live test.

Two live backend exits were observed earlier without a traceback; cause remains unconfirmed. Explicit restart, port reuse and occupied-port fallback now pass lifecycle tests. Pending native approval recovery remains incomplete; no reliability claim is based solely on that restart test.

Other-provider execution, a final signed standalone installer, plugin installation/management, voice, an integrated editor/terminal, complete nested worker messaging/recovery and end-to-end parity with Codex/Claude remain open. The actual Agent Teams AI graph package is reused; its complete runtime is not adopted. Graft is optional/off the default path. Python remains the present runtime, with a source-checkout Tauri shell.
