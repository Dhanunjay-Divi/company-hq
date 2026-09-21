# UI/UX direction from reviewed agent-team repositories

Updated 2026-09-21.

Company HQ should feel like a simple project chat first, then reveal team and evidence surfaces only when useful. The user should not need to understand Ruflo, ClawTeam, code graphs, model routing or task stores before starting.

## What the reviewed repos teach us

The 40-repo Claude catalog is mostly implementation method, memory, cost and tool infrastructure: 8 harnesses, 8 skills, 7 memory candidates, 10 tools and 7 cost candidates. The useful product lesson is not to expose all of that as top-level UI. Keep those systems behind one conversation and one project workspace.

The named team repos are also better as selected ingredients than as separate apps:

| Source | UX lesson for Company HQ |
| --- | --- |
| Codex / Claude-style chats | Start with one chat composer, a project list and simple status. Do not open with a graph, logs or empty counters. |
| OpenHands Agent Canvas | Keep chat central, and put files/browser/terminal/planner/task list in a workspace side panel when work is active. |
| Zed / Continue | Make plan/agent mode and permissions visible, but keep the everyday action as a normal chat. |
| Agent Teams AI | Use the graph after a team exists; it is a visibility surface, not the first screen. |
| ClawTeam | Use board/inbox state for task truth, but do not make the user operate a task database before explaining the goal. |
| Ruflo | Use memory and coordination behind the scenes; show only project decisions and handoff results. |
| Codebase Memory / Graft / Graphify | Use code structure to reduce repeated reading; show “used code context” as evidence, not as the primary UI. |
| ECC / Superpowers | Use concise planning, verification and review flows. Do not import broad hooks or mandatory workflows into the user experience. |
| gstack | Pull product/design/browser QA thinking into plans and acceptance checks. Keep marketing/growth as deliverables when the goal needs them. |
| Vibe Kanban / Beads direction | Show lifecycle and dependencies when work has tasks. Avoid a second competing task truth. |
| RTK / Headroom cost candidates | Show compact usage and evidence controls. Do not make compression settings part of the first-run flow. |

## Current product shape

1. **Left rail:** project chats and secondary views.
2. **Center:** chat-first start screen and supervisor conversation flow.
3. **Right/evidence dock:** opens only after there is a project, runtime event, approval or useful evidence.
4. **Specialized views:** team graph, work board, stack decisions, shared memory and system status stay one click away.
5. **Native app:** first Tauri shell starts or reuses the guarded local backend and opens Company HQ in a native window. The final signed app still needs packaging work.

## UX rules going forward

- First screen asks “What do you want the team to build?”
- Creating a project chat drafts a safe read-only planning message, but does not auto-spend tokens.
- Graphs and boards appear after they help explain active work.
- Right dock is for evidence and context, not an empty panel.
- The app should say what is real: started thread, pending approval, token reports, task status and verified output.
- If a feature comes from a repo in the catalog, it must be adopted behind the Company HQ contract: one authority, scoped state, tested behavior and clear user value.
