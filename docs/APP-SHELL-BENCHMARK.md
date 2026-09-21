# App shell benchmark

Updated 2026-09-21.

Company HQ is moving toward a desktop IDE-style app, not another hidden chat wrapper. The benchmark is a founder-facing command center where the supervisor can discuss the goal, decompose work, assign specialists, show evidence, keep memory scoped to the project and protect budget before execution.

## Reviewed references

| Reference | Useful pattern | Company HQ decision |
| --- | --- | --- |
| Zed parallel agents and Agent Panel | Agent threads, terminal threads, persistent thread sidebar and visible parallel work. | Keep a persistent workspace shell with team graph, work board and supervisor evidence dock. |
| Continue Agent mode | Chat, plan and agent modes with permission-gated tool use. | Keep read-only planning separate from execution approval. |
| OpenHands Agent Canvas | Control surface for conversation, files, terminal, model selection and backend events. | Treat the evidence dock as the runtime control surface, not just a transcript. |
| Helmor | Local-first multi-agent workbench with isolated git workspaces, diffs, editor and terminals. | Prefer local-first, worktree-aware execution and visible worker ownership. |
| Tauri | Rust core with OS webviews and smaller native app footprint. | Target Tauri for the app package when the runtime sidecar starts. |
| Electron | Mature Chromium/Node process model and packaging ecosystem. | Keep as fallback if Monaco/editor integration or plugin compatibility matters more than size. |

## What landed in the current shell

- Desktop-style frame with a command bar and status bar so it feels like a local app.
- Workspace health, capability count and budget state are visible before model work starts.
- The run overview remains first because the founder should understand the next safe action.
- The supervisor console is now an evidence dock with approval/event/thread counters.
- The active workbench keeps existing controls for budget gates, memory, system status, decisions and task ownership.

## Next app-quality gates

1. Package the web shell as a local Tauri app with an explicit state directory and loopback binding checks.
2. Add a command palette for “start plan”, “set budget”, “open evidence”, “create team” and “review changes”.
3. Add worker/session lanes that distinguish assigned, started, delivered, acknowledged, blocked and verified states.
4. Add an editor/diff panel only after runtime writes are safely isolated in a project worktree.
5. Run an end-to-end idea-to-plan-to-worker-to-test-to-review acceptance scenario before calling it daily-ready.
