# Best-of-all architecture decision

Status: **target architecture locked for implementation**  
Decision date: 2026-09-21 UTC

This document replaces the assumption that more frameworks are always better.
Company HQ uses **one authority per responsibility**, then a measured second-stage
fallback only when the primary path is insufficient. Candidate repositories are
reused selectively; they are not all installed or always loaded.

## Non-negotiable operating rules

1. **Company HQ is the desktop control center.** Users do not manually coordinate separate provider chats.
2. **One task authority, one long-term memory authority, one runtime supervisor.**
3. **Two-stage behavior is explicit in code, not prompt folklore.**
4. **Native subscription runtimes first.** API/gateway fallback is opt-in and may never silently change billing routes or provider account state.
5. **Smallest capable model first.** Flagship models are escalation capacity, not the default.
6. **Context is retrieved, not replayed.** Workers receive compact task packets, not the user's entire history.
7. **Product repositories stay clean.** Runtime/index/task state lives outside attached repositories unless the user explicitly opts in.
8. **No benchmark percentage becomes a product claim until reproduced on a representative Company HQ task with preserved correctness evidence.**

## Final responsibility map

| Responsibility | Primary | Second stage / fallback | Do not make primary |
| --- | --- | --- | --- |
| Desktop shell / control center | Company HQ React/TypeScript, packaged toward Tauri 2 | Reuse Agent Teams AI graph/editor UX selectively | Separate Agent Teams/Superset/Emdash runtime |
| Native machine/runtime core | Rust sidecar target; current Python bridge during migration | Provider-native binaries/CLIs | C rewrite or Python-only permanent core |
| Task DAG / readiness / claim | **Beads** external-state adapter | ClawTeam compatibility during migration | Two canonical task databases |
| Agent orchestration | **Company HQ manager/router** | Selected Ruflo goals/workflows/intelligence modules | Ruflo autopilot/federation as a second scheduler |
| Provider execution | Official/native provider runtimes with preserved account homes | CCR/OpenCode adapter only for reviewed API/coding-plan routes | Login scraping, auth-file rewriting, silent API fallback |
| Code intelligence | **Codebase Memory MCP** warm process | **Graphify** for broad/cross-asset graph questions | Three always-on code indexes |
| Semantic refactoring | Native IDE/LSP first; Serena only if a measured refactor gap remains | Explicit Serena MCP/plugin use | Always-on duplicate retrieval |
| Long-term cross-provider memory | **Supermemory local target backend** | Current guarded memory backend until migration passes | AgentMemory + Claude-Mem + Graphiti simultaneously |
| Orchestration learning/telemetry | Ruflo intelligence/cost/observability behind Company HQ | Company HQ local metrics | Ruflo owning provider auth/task truth |
| Shell/test/log compression | **RTK** | raw recall artifact on demand | Sending full noisy logs by default |
| Large structured context compression | **Headroom**, only above thresholds | uncompressed payload on correctness fallback | Double-compress every turn |
| Skills / specialist roles | Lazy registry: Agency Agents + selected Top-40 skills | domain-specific specialist packs | Loading hundreds of skills into every prompt |
| Browser QA | Playwright MCP + selected gstack QA method | provider-native browser capability | Browser tooling on non-browser tasks |
| Video production | OpenMontage on demand | ordinary media tooling | Core dependency |
| Diagrams | Diagram Design on demand | Mermaid/native renderer | Core prompt payload |
| Scientific research | Scientific Agent Skills on demand | general researcher | Always-loaded scientific catalog |

## Measured decisions

### Code intelligence

Public, model-free bakeoff on the same synthetic fixture:
GitHub Actions run **35553804431**.

| Candidate | Build/index | Warm query | Query bytes | Expected symbols | Project-tree writes | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Graphify 0.9.65 | 0.462 s | 0.233 s | 1,886 | 3/3 | none with external output | stage-two graph / cross-asset orientation |
| CodeGraph 1.6.0 | 0.635 s | 0.235 s | 1,863 | 3/3 | .codegraph | borrow blast-radius/affected-test ideas |
| Codebase Memory MCP 0.10.8 | 1.592 s | **0.012 s** | **1,097** | 3/3 | none with external cache | **primary warm code intelligence** |
| Graft 0.18.0 | failed clean isolated build | n/a | n/a | 0/3 | none | retire from default path |

Graphify still adds value beyond code: docs, papers, images, video, SQL/config and
broad graph traversal. It is therefore a **second-stage capability**, not a
duplicate always-on code index.

CodeGraph produced excellent source/blast-radius output. Instead of maintaining a
third index, Company HQ should reproduce the useful experience using Codebase
Memory caller/trace/coverage data and borrow CodeGraph presentation ideas.

### Token/context efficiency

Public model-free bakeoff run **35553431498**.

- RTK 0.49.0: pytest output **16,994 -> 257 bytes (98.49% reduction)** while preserving the exact failure sentinel.
- Headroom 0.37.0 with ML compression disabled: structured payload **10,515 -> 5,295 tokens (49.64% reduction)** while preserving the anomaly sentinel.

Product rule: **RTK first for command output. Headroom second only for large
structured/RAG/tool payloads. Never blindly run both over the same content.**
Every compacted result retains a pointer/hash to retrievable raw evidence.

### Task DAG

Public model-free Beads 1.3.0 bakeoff run **35554136836**.

Verified in external state with zero workspace files:
- task creation;
- blocking dependencies;
- dependency-aware ready work;
- atomic claim;
- sequential unblocking after completion;
- cycle rejection;
- durable external state.

Decision: **migrate canonical task/DAG authority from ClawTeam to Beads**.
ClawTeam remains only as a compatibility/message adapter until its task routes
are fully replaced and tested.

## The staged flow Company HQ must enforce

### Stage 0 — Intake and scope

Capture goal, repository, constraints, acceptance criteria, risk and user
authorization. Do not start a model merely because a workspace opened.

### Stage 1 — Read-only plan

The supervisor starts in read-only mode. It may inspect approved context and ask
material clarifying questions. It produces a concise plan/DAG and proposed
worker/model assignments. **No project edits.**

Execution starts only after explicit user approval or an already-approved
automation policy for that scope.

### Stage 2 — Context assembly

Use this order:

1. Beads task + dependency state.
2. Relevant long-term project/user facts after the Supermemory backend is accepted; until migration, the guarded current memory backend supplies this slice.
3. Codebase Memory warm structural/semantic lookup.
4. Graphify only when the question is broad, cross-asset, or primary retrieval has insufficient coverage.
5. Targeted raw file reads for exact verification/editing.

Do not dump all memories, all graph output or all source files into a worker.

### Stage 3 — Worker/model routing

Filter by capability and account availability, then start with the smallest
reviewed model likely to pass. Generic tiers:

- **fast/scout** — lookup, tiny edit, formatting, triage;
- **standard** — ordinary feature/bug/test work;
- **strong** — difficult cross-file or reasoning-heavy task;
- **flagship** — architecture, repeated failure, high-risk ambiguity.

Escalate one tier only when tests/evidence fail, uncertainty stays high, or risk
policy requires it. A provider name never implies its flagship model.

### Stage 4 — Isolated execution

Each independent coding worker gets its own branch/worktree or equivalent
isolated workspace. Company HQ/Rust runtime owns process lifecycle,
cancellation, filesystem boundaries, concurrency and permission enforcement.

### Stage 5 — Evidence compression

- Route noisy shell/test/build output through RTK.
- Preserve failure/error context and raw-output recall IDs.
- Use Headroom only for large structured payloads above configured thresholds.
- Never compress the active user instruction, approval request, security finding or recent critical context without an explicit safe transform.

### Stage 6 — Verification

Run deterministic tests/lint/typecheck/security checks before asking another
model to reason about the result.

### Stage 7 — Independent review

A second provider/model is required only for high-risk changes, architectural
changes, security-sensitive changes, repeated failures, or a configured review
gate. Routine low-risk edits should not automatically pay for two agents.

### Stage 8 — Merge proposal / human gate

No worker merges directly to a protected branch. Company HQ shows the diff,
checks, unresolved findings, token/account usage and reviewer evidence. The user
or approved policy authorizes merge/deploy/publish/spend.

### Stage 9 — Learn without bloating memory

Persist only approved decisions, stable conventions, verified repair lessons,
model/task outcome metrics and task completion evidence. Do not store raw
transient logs/chat replay as durable memory by default.

## Explicit two-stage / fallback pairs

| First stage | Second stage |
| --- | --- |
| Read-only plan | Approved execution |
| Native subscription runtime | Reviewed API/gateway fallback |
| Small/standard model | Strong/flagship escalation |
| Codebase Memory | Graphify broad/cross-asset fallback |
| RTK command compression | Headroom structured-context compression |
| Deterministic tests | Model reviewer |
| Implementer | Independent reviewer for risk gates |
| Existing memory backend | Supermemory local after acceptance/migration |
| One worker | Parallel workers only for independent critical-path savings |

## Ruflo role

Ruflo stays important, but behind Company HQ. Review/adopt selectively:

- Goals — long-running goal/milestone tracking.
- Workflows — resumable stages and human gates.
- Intelligence — outcome feedback for routing/model selection.
- Cost Tracker — token/cost/budget signals.
- Observability — traces, latency, worker lifecycle.
- Security/AIDefence — prompt/PII/security gates where validated.
- Jujutsu/review ideas — diff/reviewer intelligence when useful.

Keep Ruflo autopilot, federation and provider/model-worker ownership disabled
until proven not to compete with Company HQ scheduler, task store or account
boundaries.

The repository currently pins Ruflo 3.41.2. Upstream 3.42.4 fixes smart-memory
similarity reporting but still documents an unresolved reasoningBank/vector
backend status issue. Upgrade only through the normal pinned review/test path.

## Desktop/runtime target

Do not rewrite the working prototype all at once.

**Phase A:** package the current React UI as a real desktop app while retaining
the tested Python compatibility service.

**Phase B:** introduce a Rust runtime boundary for process supervision, worktrees,
IPC, cancellation, permissions, resource budgets, local secret boundaries and
usage aggregation.

**Phase C:** move critical Python runtime responsibilities behind the Rust API.
Python remains allowed for scientific/data tooling and upstream integrations,
but launching Company HQ should eventually not require users to manage Python.

TypeScript remains the correct layer for UI, provider catalogs, typed events and
high-level policy. Rust answers what is allowed and running; TypeScript answers
what should happen.

## Provider/account policy

Company HQ implements provider adapters rather than making a gateway own all
accounts.

Order:

1. official/native runtime using the user's authorized subscription/coding plan;
2. officially documented coding-plan endpoint intended for third-party use;
3. explicit API/PAYG fallback chosen by the user.

CCR/OpenCode are useful adapter/reference projects for catalogs, protocol
translation, logs, retry and fallback. They are **not authorized to import,
rewrite or emulate another provider login automatically**. Provider subscription
portability must be verified per provider before enabling it.

## Skills and the Top-40 catalog

Skill repositories are a **lazy capability registry**. Company HQ indexes only
small metadata: name, domain, trigger, required tools, risk, license and source
revision. The context builder loads the one or few selected skill documents for
the current task.

Examples:
- Agency Agents / wshobson agents — specialist role packets.
- ECC — context discipline, verification and review patterns.
- Superpowers — clarification, bounded planning, debugging/review patterns.
- gstack — product/design/browser QA patterns.
- UI/UX skills — only for interface work.
- Scientific Agent Skills — only for scientific/research work.
- OpenMontage — only for video deliverables.
- Diagram Design — only for diagram deliverables.
- Context7 — only when current official docs retrieval is needed.
- Playwright MCP — only for browser QA.

Do not install a repository merely because it appears in the catalog.

## Retired/default-off choices

- **Graft:** removed from the default path after the clean bakeoff failed while other graph candidates succeeded.
- **Vibe Kanban:** not a canonical store; Company HQ owns product UI and Beads owns task truth.
- **Graphiti:** defer until temporal entity/fact history is a demonstrated gap; it requires additional graph/LLM infrastructure.
- **AgentMemory / Claude-Mem:** useful references, but duplicate the chosen cross-provider memory authority and add resident services/hooks.
- **Serena:** current upstream declares GPL-3.0-or-later. Use only as an explicit semantic-refactor service if LSP/native tools leave a measured gap.
- **CC Switch:** configuration reference, not execution brain.
- **Separate autonomous Agent Teams/Ruflo/Superset schedulers:** disabled.

## Next implementation order

1. Merge the reproducible bakeoff/decision evidence after review.
2. Milestone 2: desktop onboarding + read-only plan/approve-execute split.
3. Add Beads adapter and migrate task/DAG routes with compatibility tests.
4. Add provider-neutral runtime adapter boundary; keep current Codex path working.
5. Add real worker lifecycle/communication + bounded durable replay.
6. Add RTK and usage accounting/budgets.
7. Add Codebase Memory primary context builder + Graphify stage-two adapter.
8. Add Supermemory-local acceptance fixture, then migrate canonical long-term memory only if it passes isolation/recall/correctness tests.
9. Add additional native providers one at a time with account/quota tests.
10. Introduce Rust runtime sidecar and move critical lifecycle/security duties.
11. Add Headroom thresholded structured compression and routing outcome learning.
12. Run one bounded end-to-end idea-to-plan-to-parallel-implementation-to-tests-to-review-to-merge-proposal acceptance before calling Company HQ daily-ready.
