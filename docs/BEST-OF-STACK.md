# Best-of-stack architecture

This is the current Company HQ component decision record. It is intentionally a
**capability selection**, not an instruction to install every repository.

The selection pool is the user's 40-repository catalog in
`docs/repository-candidates.json` plus the extra repositories reviewed for the
same goal: Ruflo, Agent Teams AI, Emdash, Superset, OpenCode, Graft,
Codebase Memory MCP, CodeGraph, Serena, Graphify, Supermemory, Graphiti,
claude-mem, agentmemory, Agency Agents, wshobson/agents, Diagram Design,
Scientific Agent Skills, OpenMontage, RTK, Headroom and related references.

## Selection rules

A component becomes a default only when it improves the system without creating
a second source of truth. Company HQ optimizes for:

1. native subscription/account boundaries before proxying,
2. one canonical task authority and explicit worktree ownership,
3. compact retrieval before raw repository exploration,
4. the smallest capable model before escalation,
5. measured token/quality trade-offs rather than marketing percentages,
6. local/isolated state by default,
7. progressive disclosure for skills and memory,
8. maintained, auditable and license-compatible source.

## Current winning stack

| Layer | Primary choice | Fallback / specialist | Why |
| --- | --- | --- | --- |
| Desktop/control plane | **Company HQ**, reusing current **Agent Teams AI** runtime/provider/usage patterns | Emdash UX/worktree patterns | Agent Teams now has mature native provider, model/effort, task review, recovery and budget patterns; Company HQ keeps the single authority and user-facing workflow. |
| Native execution | **Provider-native runtimes** (Codex first, then Claude/Kimi/etc. only after verified account integration) | OpenCode for broad provider/API coverage; CCR only for explicitly approved gateway/coding-plan lanes | Keeps subscription authentication and billing semantics honest. |
| Orchestration | **Company HQ task authority + bounded Ruflo capabilities** | Agent Teams orchestration patterns | Ruflo contributes goals, workflows, intelligence, observability, cost and security without becoming a competing scheduler. |
| Project/task state | **ClawTeam/Company HQ canonical task records** | Borrow Beads dependency/compaction ideas | A second issue/task database would create split ownership. |
| Project memory | **Ruflo** for decisions, task outcomes and learned patterns | Supermemory local for user/cross-project memory after benchmark | Reuses the orchestration substrate; avoids injecting whole chat history. |
| Temporal enterprise knowledge | Not default | Graphiti when temporal facts/provenance justify a graph DB | Powerful but operationally heavier than normal coding work needs. |
| Structural code graph | **CodeGraph external-state adaptation candidate** | Graft + guarded Codebase Memory MCP | CodeGraph is local, broad and designed for pre-indexed structural questions; upstream project-local storage must be adapted before activation. |
| Semantic code/refactor tools | **Serena as optional external MCP** | native agent tools | Symbol/reference/refactor operations can save many file reads, but its GPL runtime stays external rather than vendored into Company HQ. |
| Docs/config/media graph | **Graphify on demand** after external-state wrapper | CodeGraph for ordinary source | Strong heterogeneous graph support; upstream `graphify-out/` project writes make it unsuitable as the default until isolated. |
| Deterministic token reduction | **RTK candidate for default shell-output compression** after matched-output tests | native concise commands | Local, deterministic, cross-agent and does not proxy model traffic. |
| Broad context compression | Optional **Headroom MCP/library** after accuracy benchmark | none | Potentially large savings, but transparent provider wrapping is not accepted as the native-subscription default. |
| Cost/usage/routing feedback | **Agent Teams usage schema + Ruflo cost/intelligence patterns** | provider-native usage | Distinguishes exact vs estimated usage and API vs subscription billing while enabling routing feedback. |
| Skills marketplace | **wshobson/agents** as primary curated portable catalog | Agency Agents as secondary role library | Progressive disclosure and multi-harness generation avoid loading hundreds of skills into every prompt. |
| Product/engineering method | Selected **ECC + gstack + Superpowers** techniques | other 40-repo skills when task-specific | Reuse bounded planning, verification, debugging, product/design and browser-QA techniques without installing competing harnesses. |
| Scientific/research work | **Scientific Agent Skills**, on demand | general research agents | Load only the selected scientific skill needed for a task. |
| Diagrams | **Diagram Design**, on demand | Mermaid/native diagrams | Specialist capability should not occupy normal coding context. |
| Video/media production | **OpenMontage**, on demand | none | Full production pipeline is valuable only when the deliverable is media. |

## Repositories deliberately not made core

- **Superset** is a strong parallel-workspace reference, but Elastic License 2.0
  and its own workspace authority make it a poor core dependency for Company HQ.
- **Vibe Kanban** has excellent task/worktree/review ideas, but its repository
  announces that the product is sunsetting.
- **CC Switch** is useful provider/configuration UI reference, but Company HQ
  will not make relay/proxy switching the default for native subscriptions.
- **claude-mem** and **agentmemory** remain memory benchmark candidates. Running
  them beside Ruflo and Supermemory by default would duplicate capture,
  compression and retrieval.
- **Beads** has excellent dependency, compaction and messaging concepts, but it
  would be a second canonical task store.
- **Graphiti** is reserved for workloads that actually need temporal knowledge
  graphs instead of being installed for every repository.
- **RTK and Headroom percentages are not Company HQ savings claims.** Company HQ
  adopts them only after matched acceptance tasks preserve errors and outcomes.

## How the 40-repository catalog is used

The 40 entries are not discarded. They are a **component menu**:

- Harness entries feed planning, verification, debugging and review patterns.
- Skills entries feed the lazy skill registry.
- Memory entries are benchmarked against the selected memory/code-context layers.
- Tool entries are activated only when Company HQ lacks that capability.
- Cost entries are benchmarked against equivalent raw tasks before adoption.

The full identity, license metadata, observed revision and earlier next action
for every one of the 40 remains in `docs/repository-candidates.json`. A repo
can move from reference to active component when a measured gap justifies it.

## Target request path

```text
User goal
  -> Company HQ overall manager
  -> plan/clarify in read-only mode
  -> task DAG / canonical task records
  -> context builder
       -> structural code query first
       -> relevant project decisions/patterns
       -> one or two task-specific skills
  -> router
       -> native provider/account capability
       -> smallest capable model + reasoning tier
       -> available quota/concurrency
       -> codebase-specific outcome history
  -> isolated worker/worktree
  -> tests + risk-aware review
  -> escalate only on failure/uncertainty/risk
  -> human approval -> merge candidate
```

## Benchmark gates before promotion

A new component must pass a matched task set:

- same repository snapshot and task,
- same acceptance checks,
- cold and warm-context runs distinguished,
- input/cached/output/tool-output volume captured,
- errors and diagnostics preserved,
- wall time and tool calls recorded,
- no hidden account/config/project mutation,
- rollback verified.

The winning component is selected per capability. Company HQ does not require
one repository to win every category.
