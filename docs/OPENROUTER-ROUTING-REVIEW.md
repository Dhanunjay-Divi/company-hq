# OpenRouter routing review

Date: 2026-09-22
Scope: read-only review for the current HQ native-provider routing wrapper.  No OpenRouter API key, paid routing, subscription transfer, install, or runtime configuration was authorized or changed.

## Evidence boundary

The official [documentation index](https://openrouter.ai/docs/llms.txt) currently has 459 listed lines. This review does not claim to have read every listed page. It sampled the pages that can affect routing correctness, tool safety, quota accounting, privacy, and operational evidence. OpenRouter pages are authoritative for OpenRouter behavior; HQ policy and native Codex/Claude/Kimi/ZCode subscription behavior remain local product contracts.

## Current HQ contract

The implementation already has a stable preferred supervisor, an ordered enrolled-model allowlist, optional per-model percentage ceilings, an optional global reported-token pool, account-level cooldowns tied to observed reset data, and same-team handoff only after a native quota error and native idle state. Handoff is blocked by active children, unresolved requests, or pending tools; task-board and artifact ownership stays with the project. The relevant local code is `clawteam/integration/routing_policy.py`, `routing_service.py`, and `provider_handoff.py`.

That contract should remain the source of truth for native subscriptions. OpenRouter cannot make a user’s Codex, Claude, Kimi, or ZCode subscription portable through an OpenRouter API call. No price or latency measurements are available here, so no model or provider ranking is asserted. External web/cloud tools are not automatic desktop control.

## Documentation areas reviewed

| Area | Sources | Decision for HQ |
| --- | --- | --- |
| Provider selection and provider preferences | [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching) | Defer provider-specific routing until an authorized OpenRouter account and measurements exist. Preserve explicit allowlists and fail-closed policy. Provider sticky routing is relevant only to an OpenRouter request path. |
| Model failover | [Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks) | Adopt the bounded idea, not a direct transplant: ordered fallback candidates are useful, but HQ must retain same-team, idle, pending-work, and artifact/task ownership gates. OpenRouter may retry rate limits, downtime, context errors, and moderation refusals; the final model determines price. |
| Automatic and latest resolution | [Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router), [Latest Model Resolution](https://openrouter.ai/docs/guides/routing/routers/latest-resolution) | Defer. Dynamic selection/latest slugs conflict with reproducible native supervisor policy unless an explicit allowlist, capability check, and audit record surround them. |
| Tool calling and discovery | [Client Tools](https://openrouter.ai/docs/guides/features/tool-calling), [Tool Search](https://openrouter.ai/docs/guides/features/server-tools/tool-search), [Server Tools](https://openrouter.ai/docs/guides/features/server-tools) | Defer server tools and tool discovery. Tool definitions, approval boundaries, and desktop-control authority must remain HQ-owned; a model discovering a tool is not authorization to invoke it. |
| Advisor/subagent and multi-model features | [Advisor](https://openrouter.ai/docs/guides/features/server-tools/advisor), [Subagent](https://openrouter.ai/docs/guides/features/server-tools/subagent), [Fusion](https://openrouter.ai/docs/guides/features/server-tools/fusion) | Defer. These create additional model calls and ownership/trace questions. They must not bypass active-child, pending-tool, quota, or approval gates. |
| Caching | [Response Caching](https://openrouter.ai/docs/guides/features/response-caching), [Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching) | Defer for customer/private prompts. Response caching is beta, API-key scoped, returns cached content verbatim, and has TTL/eviction semantics. Any future use needs explicit data-class policy and cache-hit accounting. |
| Reasoning and capability metadata | [Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens), [Models](https://openrouter.ai/docs/guides/overview/models), [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata) | Adopt metadata as an input to eligibility only after schema validation. Do not infer capability from model names; record requested and actually used model, provider, tool support, context, reasoning usage, and fallback outcome. |
| Limits, errors, retries | [Limits](https://openrouter.ai/docs/api_reference/limits), [Errors and Debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging), [Uptime Optimization](https://openrouter.ai/docs/guides/best-practices/uptime-optimization) | Adopt bounded, classified retry evidence. A transport/provider error is not automatically a native account quota reset. Preserve current account cooldown and reset-source rules; avoid retry storms and double-counting tokens. |
| Privacy and retention | [Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection), [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging), [Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr) | Defer routing private customer content through OpenRouter pending an approved data-processing and provider-retention decision. Never log raw prompts, completions, audio, captions, session codes, or credentials. |
| Budgets and guardrails | [Workspace Budgets](https://openrouter.ai/docs/guides/features/workspaces/workspace-budgets), [Guardrails](https://openrouter.ai/docs/guides/features/guardrails), [Service Tiers](https://openrouter.ai/docs/guides/features/service-tiers) | Treat provider budgets and allowlists as prerequisites for any future paid integration. HQ’s guarded local policy and continuation behavior remain authoritative; no OpenRouter budget is configured. |
| Observability | [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata), [Logs](https://openrouter.ai/docs/guides/features/logs), [Activity](https://openrouter.ai/docs/guides/features/activity), [Input/Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging) | Adopt non-content routing and usage evidence only. Keep prompt/completion logging disabled for sensitive flows; retain bounded IDs, provider/model, status, tokens, latency when supplied, fallback reason, and policy decision. |

## Concrete recommendations

1. **P1 — Keep OpenRouter behind an explicit, disabled integration boundary.** If enabled later, require a project/team opt-in, an exact model/provider allowlist, capability metadata validation, an approved spend limit, and a redacted audit record. Do not map native subscription credentials or claim subscription coverage through OpenRouter.

2. **P1 — Reuse only the safe fallback shape.** Represent OpenRouter’s ordered model fallback as a candidate plan, then run the existing HQ eligibility checks: same team, native idle, no active children, no pending tools/approvals, and preserved project artifact/task ownership. Retry only classified transient/provider failures with a bounded attempt count; never treat arbitrary 4xx or moderation/context outcomes as proof of native quota exhaustion.

3. **P2 — Add capability and outcome fields before any live integration.** The adapter should record requested model, actual model/provider, capability/tool support, fallback index, status class, reported usage, and a generation/request identifier. Keep content out of durable logs. This makes later price/latency/capability comparisons evidence-based.

4. **P2 — Add a measurement gate.** Before choosing Auto Router, latest resolution, service tiers, or provider preferences, collect a fixed-prompt preproduction sample with the same model allowlist and privacy class. Report cost, latency, success/error class, tool-call success, and fallback rate; until then, leave rankings unknown.

## Unknowns and open gates

- No OpenRouter account, API key, paid routing authorization, workspace budget, provider-retention approval, or live measurements are present.
- Provider-specific availability, price, latency, context, reasoning, and tool support can change; this review does not rank providers or models.
- OpenRouter routing metadata and usage fields need an actual schema-tested adapter before they can be trusted by HQ quota accounting.
- Native Codex/Claude/Kimi/ZCode subscription limits and resets remain account/provider-specific and are not established by OpenRouter documentation.
- No production or preproduction deployment was performed; no Mac/Windows behavior changed.

## Subscription decision (official sources only)

This is a purchase decision for direct coding access, separate from OpenRouter. It uses current HQ readiness supplied by the supervisor: GLM is live, Kimi is authenticated but lacks coding entitlement on the server, Claude is signed out, and DeepSeek integration is in progress without an API key.

| Option | Verified official terms | HQ readiness | Decision |
| --- | --- | --- | --- |
| **GLM Coding Plan (Z.ai)** | [Official plan docs](https://docs.z.ai/devpack/overview) say plans start at **$18/month**, support Claude Code/Cline/OpenCode, and have 5-hour plus weekly credits. Lite/Pro/Max allowances are 2,000/12,000/28,000 credits per 5 hours and 10,000/60,000/140,000 weekly. | Existing HQ GLM path works and is already paid. | **Do not buy another GLM subscription.** It is the current baseline; do not claim the quota equals a fixed token count because credits depend on model, cache, tools, and peak/off-peak rates. |
| **Claude Pro / Max** | Anthropic’s [Claude Code subscription terms](https://support.anthropic.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan) list Pro **$20/month**, Max 5x **$100/month**, Max 20x **$200/month**; Claude and Claude Code share rate limits, which reset every 5 hours. | Claude currently signed out in HQ. | **Only conditional next purchase:** first verify the monthly plan, Claude Code entitlement, region, and adapter with a real authenticated turn. Start with Pro; upgrade to Max only after measured usage shows Pro is insufficient. No quality benchmark claim is made. |
| **Kimi membership / Kimi Code** | Kimi’s [membership plans](https://www.kimi.com/en/help/membership/membership-overview) list **¥49/month** minimum and say Kimi Code is included. [Kimi Code terms](https://www.kimi.com/en/help/kimi-code/benefits) say weekly quota and a rolling 5-hour limit are shared across devices/API keys and the benefit is for personal development, not enterprise development. | Authenticated, but current server lacks coding entitlement. | Do not buy for HQ routing now; entitlement and personal-use terms need resolution first. |
| **DeepSeek API** | The official [pricing page](https://api-docs.deepseek.com/quick_start/pricing) is pay-as-you-go, not a subscription: current listed prices vary by model and peak/off-peak window, with API tool calls and Anthropic/OpenAI-compatible endpoints. | Integration is being added; no API key. | Do not buy a subscription. Consider only after API-key authorization and spend controls; price is verified, operational readiness is not. |
| **Qwen Code / Alibaba Cloud Model Studio** | Official [Qwen Code docs](https://www.alibabacloud.com/help/en/model-studio/qwen-code) document pay-as-you-go, Coding Plan, Token Plan Personal/Team, and API-key configuration. The reviewed page does not expose a single current USD subscription price. | No current HQ Qwen integration evidence. | Price **unknown from the reviewed official page**; defer purchase until region, plan price, quota, and adapter are verified. |

The recommendation is therefore **Claude Pro at $20/month only after entitlement and adapter verification**, with Max deferred until measured Pro usage justifies it. GLM is already paid and working, so it is not an additional purchase. This is based on verified price and integration readiness, not a model-quality ranking. No account was created or subscription purchased.

## Shared skill, memory, and task authority audit

The smallest existing hook is the provider session’s MCP server list in `clawteam/integration/shared_tools.py`, already passed by `KimiRuntime` and `ZCodeRuntime` when `shared_tools=True` (`clawteam/integration/kimi_runtime.py:56-58`, `zcode_runtime.py:68-69`). `shared_tools.servers(project)` currently exposes only the reviewed `ruflo` and `codebase_memory` launchers with project-scoped environment variables. It is the right place to add one reviewed HQ bridge entry, rather than copying skill files into every provider account or adding another scheduler.

The canonical task authority already exists in `clawteam/integration/hq_tools.py`: `hq_tasks` reads and updates `TaskStore(team)`, `hq_plan` writes through `WorkflowPlans`, and `hq_command`/`hq_recall` stay bounded. Codex receives these as dynamic tools in `codex_bridge.py:1635-1636`; other runtimes currently receive only the shared MCP list. The minimal implementation plan is:

1. Add one provider-neutral, read-only-by-default MCP bridge launcher to `shared_tools.servers(project)` that exposes the existing `hq_tasks`, `hq_plan`, bounded command/evidence, and approved skill-file read operations through the same HQ session/team/project identity.
2. Have Claude, Kimi, ZCode, and future DeepSeek adapters pass that same server entry at session creation; do not copy `skills/`, create provider-local task stores, or expose provider credentials to the bridge.
3. Bind every bridge call to the existing team/project session and route task writes through `TaskStore`/`WorkflowPlans`; keep HQ as the only task and memory authority. Ruflo/codebase-memory remain the existing shared memory/code-intelligence services, with no second memory backend.
4. Add adapter contract tests for identical tool names/schema, project binding, exact owner validation, plan-mode write rejection, and no raw customer-content persistence. This is a file/function plan only; no implementation or provider session was started in this audit.
