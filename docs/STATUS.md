# Verified features and release boundaries

Updated 2026-09-25. This is a local development release for macOS Apple Silicon. The [release acceptance record](RELEASE-ACCEPTANCE.md) distinguishes automated checks, actual native runtime observations, and work that still requires a user's account or operating-system permission.

## Available in this release

- A Rust/Tauri desktop application with a frozen Python backend and React interface. The core app runs without launching a terminal or keeping the source checkout available. State stays outside the application bundle.
- Provider setup now distinguishes a desktop app from the coding runtime HQ can actually use. The connection sheet presents the official setup or sign-in step first and keeps adapter details and recent activity optional. A second backend using the same private state shows a recovery screen instead of crashing the desktop app.
- Separate linked teammate conversations under a project coordinator, each with its own provider session, assignment and observed status; cross-provider automatic delegation and reporting are not yet claimed.
- A text-only custom OpenAI-compatible endpoint adapter with explicit model verification and no automatic coding handoff. The supplied Qwen endpoint did not respond during local acceptance, so no live Qwen turn is claimed.
- Chat first, optional project attachment with a native folder chooser, Markdown replies, image attachments, persistent text drafts, and paged durable user/final-message history. Private state survives a changed loopback port. Attachment drafts must be selected again after reload.
- Codex's native app-server for actual model work, permissions, questions, account windows, skills/MCP inventory, and native collaboration. The reviewed flagship is the default supervisor; specialist work can use smaller models.
- A Claude Code adapter using the official stream/control protocol, native sign-in, provider-reported models, images, approvals and questions. The local CLI is installed; this machine is signed out. A real authenticated Claude turn is an outstanding account acceptance check.
- DeepSeek is implemented through the HQ Terra path with a fixture-tested API-key adapter using the official Claude-compatible transport. No live DeepSeek key or request is claimed.
- Recoverable chat Trash/Restore, full archived transcript export to private files, and Finder actions for bound folders. Exports never delete or modify project files.
- Separate Codex and Claude native task metadata browsing. Opening a summary does not resume/import another task. Claude's SDK filters the current metadata page; archive and global-search parity are not claimed.
- Canonical Beads tasks, dependency validation, blocked/readiness states, and resumable plan application. Legacy boards migrate on first mutation and remain backed up. Missing Beads after migration fails closed.
- An animated Office view with Munder Difflin procedural portraits, an original floor, actual status labels, clickable roles/assignments, reduced motion, and a no-model example preview. The Agent Teams AI graph remains available as Team map.
- Actual Codex descendant reconciliation, worker direction/steering and stop requests. The team graph joins observed workers with recorded board data. Stale workers and incomplete discovery are explicitly marked; a sent direction is not an acknowledgment.
- Project file tree, small UTF-8 editor with revision conflict detection, and a native Codex command runner that follows the chat's sandbox policy.
- Supervisor client tools for the canonical plan/tasks, native commands, and raw-evidence recall. These are attached to newly created Codex chats. Existing older native chats may need a new chat to gain these tools.
- RTK filtering of captured command output with complete bounded raw evidence and paging. Commands are executed once. Codebase Memory remains primary code intelligence; optional Graphify handles broad/cross-asset questions using an external output directory.
- Scoped Ruflo memory remains available through the reviewed adapter. The shared context MCP source-probes the exact team/project and exposes the canonical board read-only across supported providers; Codex HQ tools remain the mutation interface. The desktop uses the existing shared adapter if present; that optional tool still requires its Node/Python dependencies. A second unverified memory backend is not enabled by default.
- Per-chat automatic workspace access, Plan first, and explicit Full access. Provider, administrator and operating-system rules remain authoritative. Claude's normal permission mode is not an OS filesystem sandbox.
- Reported account allowance percentages and reset times, separate local chat budget percentages, individual worker usage when reported, and best-effort interruption after the local threshold is observed.
- Local-only voice input where the browser supports on-device speech recognition. Unsupported browsers clearly disable it; HQ does not silently send audio to another service.

## Boundaries users should know

Kimi Code (ACP) and Z.ai/GLM (pinned ZCode 0.16.9 protocol) have native runtime adapters and sign-in/model discovery. GLM account login, real replies, tool execution and shared MCP connection were observed. Kimi account login and catalog were observed, but live execution was refused with a server 403 because this account lacks coding entitlement; the user is activating it. DeepSeek has a fixture-tested HQ adapter but no live key. Grok, Cursor and Ollama remain detected providers without HQ execution adapters. Codex and Claude use distinct accounts and expose different capabilities; HQ cannot add Claude models to Codex's own picker.

Browser control through HQ's Codex runtime has a real Chrome acceptance record. Codex's embedded browser was unavailable to that standalone runtime. Native desktop computer-control actions remain unverified. The user enables native plugins and grants macOS Accessibility/Screen Recording; Full access does not replace those grants. HQ can inspect supported tools, connect supported OAuth MCP servers and change exposed skill enablement, but it is not the complete native plugin marketplace or every provider's IDE.

Pending provider approval handles cannot be fabricated after a process restart; HQ recovers the conversation and fails closed until the native runtime reissues the request. Complete cross-provider team messages, arbitrary cross-provider task resume, and exact child/account billing aggregation are not claimed.

The stable Astra supervisor uses an explicitly enrolled GLM fallback when policy permits. Automatic quota continuation now requires a safe stopped checkpoint, verified child inventory, no approvals/tools in flight and durable transition records; fixture checks pass, but no forced live-quota handoff has been observed. Local token ceilings are disabled by default. The token gate sees usage after the provider reports it and cannot guarantee a billing limit. **Cost-efficiency acceptance has not passed.** Creating more agents is not the default for a small task.

The macOS artifact is a local, unsigned/not-notarized development build. Public distribution needs Apple signing credentials. The source has been pushed to GitHub; the latest local development build is unsigned and not notarized. Windows/Linux desktop artifacts have not been built or tested. The Rust shell owns the window/backend lifecycle; the core Python services have not been rewritten in Rust without a measured reason.

## Reuse decisions

[Best stack](BEST-STACK.md), [upstream review](UPSTREAM-REVIEW.md), and the [40-repository inventory](repository-candidates.json) retain the candidate analysis. This release uses Agent Teams AI's licensed graph/avatar code, native provider execution, Beads task authority, RTK output reduction, Codebase Memory, and scoped Ruflo. Graphify is optional. Graft and a second scheduler are outside the default path. Supermemory migration and Headroom activation remain conditional on measured benefit and isolation checks. Repository availability alone is not evidence of compatibility or savings.

[Workflow](WORKFLOW.md), [provider runtimes](PROVIDER-RUNTIMES.md), [context pipeline](CONTEXT-PIPELINE.md) and [desktop packaging](DESKTOP.md) describe the implementation boundaries.
