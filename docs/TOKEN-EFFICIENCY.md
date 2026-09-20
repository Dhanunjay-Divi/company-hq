# Company HQ: tooling and token-efficiency strategy

Status: implementation policy for the current stacked PRs. This is deliberately
not an "install every interesting repository" plan.

## Decision

Company HQ is the desktop control plane. A provider's supported native runtime
is the execution boundary. ClawTeam is the canonical task/inbox record. Ruflo
stores small, project-scoped decisions. Git/source remains the truth. Structural
code tools are invoked on demand, not injected into every prompt.

The router chooses **provider -> smallest reviewed model -> smallest supported
reasoning effort** that fits the task. Today only native Codex execution is
verified. Future Claude/Kimi/GLM/Grok adapters must use a reviewed official
runtime/authentication path and report their own live catalog before Auto may
route work to them. Company HQ must not extract subscription credentials or
pretend API billing is subscription capacity.

## Context ladder

Use the cheapest source of truth first:

1. current task + explicit user constraints;
2. exact ClawTeam task/messages and relevant Ruflo decisions;
3. targeted structural query when code relationships are uncertain;
4. one relevant role/skill playbook;
5. exact source snippets required to execute or verify;
6. broader repository/history only when the earlier layers are insufficient.

Never preload the whole repository, the 232-agent roster, all skills, all
decision memory, or the full chat history "just in case".

Workers receive compact packets: objective, acceptance check, constraints,
relevant paths/IDs, and only the evidence needed for their independent part.
They do not receive a replay of the entire supervisor conversation.

## Code understanding: use both, but not redundantly

| Tool | Use | Do not use |
| --- | --- | --- |
| **Graft** | Fast deterministic map/caller/dependency navigation when the agent would otherwise rediscover structure. Model features remain off. | Do not automatically build/query it for a one-file obvious change. |
| **codebase-memory-mcp** | Primary MCP structural knowledge graph for repeated relationship/caller/impact queries. Index on demand and keep indexes external to product repos. | Do not dump graph results into every task or query it again when Graft/source already answered the question. |
| **Git/source** | Final implementation truth and exact verification. | Do not replace source inspection with stale memory. |

Rule: ask one structural system first. Query the second only for a concrete gap,
cross-check, or capability the first does not provide. This keeps graph
duplication from becoming context duplication.

Graphify/codegraph/Serena/Graphiti-style alternatives stay deferred unless a
measured task demonstrates a missing structural capability. Adding another
always-on graph now would duplicate indexing, state and retrieval tokens.

## Memory

- **ClawTeam**: task ownership, dependencies, inboxes and coordination evidence.
- **Ruflo**: compact project decisions/constraints with exact project scope.
- **codebase-memory/Graft**: code relationships, not user-conversation memory.
- **Runtime event journal**: bounded execution evidence; streaming deltas are not
  persisted as another transcript.

Do not add Supermemory/Graphiti/another vector store by default. If future
cross-provider continuity has a measured gap, add one memory adapter behind a
single gateway and compare retrieval/context cost before making it always-on.

## Specialist libraries

These are capabilities, not permanent teammates or permanent prompt content.

| Capability | Policy |
| --- | --- |
| **Agency Agents (232 specialists / 16 domains)** | Load one relevant role file at a time. Never preload the roster. A role is guidance, not a live worker. |
| **ECC patterns** | Borrow selective context, verification and review handoff patterns; no blanket hook/install adoption. |
| **gstack patterns** | Use for product/design/browser QA where its workflow is relevant. |
| **Superpowers patterns** | Use bounded planning/debugging/review methods where useful. |
| **Diagram Design** | Load only when a diagram is an actual deliverable or materially improves architecture communication. |
| **Scientific Agent Skills** | Load the smallest relevant scientific/research skill for research tasks only. Do not inject 160+ skills into normal software work. |
| **OpenMontage** | Video-production workflow only. It should not enter ordinary coding context or startup cost. |
| **Open-source agent tool collections** | Treat as discovery catalogs. Review one concrete tool against an identified gap before adding it. |

The Top-40 inventory in `docs/UPSTREAM-REVIEW.md` is a candidate audit, not an
installation queue. Public identity/metadata review of all forty does not imply
full source/runtime acceptance of all forty.

## Model and reasoning policy

Auto routing does not spend a model call to classify work. It uses an
explainable deterministic classifier plus the native provider's token-free model
catalog.

Current reviewed Codex bands:

- **small**: Luna / low where supported;
- **standard**: Terra / medium where supported;
- **complex**: Sol / high where supported;
- **flagship fallback**: Astra only when the smaller reviewed complex tier is
  unavailable, or after explicit/evidence-driven escalation.

Manual model selection remains available. Unknown model names are not ranked by
guesswork.

Do not automatically retry the same failed task across a chain of increasingly
expensive models. First inspect the failure and re-plan; ask or escalate only
when the evidence justifies it.

## Usage controls

The native runtime's latest cumulative token report is authoritative per thread.
Company HQ keeps the latest total for the supervisor and each observed child,
then sums those thread totals once. Repeated cumulative notifications do not get
summed again.

Display:

- provider-reported total tokens;
- input tokens;
- cached input tokens separately;
- output/reasoning tokens;
- observed thread count.

Cached input is **not added again** to `totalTokens`. A reported-token
checkpoint is a context/usage guard, not a dollar estimate and not a claim about
subscription billing. The default checkpoint is 100,000 reported tokens; it
warns at 80%. Reaching it does not kill an active turn, but blocks new model
input until the user raises or disables the checkpoint.

No cost-saving percentage should be claimed until matched tasks are measured
before/after.

## Worker policy

Default maximum: three support workers, and fewer is better when work is
sequential.

- Luna: bounded read/search/inventory.
- Terra: normal implementation.
- Sol: independent complex review, architecture, security or difficult debugging.
- Flagship: exceptional/evidence-driven.

Only native child threads observed from the provider are shown as live workers.
A role card or task owner is not proof of a running model process.

## Provider expansion

Each future provider adapter must expose the same minimum contract:

1. authorized current account/runtime state;
2. live model catalog and supported effort/capability metadata;
3. start/resume/send/stop;
4. sandbox/permission semantics;
5. child lifecycle and communication evidence when available;
6. authoritative usage/quota signals the provider actually exposes.

Adapters should prefer official subscription-aware runtimes when the provider
supports them. If a provider requires API billing, the UI must say so rather
than presenting it as subscription reuse.

OpenCode or another broad provider bridge can be evaluated later for the
long-tail, but it should not sit between Company HQ and an official
subscription-aware runtime merely for uniformity.

## What we intentionally do not make core

- a second scheduler beside ClawTeam/native execution;
- a static team of 232 agents;
- multiple always-on memory/vector/knowledge-graph systems;
- video/scientific/design skills in every software prompt;
- global provider config rewrites;
- credential extraction or account switching;
- automatic flagship-first routing;
- token or dollar savings claims without measurements.

This architecture optimizes for useful work per context token, not for maximum
number of installed repositories.
