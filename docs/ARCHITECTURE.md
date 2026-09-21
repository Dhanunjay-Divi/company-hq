# Architecture

The canonical target is defined in [BEST-STACK.md](BEST-STACK.md). This file
describes the runtime boundaries and the migration from the current prototype.

## Target

~~~mermaid
flowchart TD
  U[User] --> D[Company HQ desktop]
  D --> M[Company HQ manager/router]
  M --> T[Beads canonical task DAG]
  M --> C[Context builder]
  C --> SM[Supermemory local target]
  C --> CBM[Codebase Memory MCP]
  C --> GF[Graphify stage two]
  M --> R[Provider adapter registry]
  R --> N[Native subscription runtimes]
  R --> F[Reviewed API/gateway fallback]
  M --> W[Worker runtime]
  W --> WT[Isolated worktrees]
  W --> RTK[RTK command evidence]
  RTK --> H[Headroom only for large structured context]
  W --> V[Tests/lint/type/security]
  V --> RV[Independent reviewer when risk gate requires]
  M --> RF[Ruflo goals/workflows/intelligence/cost/observability]
  T --> G[Agent Teams graph/UI adapter]
  G --> D
~~~

## Authority boundaries

- **Company HQ manager/router** is the only orchestration authority.
- **Beads** is the target task/dependency/readiness authority.
- **Supermemory local** is the target long-term cross-provider memory authority,
  but does not replace code indexes or task state.
- **Codebase Memory MCP** is the primary warm code-intelligence service.
- **Graphify** is invoked only as a second-stage broad/cross-asset graph.
- **Ruflo** supplies bounded goals/workflow/intelligence/cost/observability
  capabilities behind Company HQ; it is not a second scheduler or provider-auth owner.
- Provider runtimes own their own supported account/login state. Company HQ
  receives capability/usage signals but does not copy or rewrite credentials.

## Current implementation

Today the merged baseline still uses:

- React/Vite Company HQ shell and Agent Teams graph adapter.
- Loopback Python HTTP service.
- Native Codex app-server bridge.
- ClawTeam task/inbox compatibility state.
- Guarded Ruflo scoped memory.
- Guarded Codebase Memory support.

That is a **transition state**, not the final division of responsibility.

## Desktop/runtime migration

1. Package the existing React shell as a real desktop application.
2. Add a Rust runtime boundary for process supervision, worktrees, IPC,
   cancellation, permissions, resource/token budgets and durable event transport.
3. Keep Python adapters behind that boundary while functionality is moved
   incrementally. Do not rewrite working integrations all at once.
4. Eventually normal Company HQ startup should not require the user to manage
   a Python environment. Python remains valid for scientific/data integrations.

## Context pipeline

The context builder assembles the smallest sufficient packet:

1. Beads task/acceptance/dependency state.
2. selected stable project/user memories;
3. Codebase Memory query/trace/coverage;
4. Graphify only if broad or cross-asset context is still missing;
5. targeted raw source reads for verification/editing;
6. one or a few lazily selected specialist skills.

Raw histories, full skill catalogs, whole graph dumps and whole repositories are
not default prompt material.

## Execution pipeline

Plan and execution are separate states. Planning is read-only. After approval,
workers run in isolated worktrees. Deterministic verification happens before
model review. Independent review is conditional on risk rather than automatic.

No worker directly merges a protected branch, deploys, publishes, spends money
or sends external communications without the applicable user/policy gate.

## Cost/token pipeline

- RTK is the first filter for noisy command/test/build/log output.
- Headroom is a second-stage transform for large structured payloads only.
- Raw evidence remains retrievable.
- Model routing starts at the smallest capable tier and escalates one tier at a
  time on failed evidence, unresolved ambiguity or risk policy.
- Account-wide allowance, provider-reported tokens and estimated/billed money
  remain distinct metrics.

## Product and account isolation

Source/configuration, Company HQ state, provider account homes and attached
product repositories remain separate. The desktop must fail closed when an
optional capability cannot satisfy its sandbox/state/account requirements.
