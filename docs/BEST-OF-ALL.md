# Best-of-all architecture

Company HQ is the product. Upstream repositories are capability sources. The
goal is not to run every framework at once; it is to reuse the best proven
piece at each layer while keeping one coherent desktop workspace.

## User experience

The user opens Company HQ, connects a local project, and talks to one overall
manager. The manager proposes a plan, chooses useful specialists, selects an
authorized provider/model/effort, creates isolated work, and reports progress.
The user should not need to open separate Claude, Codex, Kimi, GLM or Grok
extensions to coordinate the work.

```text
Company HQ desktop
  |
  +-- mission / plan / approval
  +-- work board / team map / diffs / usage
  +-- project memory / code intelligence
  |
  +-- smart router
       |
       +-- native Codex
       +-- native Claude
       +-- native Kimi
       +-- native GLM
       +-- native Grok
       +-- native Gemini
       +-- OpenCode long-tail providers
```

Native subscription/account routes are preferred when the provider officially
supports them. API gateways such as CCR or CC Switch are explicit optional
routes, not silent defaults.

## Selection rules

Every capability is judged against the same constraints:

1. correctness on representative tasks;
2. context/token reduction without dropping required evidence;
3. no product-repository pollution by default;
4. no hidden authentication or billing-route changes;
5. cross-platform reliability;
6. compatible license and update path;
7. graceful degradation when unavailable;
8. measurable benefit over the capability already in Company HQ.

An upstream is not adopted merely because it has more features.

## Current decisions

### Keep Company HQ as the control plane

Do not replace the desktop with a stack of extensions or CLIs. Selectively reuse
Agent Teams AI's provider/runtime/team/worktree/diff implementation patterns.
Use Emdash and OpenChamber as permissive references where they solve a concrete
UX/runtime gap. Superset is a useful reference but its Elastic License needs a
different reuse posture.

### Use Ruflo as an augmentation layer

Ruflo is broader than memory. The useful surfaces for Company HQ are cost and
budget tracking, resumable workflows, long-horizon goals, learned routing,
observability, security gates, ADR/diff intelligence and compact-context
mechanisms.

Ruflo does **not** become a second top-level scheduler. Company HQ remains the
authority for tasks, provider selection, worker lifecycle and human approvals.

### Benchmark code intelligence instead of guessing

The deterministic model-free benchmark in `benchmarks/code-intelligence/`
currently compares Graft 0.18.0, Codebase Memory MCP 0.11.0, Graphify 0.9.65,
and CodeGraph 1.6.0 on the same synthetic authentication call chain.

Measured current result:

| Candidate | Full symbols/relation | Query token proxy | Repo clean | Index / query |
| --- | --- | ---: | --- | --- |
| Codebase Memory MCP 0.11.0 | yes | 378 | yes | 1.755s / 0.025s |
| Graphify 0.9.65 | yes | 570 | yes | 0.431s / 0.471s |
| CodeGraph 1.6.0 | yes | 914 | **no** | 0.690s / 0.655s |
| Graft 0.18.0 | no (fresh safe install failed native parser) | 0 | yes | 0.260s / — |

So **Codebase Memory MCP 0.11.0 is the current default for repeated structural
code queries**. Graphify is complementary: it indexes much faster and extends
naturally to docs/media graphs while keeping the project tree clean. CodeGraph
remains a strong optional specialist but is not the default while it places its
index inside the product tree. Graft stays available only where a verified local
native runtime already exists; it no longer wins the portable default slot.

Serena is evaluated separately for semantic symbol lookup, safe editing and
refactoring. Its current repository is GPL-3.0-or-later, so Company HQ should
treat it as an external optional service/tool unless a later license review
justifies a different reuse boundary.

### Token efficiency is layered

The model-free bake-off in `benchmarks/token-efficiency/` now gives us a
selective policy rather than one global compressor.

| Path | Logs | Tests | Repetitive JSON | Decision |
| --- | ---: | ---: | ---: | --- |
| RTK 0.49.0 | 99.35% saved, evidence kept | 96.35% saved, evidence kept | 99.7% saved but **evidence lost** | default for supported logs/tests only |
| Headroom 0.37.0 local structural mode | 22.8% saved, evidence kept | 0% saved | 81.96% saved, evidence kept | optional for large structured payloads |
| Raw | 0% | 0% | 0% | fallback for unknown/high-risk output |

These percentages are reductions in the benchmark payload, not provider billing
claims. Company HQ should therefore use RTK for supported shell/test/log output,
fall back to raw for unknown or evidence-sensitive output, and use Headroom only
through its local library/MCP surface when a structured payload actually
benefits. **Headroom proxy/wrap is not the default**, because native provider
authentication and subscription routing must remain unchanged.

The router also reduces usage by retrieving code/memory before raw exploration,
passing compact task packets, loading skills on demand, using the smallest
capable model, and escalating only after failure, uncertainty or higher risk.

### Skills are a catalog, not a prompt

ECC, wshobson/agents, gstack, Agency Agents, Scientific Agent Skills, Diagram
Design, OpenMontage and Superpowers are progressive-disclosure sources.

A normal backend bug should receive a small backend/debugging packet, not
hundreds of agents and skills. Scientific and media capabilities load only when
the mission calls for them.

### Keep one task authority

Company HQ/ClawTeam remains canonical for now. Beads has valuable dependency
graphs, atomic claims, compaction and messaging ideas that can be reused or
tested underneath the same UI. Vibe Kanban is not a core candidate because the
upstream project now states that it is sunsetting.

## Runtime language direction

The prototype Python adapters proved the protocol, isolation and approval
boundaries. They are not the desired permanent runtime core.

The target split is:

```text
React + TypeScript
  UI, provider registry, routing policy, skills, normalized events
          |
          v
Rust local runtime
  process supervision, worktrees, sandbox, permissions, IPC,
  concurrency/resource limits, usage metering, secure filesystem work
          |
          v
native provider runtimes + MCP/capability services
```

Python remains available for scientific/data tooling and integrations but should
not be required just to launch the finished application.

## Rollout order

1. Finish portable/readiness fixes and keep model-free CI green.
2. Keep code-intelligence and token-efficiency bake-offs in public model-free CI.
3. Add first-run plan/approve/execute UX.
4. Introduce a provider adapter interface and native workers beyond Codex.
5. Add durable worker events/messages and restart recovery.
6. Add usage budgets, smallest-capable-model routing and RTK measurement.
7. Add scoped cross-provider memory and selected Ruflo intelligence surfaces.
8. Begin Rust sidecar extraction of process/worktree/permission/usage runtime.
9. Add specialist skills and workflows only when their acceptance tests exist.

The UI remains stable while internals improve. A capability can be replaced
without changing the user's mental model: one Company HQ, one mission, one
manager, visible workers, explicit approvals.
