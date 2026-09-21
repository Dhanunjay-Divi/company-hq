# Shared agent tooling selection — 2026-09-21

The selection rule is now **one authority per responsibility plus measured
second-stage fallbacks**. A repository can be valuable without becoming an
always-running dependency.

The current target architecture is defined in docs/BEST-STACK.md.

| Repository / component | Disposition | What Company HQ uses |
| --- | --- | --- |
| Company HQ | **Primary control plane** | Desktop UX, task/model routing, approvals, provider adapters, context assembly and audit trail. |
| Ruflo | **Selective integration** | Goals, resumable workflows, intelligence/outcome learning, cost/usage, observability and selected security/review capabilities. Ruflo does not own provider auth or become a second scheduler. Current pin stays 3.41.2 until a reviewed upgrade. |
| Agent Teams AI | **Reuse UI/components, not runtime authority** | Graph/avatar/editor/team UX patterns. Full account-home/auth/runtime behavior stays disabled. |
| Beads | **Target canonical task/DAG store** | External-state tasks, dependencies, readiness, atomic claim, cycle rejection and durable task history. Model-free bakeoff passed. |
| ClawTeam | **Migration compatibility layer** | Existing UI/task/inbox adapter remains while Beads replaces canonical task routes and real runtime messaging replaces file-inbox assumptions. |
| Codebase Memory MCP | **Primary warm code intelligence** | Structural + semantic retrieval, trace/coverage/architecture, external cache, no product-tree state. |
| Graphify | **Second-stage graph** | Broad/cross-asset questions spanning code, docs, papers, images, video, SQL/config and graph traversal. |
| CodeGraph | **Reference/borrow** | Blast-radius, affected-test and concise source presentation ideas. Do not maintain a third always-on index. |
| Graft (@nanonets/graft; repo trailhq/Graft) | **Retire from default path** | Keep provenance/reference only. Clean isolated bakeoff failed while newer graph candidates succeeded. |
| RTK | **Primary command-output compression** | Test/build/lint/log compaction with raw recall evidence. Model-free pytest bakeoff preserved failure evidence with 98.49% byte reduction. |
| Headroom | **Conditional second-stage compression** | Large structured/RAG/tool payloads only after a threshold and correctness safeguards. Do not double-compress normal shell output. |
| Supermemory local | **Target long-term cross-provider memory backend** | Project/user decisions and stable context after isolated local acceptance passes. Current guarded memory remains until migration. |
| Graphiti | **Default off** | Revisit only if bi-temporal entity/fact history becomes a measured requirement. |
| AgentMemory / Claude-Mem | **Reference only** | Useful memory/context patterns, but would duplicate the selected memory authority and resident services/hooks. |
| Serena | **Explicit semantic-refactor option** | Native LSP/IDE tools first. Current upstream declares GPL-3.0-or-later; use as a separate service only if a refactor gap is demonstrated. |
| Claude Code Router | **Provider/gateway reference + optional reviewed fallback** | Catalog, protocol translation, retry/fallback, logging ideas; no automatic credential/account takeover. |
| OpenCode | **Long-tail API/provider fallback reference** | Useful when no official native runtime/coding-plan adapter exists and the user explicitly enables an API route. |
| Agency Agents | **Lazy skill catalog** | Load only the specialist role needed for a task; never inject the whole roster. |
| wshobson/agents and other Top-40 skill repos | **Lazy skill catalog** | Index tiny metadata and load selected role/skill packets on demand. |
| ECC | **Borrow patterns** | Compact context, verification and review discipline without wholesale hook installation. |
| Superpowers | **Borrow patterns** | Clarification, bounded implementation plans, debugging and staged review. |
| gstack | **Borrow/on-demand** | Product/design/browser QA patterns. |
| Playwright MCP | **On-demand** | Browser QA only for browser/web deliverables. |
| OpenMontage | **On-demand specialist** | Video-production deliverables only. |
| Diagram Design | **On-demand specialist** | Architecture/workflow diagrams only. |
| Scientific Agent Skills | **On-demand specialist** | Scientific/research tasks only. |
| Context7 | **On-demand docs retrieval** | Current library/framework docs only when native official docs retrieval leaves a gap. |
| Superset / Emdash / OpenChamber / Orkas | **Reference shell/worktree ideas** | Useful UX/isolation patterns; no separate competing desktop runtime. |
| DSH Agent Teams / Squad / Agent Squad | **Reference/specific use only** | Their runtime focus does not replace Company HQ provider-neutral control. |
| MeshClaw | **Out of scope by default** | Hardware/mesh use case only. |

## Reproducible evidence

- Code-intelligence bakeoff: Actions run 35553804431.
- Token-efficiency bakeoff: Actions run 35553431498.
- Task-store bakeoff: Actions run 35554136836.
- Portability baseline merged to main as 7c62305b27cd18ed49ce45399c0c6c85157e3ccd.
- Post-merge readiness fixes merged as c903e6ad569efb7aa6e4e959a25467736b8ec330 after a green CI run and final Codex review with no major issues.

No candidate is allowed to rewrite provider authentication, HOME/CODEX_HOME,
product repository instructions or billing routes merely because an upstream
installer normally does so.
