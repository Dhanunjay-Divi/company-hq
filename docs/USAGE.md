# Using Company HQ

Open **Company HQ.app** from Applications. You do not need a terminal for the installed app.

1. Click **New chat** and describe the result you want. No folder or chat name is required.
2. **Automatic** chooses the reviewed flagship supervisor, currently Astra. It delegates useful independent work to smaller capable agents. Small requests can stay with one agent.
3. **Work automatically** permits ordinary work within the native workspace policy. Choose **Plan first** for a read-only plan, or explicitly choose **Full access** for a trusted chat. Native provider and operating-system rules still apply.
4. Use **Add project → Choose folder** for existing files. Upload, paste or drop PNG/JPEG/WebP images into the composer. Each message supports four images up to 6 MiB each. Attachment drafts must be selected again after reload.
5. Follow the conversation. **Office** shows recorded assignments and observed native workers; **Tasks** shows dependencies/progress; **Files** opens the project explorer/editor and command runner; **Activity** shows native events and the local allowance.

For a project with independent work, open **Office → Start a teammate**. Give the
lead or specialist a focused assignment and choose a connected model. HQ creates
a separate project chat under the current chat, starts that provider session,
and shows its own conversation and live status. Use the sidebar to move between
the coordinator and teammate chats. The parent link and assignment are durable;
they do not by themselves make different providers exchange messages or review
each other's code. Ask the overall supervisor to read the teammate's result and
coordinate integration before treating the project as complete.

The supervisor owns the outcome and review. A lead coordinates a useful discipline. A worker completes a bounded assignment. HQ does not create a hundred idle agents or load every specialist prompt. Relevant guidance from the installed role library is used on demand.

## How agents share context and stay on track

Agents share the project's task board, saved Ruflo decisions and explicit messages. They do not automatically share every conversation or an unlimited common memory. The supervisor passes each worker a focused brief, file ownership, acceptance checks and relevant decisions; workers report evidence back. Other projects and provider credentials stay separate. A queued inbox note is not proof that an agent read it.

Use **Office** to inspect observed workers, send direction or stop one. The supervisor reviews the result against the requested goal and tests before calling it complete. Cached or missing runtime status is shown as stale or unknown. **Work automatically** uses the native workspace policy; **Full access** deliberately gives that chat wider access. No orchestration tool can guarantee that an agent never makes a mistake, and delayed token reports can overshoot a local allowance. Narrow assignments, native permissions, reviewable changes and stop controls are the practical protections.

## Connections and models

Open **Settings**. Codex uses its existing authorized sign-in. For Claude, select **Claude → Begin sign-in**, finish the official login, then **Check status**. **Choose model → Claude → Check connection & models** lists what the native runtime reports. Model selection stays fixed for a bound chat; start a new chat to change providers.

The Claude adapter exists, but this machine is signed out and a real Claude model turn has not passed acceptance. Kimi and Z.ai/GLM have native adapters; GLM real replies, tools and shared MCP were observed, while Kimi's current account is blocked by a server coding-entitlement 403. DeepSeek has a fixture-tested HQ API-key adapter but no live key. Grok, Cursor and Ollama remain detection-only. HQ does not inject provider models into Codex's own picker or silently change the billing route.

**Custom API** connects an explicitly entered OpenAI-compatible base URL and
model. Enter the endpoint in Settings, verify its model catalog, and use **Test
one response** when listing is unavailable or you want a generation check.
Its key is kept only for this app process and must be entered again after a
restart. This route handles text only; it has no project editing, browser
control, images, native worker tools, or chat resume after restart. HQ will not
automatically hand off a coding session to it. For an SSH-tunneled local model,
start your tunnel first, then use its loopback HTTP URL.

**Provider tasks** loads read-only Codex or Claude Code metadata. Selecting a summary does not resume or import the task. Claude filters search results on the currently loaded page; it does not expose an archive filter here. Other providers are not yet browsable.

## Permissions and computer use

**Full access** is an explicit per-chat native file/network execution mode. It does not grant macOS Accessibility, Screen Recording, browser-extension access, or another provider's account permissions. In Codex, enable the Computer Use plugin and configure its allowed browsers/apps; use HQ's **Settings → Computer access** guide for the macOS settings links. Grant the desired OS permissions yourself.

Chrome browser interaction through HQ's Codex runtime has been verified. The embedded Codex browser was unavailable to that standalone runtime; arbitrary native desktop actions remain unverified. Claude's own computer-use tools need their native configuration and separate acceptance.

**Skills & tools** inspects what the connected runtime exposes. Supported MCP OAuth connections and Codex skill enable/disable controls are available. This is not every provider's plugin marketplace. Local voice is offered only when on-device recognition is supported by the browser; otherwise the mic clearly reports unavailable.

## Tasks, files and evidence

Ask the supervisor to make a plan with deliverables, owners, dependencies and acceptance checks. New Codex chats have HQ client tools for the canonical Beads board. Old native chats created before these tools were added may require a new chat. Structured plan import is an optional advanced control, not required to use HQ.

A dependency blocks a task until its prerequisite is done. Recorded “done” alone does not prove that tests passed. Ask for test output and changed files. **Files** can inspect project files; editing requires execution mode and rejects conflicting external edits. **Terminal** uses Codex's native sandboxed command execution. With Claude, ask it in chat to use its native tools instead.

The native worker panel can send direction or stop observed workers after connection. A submitted direction means the provider accepted it; the worker's response establishes progress. After a restart, cached hierarchy is marked stale until reconciled. Stale permission handles must be reissued by the provider rather than auto-approved.

## Usage and frugality

Settings shows **remaining account percentage and reset times** only for windows the provider reports. A missing 5-hour or weekly window stays unknown. Account windows overlap and cannot be added together. Individual worker token reports are not individual subscription quotas.

Activity's **chat allowance** is a separate local reported-token threshold. It can block subsequent actions and request a best-effort interrupt; delayed native reports can exceed it. It is not a guaranteed billing cap. Earlier HQ build runs exceeded their budgets, so cost savings are not claimed. A team is useful when work can be separated and reviewed; a small request should usually stay with one agent.

## Data and recovery

Private app data defaults to `~/.local/state/company-hq` (or the configured external state root):

- `clawteam/managed-workspaces/`: working folders for folderless chats.
- `clawteam/company-profiles/`: labels and project bindings.
- `clawteam/drafts/`: durable unsent text, independent of the browser port.
- `clawteam/runtime/transcripts/`: private SQLite user/final-message history with paging.
- `clawteam/runtime/events/`: bounded recent event replay; replay does not imply a running worker.
- `clawteam/runtime/bindings/` and provider bindings: native conversation references.
- `clawteam/runtime/budgets/`: local usage policies and counters.
- `clawteam/beads/`: canonical task stores and migration backups.

Provider-native storage and sign-in remain with their provider. HQ does not copy credentials or attached project files into its app bundle. Keep private app data backed up if you need durable recovery across machine loss.

## Source development and troubleshooting

For source use, from the repository root:

```sh
python3 scripts/hq.py bootstrap       # set up and start; open the printed URL
python3 scripts/hq.py status          # inspect the source-server status
python3 scripts/hq.py stop            # wait for that source server to stop
python3 scripts/hq.py check           # deterministic model-free validation
```

`bootstrap --demo` opens a synthetic board without model execution. To build the standalone macOS app, use `python3 scripts/build_desktop.py --dmg`. See [desktop packaging](DESKTOP.md).

Run one backend per state root. Stop the source server before opening the installed desktop app. Quit the desktop app before starting the source server. If a local update invalidates a loaded view, use **Reload Company HQ**; saved conversations and text drafts remain in app data.

See [current status](STATUS.md) and [release acceptance](RELEASE-ACCEPTANCE.md) for verified behavior and remaining limits.

## Office and supervised HQ work

You can give your goal to the outer Codex supervisor, which dispatches a bounded task through HQ and reviews the actual diff, tests and coordination. The HQ conversation records its supervisor and workers; external Codex work is not silently presented as an HQ agent. There is no need to start a second conversation yourself for each step.

**Office** shows desks with actual native status and recorded roles. Select a desk or a roster entry for its role/model/assignment and **Give direction**. **Team map** is the existing Agent Teams AI graph of the same workspace. **Preview example** is explicitly illustrative; it makes no model calls and creates no tasks. Pause motion at any time; reduced-motion preferences freeze animations.

Local HQ token ceilings are disabled by default at the user's request. Usage remains reported; provider account limits are unchanged. Existing chats on this machine were switched to tracking only. An optional cap can be reenabled from Activity. Automatic quota continuation uses the stable Astra supervisor and explicitly enrolled GLM fallback only after a safe checkpoint; fixture coverage passes, but forced live-quota handoff remains unverified.

Ponytail's review skill and UI/UX Pro Max are installed as on-demand guidance, with pinned source/license copies under `skills/`. Use the former for unnecessary-complexity review and the latter for focused design/accessibility checks. No lifecycle hooks or additional orchestration service are needed.

## New connection and chat controls

Open Settings → Kimi Code or Z.ai → Check connection. The official CLI owns sign-in; a desktop app login may be separate. Once native sign-in and model discovery succeed, open New chat → Choose model → that provider. The catalog refreshes on opening its tab. Provider/model choice stays bound to that chat. New runtime versions are reviewed before activation; model discovery is not silent code installation.

The chat's ellipsis menu exports Markdown or JSON, reveals its bound project folder, or moves it to Trash. Select a trashed chat or its Restore action to bring it back. Exports are private files under the app state `clawteam/exports`, revealed in Finder on macOS. Project files and native provider histories are never deleted by Trash. Stop active work before trashing its chat.

GLM uses ZCode's native permissions, tools, and project-scoped Ruflo/Codebase Memory MCP servers. The shared context MCP source-probes the exact team/project and exposes the canonical board read-only across providers; Codex tools perform mutations. A reported model is not proof of coding entitlement. Kimi's current account needs activation before a model-backed task can pass. Five-hour/weekly account limits are shown only where the provider reports them; GLM session tokens are not a subscription percentage. Browser/desktop access still requires the relevant provider host tools and macOS permissions. Local voice offers supported setup alternatives; no real microphone transcription pass is claimed.
