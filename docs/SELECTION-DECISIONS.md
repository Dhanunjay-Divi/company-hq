# Company HQ: evidence-based component selection

Status: implementation/reviewer handoff, 2026-09-21. This is a selection checkpoint, not a claim that the complete desktop or every provider is shipped.

## Decision

Keep Company HQ as the one user-facing workspace and ClawTeam as the existing task authority. Keep the reviewed native Codex execution boundary. Keep Codebase Memory MCP as the primary structural code-intelligence candidate; do **not** promote CodeGraph to primary based only on feature claims. Graphify is a tested alternative. Select RTK for a bounded pytest-output integration; keep Headroom optional rather than adding a universal provider proxy. Preserve the restricted Ruflo integration and evaluate its other capabilities one at a time, without a second scheduler or blanket initialization.

These choices are reversible when a better candidate wins the same acceptance tests. A public README, star count, model catalog, or successful installation is not evidence that a component is integrated, authorized, economical, or correct in Company HQ.

## What was actually executed

The raw artifacts and machine-readable summary are linked from [selection evidence](../benchmarks/evidence/selection-2026-09-21.json). Public standard Ubuntu runners installed the pinned candidates; the measurement phase then ran with network disabled in a separate network namespace, as the ordinary runner user. Child processes received an explicit environment allowlist and disposable fixture state. No provider credentials, subscription sessions, or model calls were used.

Twenty-five regression tests exercised the measurement gates, including missing tools, subprocess timeouts, stderr/answer separation, nested generated files, symlink handling, source mutation, and lost failure evidence. These passed locally and in the code-intelligence workflow.

### Structural retrieval: two cases, three repetitions each

| Candidate | Required symbols and locations recovered | Median response bytes | Median query seconds | Boundary/result |
| --- | --- | ---: | ---: | --- |
| Codebase Memory MCP 0.10.8 | 6/6 queries | 571 | 0.024583 | No source changes or project additions; warm MCP, two calls per query |
| Graphify 0.9.65 | 6/6 queries | 1,563 | 0.246528 | No source changes or project additions; CLI startup included |
| CodeGraph 1.6.0 | 6/6 queries | 1,600.5 | 0.2229825 | Created `.codegraph` state in the fixture; needs external-state adaptation for our policy |
| Graft 0.18.0 | Not reached | Not measured | Not measured | Missing native `tree-sitter-kotlin` build on Linux/Node 24 with lifecycle scripts disabled |

The CBM result includes a structural call trace **plus** a source-location lookup; it is not an artificially small trace without locations. Cold indexing was 1.633 seconds for CBM, 0.402 for Graphify, and 0.636 for CodeGraph. Warm MCP and new CLI processes have different startup costs; these are workflow observations, not universal speed rankings.

The earlier semantic-query experiment returned unrelated CBM results above the requested symbols. It is not a basis for selecting semantic search as the default. Prefer exact/symbol/path queries and measured retrieval. A tiny known-file edit should still start with targeted file reads rather than building several indexes. We have not established the break-even repository size or amortized savings versus ordinary search.

Do not call CodeGraph's cache source corruption: original files were unchanged. Adapt its state location or use an explicitly approved isolated workspace before changing this disposition. Do not call Graft's setup failure an inferior search algorithm: review/build its native dependency and repeat the same tests before promotion.

### Output reduction: identical pytest cases for each reducer

| Case | Raw bytes | RTK bytes | Required evidence/exit retained | Headroom bytes |
| --- | ---: | ---: | --- | ---: |
| 200 passing tests | 16,357 | 19 | Yes; exit 0 and pass count | 16,357 |
| One failing test among passes | 16,940 | 260 | Yes; exit 1, sentinel, test name, file, failure count | 16,940 |
| Collection syntax error | 2,170 | 2,040 | Yes; exit 2, error kind, file | 2,170 |

RTK 0.49.0 passed all three gates. Headroom 0.37.0 with `kompress_model=disabled` preserved input but selected `router:noop`; it did not reduce this pytest text. This does not establish that Headroom is ineffective on JSON, retrieval payloads, or another configuration. It stays optional for those separately tested workloads.

These are **byte reductions**, not measured provider tokens or subscription savings. All actual-model-token and billed-savings fields remain null. Matching selected error markers does not prove preservation of every fact; retain complete raw output and the original process exit status in the execution integration, and fall back to raw whenever checks fail. Never re-run a mutating command merely to recover a log.

## Audit of the 40-repository inventory

Identity source: [repository-candidates.json](repository-candidates.json) and [the existing upstream review](UPSTREAM-REVIEW.md). Every entry is accounted for below. `Inventory` means a disposition against Company HQ's requirements, **not** runtime execution, a security audit, or permission to copy files. `Executed` means only the narrowly described fixture test above. Before vendoring any source, verify the exact commit, relevant file licenses/notices, dependencies, permissions and integration contract. No bulk import of these repositories was performed by this checkpoint.

| # | Repository | Disposition for Company HQ | Evidence in this checkpoint |
| --- | --- | --- | --- |
| 1 | shareAI-lab/learn-claude-code | Reference for small agent-loop mechanics, not a second runtime | Inventory |
| 2 | multica-ai/andrej-karpathy-skills | Optional concise engineering guidance, loaded per task | Inventory |
| 3 | obra/superpowers | Adapt selected planning/testing/review practices; no blanket hooks | Inventory |
| 4 | DietrichGebert/ponytail | Evaluate only for an uncovered workflow; no default loop | Inventory |
| 5 | garrytan/gstack | Lazy specialist workflow references, not a parallel company manager | Inventory |
| 6 | affaan-m/ECC | Selected role/testing/routing guidance; no global account configuration | Inventory |
| 7 | Yeachan-Heo/oh-my-claudecode | Orchestration reference; avoid duplicate task authority | Inventory |
| 8 | coleam00/Archon | Evaluate retrieval/tool ideas only if current stores have a measured gap | Inventory |
| 9 | Leonxlnx/taste-skill | Optional design task skill | Inventory |
| 10 | anthropics/skills | Optional skill source with per-file license review | Inventory |
| 11 | mattpocock/skills | Optional task-specific skill source | Inventory |
| 12 | wshobson/agents | Lazy specialist roles; roles are not permanently bound to models | Inventory |
| 13 | anthropics/claude-plugins-official | Explicitly selected compatible plugins, not automatic installation | Inventory |
| 14 | addyosmani/agent-skills | Optional engineering task skills | Inventory |
| 15 | nextlevelbuilder/ui-ux-pro-max-skill | Optional UI work, not every coding task | Inventory |
| 16 | travisvn/awesome-claude-skills | Discovery catalog, not a runtime dependency | Inventory |
| 17 | OthmanAdi/planning-with-files | Adapt compact durable task packets without copying every conversation | Inventory |
| 18 | thedotmack/claude-mem | Hold duplicate memory store; reconsider only for measured missing capability | Inventory |
| 19 | colbymchenry/codegraph | Tested challenger; external-state adaptation required before default adoption | Executed: six queries |
| 20 | Graphify-Labs/graphify | Tested alternative graph; enable on demand, not alongside every indexer | Executed: six queries |
| 21 | yamadashy/repomix | Explicit export aid; avoid routinely sending an entire repository | Inventory |
| 22 | rohitg00/agentmemory | Hold duplicate store; compare recovery/scoping before adoption | Inventory |
| 23 | gastownhall/beads | Task-store challenger; no concurrent canonical task databases | Inventory; not re-executed here |
| 24 | multica-ai/multica | Desktop/workflow reference, not a replacement decision without end-to-end tests | Inventory |
| 25 | firecrawl/firecrawl | Optional authorized web-data workflow; do not send private code by default | Inventory |
| 26 | farion1231/cc-switch | Configuration UX reference; no credential copying or silent billing reroute | Inventory |
| 27 | upstash/context7 | Optional targeted documentation retrieval with source/version checks | Inventory |
| 28 | BloopAI/vibe-kanban | Workflow UX reference; no second task board | Inventory |
| 29 | github/github-mcp-server | Candidate for narrowly scoped GitHub tools with explicit permissions | Inventory |
| 30 | microsoft/playwright-mcp | Candidate for UI verification with isolated browser state | Inventory |
| 31 | oraios/serena | Semantic-edit challenger; test language servers, edits and boundaries first | Inventory; not executed here |
| 32 | musistudio/claude-code-router | Routing reference only; no subscription-token proxy as default | Inventory |
| 33 | punkpeye/awesome-mcp-servers | Discovery catalog, never bulk exposed in every prompt | Inventory |
| 34 | x1xhlol/system-prompts-and-models-of-ai-tools | Not production policy or trusted authorization; exclude by default | Inventory |
| 35 | shanraisshan/claude-code-best-practice | Reference guidance, not a runtime dependency | Inventory |
| 36 | openai/codex-plugin-cc | Evaluate official interoperability against installed runtime/auth support | Inventory |
| 37 | jarrodwatts/claude-hud | Usage/context display reference; unknown quota must remain unknown | Inventory |
| 38 | rtk-ai/rtk | Selected for bounded pytest-output integration with raw evidence retained | Executed: three preservation cases |
| 39 | headroomlabs-ai/headroom | Optional for other payload types; no benefit on tested pytest configuration | Executed: same three cases |
| 40 | JuliusBrussee/caveman | No default aggressive instruction compression; correctness/clarity first | Inventory |

## Additional repositories and Ruflo

| Component | Disposition | What must not be implied |
| --- | --- | --- |
| ruvnet/ruflo | Keep reviewed scoped memory; consider cost, workflow, observability and learned-routing components separately | Plugin documentation is not proof those capabilities are implemented or safe in Company HQ |
| nanonets/graft | Retain optional wrapper; block default promotion until native installation is reproducible | A failed build is not a measured retrieval loss |
| DeusData/codebase-memory-mcp | Keep primary structural graph, with project-scoped external state and version checks | No global installer/config rewrite or claimed semantic-search superiority |
| msitarzewski/agency-agents | Lazy role catalog; use relevant packets only | Hundreds of definitions do not require hundreds of workers |
| calesthio/OpenMontage | Optional video deliverable workflow with separate permissions/cost checks | Video generation costs are not automatically included in coding subscriptions |
| cathrynlavery/diagram-design | Optional diagram skill | Not part of every coding prompt |
| lamm-mit/scientific-agent-skills | Optional research/domain skills after dependency checks | No claim the whole catalog has been installed or validated |
| getzep/graphiti | Optional temporal-memory experiment | Do not add another default store simply because it uses a graph |
| supermemoryai/supermemory | Optional cross-session memory evaluation | No unapproved transfer of private project data to a hosted service |
| "Open-source agent tools" | Unresolved generic label | No exact repository identity or copied implementation is claimed |

Ruflo is not reduced to memory as a design possibility. The **currently admitted** integration is restricted memory. Additional modules need a contract test for cancellation, failure recovery, permission inheritance, account isolation, bounded context, and duplicate-work prevention before exposure. Broad initialization, autonomous background workers, hooks, federation and provider routing remain off until separately reviewed.

## Economical execution contract

This is the integration acceptance contract, not a claim that every item is already wired into main:

- Classify locally when deterministic rules suffice; use one capable worker by default. Add parallel workers only for independent work with explicit ownership/worktree isolation.
- Choose from the account's actually authorized model catalog. Subscription tier and model size are separate. Do not hard-code imaginary small/medium/large models or fabricated remaining quota.
- Escalate after failed checks, missing capabilities or explicit high-risk requirements, not merely an agent's self-reported confidence. Bound retries and review costs.
- Do not charge a mandatory extra model review for every trivial planning task. Use deterministic checks for routine low-risk work and independent review for sensitive changes or release acceptance.
- Build compact task packets containing acceptance criteria, current diff/files, selected instructions and relevant scoped memory. Load one useful skill rather than an entire catalog.
- Use exact code lookups before broad semantic retrieval. Reuse a valid index; invalidate on source changes. Do not build CBM, Graphify, CodeGraph and Graft for every task.
- Preserve raw output and original exit status. Apply the tested reducer only to supported command families; unsupported/failed/lossy reduction falls back to raw. Do not proxy credentials to obtain output savings.
- A hard spend cap requires an enforceable pre-execution admission budget and accurate provider metering. A post-hoc token display is not a hard cap. Unknown provider quota stays unknown, with no silent switch to paid APIs.

## IDE and release boundary

Main currently provides a local browser-based Company HQ UI with a Python backend and native Codex bridge. It is not yet a packaged Rust desktop, nor proof of Claude/Kimi/GLM/Grok subscription execution. The user can supervise in the Company HQ UI and use a normal code editor alongside it; installing several chat extensions is not the orchestration mechanism.

Rust/TypeScript remains a planned desktop/runtime direction, not a delivered rewrite. Keep working, tested Python integration code until a replacement passes the same lifecycle, recovery, permissions and account-boundary tests. Language preference alone is not evidence of token savings or a reason to restart the product.

Run the reviewed main demo using the current README instructions. This benchmark branch is for review and reproducible evidence, not a new all-provider production release. Do not buy every top subscription based on catalog entries alone.

## Remaining acceptance before a complete release

A realistic repository suite with stale-index and cross-project tests; verified supported provider logins/model discovery; bounded model escalation and enforceable usage controls; durable worker messaging/recovery; end-to-end UI and project approval tests; and an installer/launcher that removes routine terminal setup. These are separate implementation/acceptance tasks. The six upstream tools tested here do not establish completion of those features.
