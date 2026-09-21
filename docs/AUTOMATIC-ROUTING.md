# Automatic routing and review

Company HQ uses one control plane. The user describes the outcome once; the
system decides which capabilities are useful without loading every agent, skill,
or repository into model context.

## End-to-end pipeline

```text
User request
   |
   v
0. Safety / permission boundary
   |
   v
1. Deterministic classification (no model call)
   - request facets
   - repository stack signals from names/extensions only
   - risk level
   - useful candidate tools/skills/roles
   |
   v
2. Independent preflight review
   - different model family preferred
   - high risk: apex reviewer when available
   - reviewer may only add/remove allowlisted roles
   - block before execution on material safety/capability gaps
   |
   v
3. Staffing + model assignment
   - smallest capable team
   - scout / worker / expert / apex tier
   - only locally available tools survive the plan
   - only selected skill packets are loaded
   |
   v
4. Execution
   - Company HQ remains the scheduler
   - ClawTeam remains canonical task/message state
   - native provider runtimes keep their own authorized accounts
   - isolated child workers/worktrees as supported
   |
   v
5. Verification
   - tests/lint/typecheck/browser checks appropriate to the change
   - capture actual failures, usage, child state, and approvals
   |
   v
6. Independent completion review
   - prefer a different provider family from the implementer
   - compare diff + acceptance evidence against the reviewed plan
   - high-risk work cannot be presented as merge-ready without review evidence
   |
   v
Human approval / merge
```

Stages 0–3 are the current automatic routing milestone. Stages 5–6 are explicit
architecture requirements; completion review is implemented in the next worker
lifecycle/review milestone rather than being faked through a prompt.

## Why classification is deterministic first

Calling a large model just to decide whether a task needs a frontend engineer or
a database specialist wastes quota and can hallucinate tools that are not
installed. The first pass therefore uses compact metadata:

- task words and phrases;
- project file names and extensions, bounded to a small sample;
- the reviewed capability catalog;
- actual local health/availability.

No source bodies or full skill prompts are read during this pass.

## Lazy specialist loading

The repository is a capability catalog, not an instruction dump. Company HQ
indexes compact metadata for the broad upstream pool, then loads only selected
packets.

Examples:

- scientific request -> scientific research specialist/skill;
- explicit diagram request -> Diagram Design packet;
- video deliverable -> OpenMontage packet;
- product scope -> gstack/Agency Agents product methods;
- backend/security -> matching ECC/wshobson engineering skills;
- refactor -> CodeGraph, and Serena when semantic refactoring is useful.

The 40-repository catalog remains a discovery pool. A repository is not active
just because it is catalogued.

## Current stack decisions

| Layer | Decision | Why |
| --- | --- | --- |
| Desktop/control plane | Company HQ, reusing Agent Teams AI UI/runtime patterns selectively | One user-facing workspace and one scheduler |
| Canonical tasks/messages | ClawTeam | Already integrated and project-scoped; avoid competing task stores |
| Orchestration extras | Ruflo goals/workflows/intelligence/cost/observability selectively | Valuable capabilities without handing it scheduling authority |
| Code intelligence | Prefer CodeGraph; add Serena for semantic/LSP editing | Local, cross-platform graph plus precise symbol-aware refactoring |
| Mixed code/docs/media graph | Graphify on demand | Useful when relationships cross code, docs, PDFs, schemas or media |
| Legacy structural fallback | codebase-memory-mcp / Graft only when healthy | Keep fallback coverage while stronger candidates are benchmarked |
| Tool-output reduction | RTK preferred after matched benchmark | Low-risk local filtering; no provider auth proxy |
| Aggressive compression | Headroom experimental | Promising, but must pass matched quality/error-retention tests first |
| Skills/roles | ECC + wshobson + gstack + Agency Agents + Superpowers + specialist repos, lazy-loaded | Broad expertise without huge always-on context |
| Provider routing | Native authorized runtime first; OpenCode only for explicit configured long-tail providers | Preserve subscription/account/billing boundaries |
| Vibe Kanban | Do not adopt as core | Upstream is sunsetting; borrow UX ideas only |
| CC Switch | Reference only | Useful configuration ideas, but no second provider authority/proxy by default |

## Model hierarchy

There is no permanent universal winner. Company HQ has role tiers:

- **Scout** — smallest capable model for discovery/checks.
- **Worker** — normal implementation.
- **Expert** — complex implementation and review.
- **Apex** — high-risk architecture/security/migration/coordination only.

The current verified Codex seed is:

- Scout: `gpt-5.6-luna`
- Worker: `gpt-5.6-terra`
- Expert: `gpt-5.6-sol`
- Apex coordinator: `gpt-6-astra`

Apex is a policy slot, not a permanent OpenAI entitlement. Current external
challengers include Claude Fable 5, Grok 4.6, Kimi K3 and GLM-5.3. Promotion to
the apex slot requires matched completed-task evidence in this codebase.

For an OpenAI/Codex implementation, preflight review prefers Anthropic when an
authorized Claude Code runtime is present:

- low risk: Sonnet class;
- medium risk: Opus class;
- high risk: Fable class, then Opus fallback.

If cross-family review is unavailable, Company HQ may use an isolated same-family
reviewer and must label the reduced diversity.

## Apex evaluation

A model is not promoted because of marketing or one benchmark. Company HQ scores
completed runs using acceptance correctness, actual tool/task completion,
reviewer catch rate, rework, token efficiency, latency and runtime stability.
Quality dominates the score; when quality is statistically indistinguishable,
the lower-token/lower-latency model wins.

The apex comparison should be refreshed on a significant model/runtime catalog
change or at least every 30 days.

## Token-efficiency rules

1. Classify without a model.
2. Query code intelligence before broad repository rereads.
3. Retrieve scoped memory only when relevant.
4. Pass compact role/task packets, not inherited chat transcripts.
5. Load only selected skills.
6. Use RTK-style compact command/test output only after error-preservation tests.
7. Start one worker by default; parallelize only independent work.
8. Escalate model tier only after complexity/risk classification or failed evidence.
9. Use an independent reviewer instead of duplicating every task across models.
10. Measure cached input, uncached input, output, retries and accepted/reworked results.

## Safety and account boundaries

Reviewers and workers never gain a provider account by being named in the
catalog. A provider is usable only when its supported local runtime is installed
and already authorized by the user. Company HQ does not scrape sessions, copy
credentials, rewrite HOME/CODEX_HOME, silently buy API usage, or move traffic
through an unapproved proxy.
