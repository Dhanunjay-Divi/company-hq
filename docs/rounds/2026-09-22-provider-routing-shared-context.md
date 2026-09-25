# 2026-09-22 — Providers, routing, shared context and usability

## Request and ownership

Complete Company HQ across projects, use HQ for real implementation, connect usable providers, keep one shared project context and make usage and access understandable. The user keeps the outer Codex reviewer as delivery lead. Product repositories were not edited.

HQ's Terra worker implemented the four DeepSeek connection/runtime/test modules, then addressed a concrete review packet. The outer reviewer wired the API/UI/shared tools and ran combined verification. Bounded specialist agents handled routing safety, speech setup, shared context and ZCode protocol review. This is actual HQ-backed implementation, not a simulated roster.

## Observations and corrections

- Real GLM work authored Kimi/ZCode adapter tests. That run was stopped after overlapping runtime changes caused repeated investigation; it did not produce a native final success reply. The reviewer reconciled the tests and code.
- ZCode updated during work. The hash check blocked execution as intended. Review found the new app-server omitted standalone credential context; a version-pinned, uniquely matched in-memory adaptation restored two eligible models. No installed provider code or account file was changed.
- DeepSeek review caught decimal-string balances being dropped, shallow catalog copies, incomplete credential redaction, and model/credential binding risks. HQ corrected these with fixtures. No live DeepSeek request can be claimed until the user connects an API key and a bounded task succeeds.
- Automatic quota handoffs now require native terminal state, complete verified child inventory, no approvals/tools in flight and durable transition records. Stale/unknown worker states block handoff. Fresh provider allowance is required before a depleted account becomes eligible again.
- Settings now separate account allowance from optional local model ceilings, retain a stable supervisor, and hide unreported allowance windows. No local ceiling is requested at present.
- Shared context exposes the same skill files and canonical board to supported provider sessions; no full specialist library is injected into every prompt.
- Voice setup offers supported local language installation or macOS Dictation guidance. No cloud speech fallback is silently enabled.
- Chat actions include private file export, Finder reveal and recoverable Trash/Restore. Project files are not deleted by chat removal.

## Evidence and limits

Focused provider/routing/context verification passed during review. An initial combined run failed an outdated attachment test fixture after the routing hook was added; its stub was updated without weakening the attachment boundary. Final combined and packaged results are recorded in the release acceptance record after completion.

The DeepSeek HQ build plus review returned 1,260,585 reported native tokens, mostly repeated/cached input. This is not billed cost, account quota, or a demonstrated saving. Cost-efficiency acceptance remains open; do not advertise multi-agent savings from this run.

Kimi native login/catalog worked, but the server previously refused coding execution for missing entitlement. Claude needs an authenticated live turn; its desktop login is not sufficient evidence. DeepSeek needs API access. Unsupported providers and missing account windows are not invented. Browser testing does not prove native desktop control or microphone recognition.

## Operating decisions

Use [the shared working model](../SHARED-WORKING-MODEL.md) for leadership, skill reuse, round logs, native credential ownership and update review. Logs contain implementation evidence, not passwords, API keys, real user conversations or provider account databases. Continue using the canonical board rather than adding another orchestration scheduler.

## Final review corrections

Browser interaction exposed a routing Save wiring failure (missing HTTP dispatch and mismatched request envelope). The route and UI contract were repaired and a real HTTP round-trip/origin check added. The confirmed UI then saved Astra plus GLM fallback without a local ceiling. After the user's quality feedback, Flash was removed from automatic supervisor continuation; it remains a manually selectable worker model. Local ceilings moved under Advanced limits, and the default list shows selected continuation models instead of every available variant. Account allowance is not duplicated per model.

Independent review also corrected credential-generation cancellation, credential-loss resume rejection, isolated DeepSeek process settings/environment, stale quota reset eligibility, and image-bearing handoffs outside the compact transcript page. Ruflo launch binding now rejects another project on the first call; Codebase Memory uses a separate state directory per physical project and rejects cross-project paths. GLM now receives the context MCP on initialize and tool inventory. A source stdio probe read the exact bound project/board, listed nine registered skill collections and paged the Agency Agents guide. The normal GitHub CLI verified the existing private repository identity without copying credentials.

A disposable chat exported through the browser into a mode-0600 Markdown file; the interface reported Finder reveal. DeepSeek's connection form was inspected, and the user chose to continue using Codex and GLM rather than connect a paid key now.

The user subsequently requested focused lead conversations with agreed decisions reported to the main supervisor. GLM is implementing the UI through HQ, while a bounded backend assignment adds descendant-verified native conversation reads and explicit supervisor reports. This is additional work and must be verified before claiming completion.

## Live HQ build demonstration and follow-up fixes

The GLM-5.3 assignment implemented the focused worker-conversation UI through HQ, then resumed after the development server stopped. The UI now labels this explicitly assigned session “Delegated builder” under the outer Codex reviewer; it does not fabricate a native cross-provider parent. Full access was explicitly selected for this chat. GLM reviewed its four files and ran a passing production frontend build. Root also ran 32 focused provider tests and the full check (23 root, 34 support, 284 integration tests, plus JavaScript/source/portability checks) before the final small corrections below.

Real checks found further integration defects: ZCode global MCP status was being mistaken for session MCP status; its user-triggered inventory now connects/revalidates workspace definitions and says so. Ruflo and shared context connected with 14 and 3 tools. Codebase Memory failed to create a Unix socket because the per-project state path exceeded macOS socket limits; its guard now uses a short private project/state-scoped runtime directory, validates ownership/mode, and preserves separate graph data. Actual stdio initialization then succeeded; four scope fixtures passed.

The native ZCode projection retains a completed turn ID, so HQ incorrectly kept showing “Working” after the actual build finished. Completion now uses the native runtime’s activeTurnId when provided, with new assistant evidence and no active tools or pending permissions. Eleven adapter fixtures passed; live completion verification follows. One initial regression assertion raced the asynchronous completion event; it was corrected to await the event, not just the state assignment. A mistaken test class name and a startup connection-refused attempt were harness errors, not product passes.

The user requested stopping Codex at 14% remaining. The existing Codex usage guard was updated from its paused 20% policy to active five-minute checks at 14% in either reported account window; it leaves GLM work alone and never redeems resets or spends credits. Last checked: 15% weekly remaining, five-hour window unreported. This is best effort, not a hard account billing control.

Live verification after the fixes: the GLM completion check returned `idle`, with complete native child inventory and zero active children. The workspace MCP check reported Ruflo connected (14 tools), Codebase Memory connected (12 tools), and contextMCP connected (3 tools). The visible app showed the actual GLM builder reply and Full access selected. These are workspace connectivity and a real GLM turn/build observations; cross-provider automatic hierarchy and live child-subchat delivery are still separate acceptance gates.
