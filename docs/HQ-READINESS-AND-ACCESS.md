# HQ readiness and access

Historical checkpoint, 2026-09-21. Superseded for current capability status by [STATUS](STATUS.md) and [release acceptance](RELEASE-ACCEPTANCE.md).

Reviewed 2026-09-21. Company HQ is a usable Codex-backed prototype, not a replacement for every native provider application.

## What the user can do

1. Start Company HQ with `python3 scripts/hq.py start` from the checkout, then open the printed address. Start a chat without selecting a project; attach a project only when its files are needed.
2. Use **Work automatically** for ordinary workspace work, **Full access** for an explicitly trusted chat's machine/network work, or **Plan first** for read-only planning. These settings do not grant browser, desktop, or account access.
3. Open **Provider tasks → Load tasks** to browse native Codex metadata. Search, archived tasks and agent-task filters use the supported native API. Opening a summary does not resume, import, or edit the task.
4. Open **Settings** for provider sign-in/status, reported account allowance, and computer-access setup. Runtime **Skills & tools** reports what the connected chat actually exposes; an inventory entry is not an executed-tool test.
5. Answer supported native questions, permission requests and bounded MCP forms in the conversation. Decline remains available at an exhausted chat allowance. Unsupported native requests remain denied with a diagnostic.

## Comparison with the native applications

| Capability | Company HQ today | Remaining work |
| --- | --- | --- |
| Project-optional chat, Markdown, images | Implemented; native image acceptance recorded separately | Complete transcript/draft recovery beyond bounded replay |
| Models | Native Codex catalog currently reports Astra, Sol, Terra, Luna and GPT 5.5; all five are reviewed and listed | Other providers need verified execution/catalog adapters; installation alone is insufficient |
| Existing tasks | Codex metadata and selected summaries through `thread/list` and `thread/read` | Claude/Kimi/GLM/Grok/Cursor task browsing and cross-provider resume are unavailable |
| Useful team delegation | Native Codex supervisor and workers execute; HQ has produced source code for itself | Child lifecycle, nested permissions, cross-team delivery and restart reconciliation need further work |
| Skills, MCP and apps | Inventory from the connected native runtime; selected role guidance available on demand | Native plugin-management parity and unsupported request formats remain incomplete |
| Browser and desktop control | Live HQ → Chrome page read passed, including an explicit native browser-access confirmation; fixed macOS settings links provided | Codex embedded browser was unavailable in standalone HQ; native desktop app actions remain unverified |
| Allowance | Provider-reported account windows plus separate local chat allowance | No guaranteed billing cap or complete cross-provider/child accounting |
| Native desktop experience | Tauri source shell exists | Final packaged installer, integrated editor/terminal and voice are unfinished |

## Computer access

For Codex, enable **Plugins → Computer Use** (server and skill), then configure **Settings → Computer use**. macOS additionally requires Accessibility and Screen Recording for **Codex Computer Use**. HQ's buttons only open the relevant settings pane; the user grants permission there. Per-app requests can be allowed for the requested scope, including a saved app permission where the native runtime supports it. Permissions can be revoked in the native app or operating system.

Claude has its own Desktop computer-use settings and app-session approvals. That does not connect Claude's runtime to HQ. Never infer one application's permissions from another's installed state.

Primary references: [Codex Computer Use](https://learn.chatgpt.com/docs/computer-use), [Codex app-server](https://learn.chatgpt.com/docs/app-server), [Claude Computer Use](https://code.claude.com/docs/en/computer-use), [Claude sessions](https://code.claude.com/docs/en/sessions).

## HQ building HQ: observed result

The native run used an Astra supervisor and one Terra worker in an isolated checkout. The worker produced `native_tasks.py` and six fixture tests. The outer reviewer copied and reviewed that implementation, corrected the detail-summary response shape, and added API/UI integration and transport tests. This is useful HQ-produced work; it is not proof of an autonomous finished feature.

The run crossed its 200,000-token allowance while the supervisor waited for the worker. Stop was requested at 275,714 reported tokens; the final recorded total was 329,132. The native child eventually reported completed. These are gross native reported tokens, including reused context, not billed cost. The previous action gate did not stop an already-running turn. The efficiency acceptance **failed**; no savings claim is supported. The follow-up adds a best-effort interruption request at the reported ceiling, while retaining the distinction from a provider-side hard cap.

No Pinky files, provider credentials, original shared-toolkit installation or account routing were changed by this work. Runtime chats and local provider metadata remain private app state, outside the repository; no real task transcript is included in this evidence.

## Browser and interaction acceptance

- A bounded Luna run through HQ attempted the native in-app browser. It failed because that surface was unavailable. A diagnostic browser listing reported the Chrome extension; the two turns consumed 83,550 gross reported tokens. No shell/HTTP fallback was counted as browser success.
- A fresh Luna run opened HQ through native Chrome, observed “What are we making today?”, and closed its created tab. The real `cua_repl` access confirmation for HQ's loopback address was answered through the new native-response endpoint. Both browser calls completed. Reported usage arrived at 70,531 against a 50,000 allowance; the best-effort stop event was emitted, and the turn completed. This is browser capability evidence, not a token-efficiency pass or universal desktop-control parity.
- Model-free local browser acceptance exercised task loading and selected summaries, unsupported-provider messaging, a question, a turn-scoped simulated network grant, and a primitive tool form. The final fixture marker was observed. The first attempt failed because the fixture sent singular `question` instead of the protocol's `questions` array; the product correctly rejected it. The fixture was corrected and the complete sequence passed.
- Opening OS settings uses only fixed allowlisted links and was unit-tested with a mocked launcher. No OS security permission was granted by automation.

## Verification for this checkpoint

- 164 model-free Python tests passed: 23 root, 28 supporting, 113 integration (including 42 bridge tests).
- React/Vite production build, source archive and portability checks passed.
- Read-only live Codex metadata test returned seven matching tasks and a selected summary with no unexpected fields. Native model discovery returned the five models listed above, with no further catalog page.
- The Chrome acceptance was independently checked against the native task's tool results: two completed CUA calls, with the observed heading present in the first result.
- Local browser UI verification used isolated synthetic provider state. No real external task was resumed by the new task browser.
- Other-provider runtime execution, native desktop app actions, packaged installer and guaranteed cost reduction remain unverified/unimplemented as described above.
