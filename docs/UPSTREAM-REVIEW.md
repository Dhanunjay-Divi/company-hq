# Upstream review and adoption queue

Checked 2026-09-14 UTC. The public Notion page was accessible in the browser; all 40 repository identities were extracted and current metadata fetched directly from GitHub. All 40 metadata requests succeeded. This is not a full source/security audit, and the Notion author’s license labels are not treated as licensing authority.

## First candidates

- **[ECC](https://github.com/affaan-m/ECC):** README describes a cross-harness system with planning, verification, review, memory and context management, including a Codex path. Inspect selected context and verification components first. Its hooks/configuration and large skill roster need conflict and overhead review. No ECC installer, hosted service or plugin was enabled for this handoff.

- **[gstack](https://github.com/garrytan/gstack):** README describes product, design, engineering, review and browser QA roles, with current Codex setup support. Useful for the founder-to-delivery workflow. Adapt individual methods and browser QA evidence first; inspect setup, telemetry, permission and release behavior before activating automation. No gstack setup or browser runtime was run.

- **[Superpowers](https://github.com/obra/superpowers):** README describes design clarification, bounded plans, debugging, subagent execution and staged review. Use selected planning/debugging/review techniques. Its mandatory workflow and broad test-first rules need reconciliation with project instructions and task size. No plugin/bootstrap was installed.

These are component candidates for the implementing agent. The measured selections and second-stage rules are now locked in BEST-STACK.md. Keep native execution, one task authority and one scoped memory strategy unless a measured gap justifies a replacement. Preserve exact file licenses and upstream revisions for anything copied. Metadata license fields can be null or NOASSERTION and do not settle file-specific rights.

## All 40 candidates

Source list: [The Top 40 Claude Repos](https://app.notion.com/p/The-Top-40-Claude-Repos-3d8e396e06bb81f89f09e657d663b003). Full observed heads, canonical identities, timestamps and decisions are in [repository-candidates.json](repository-candidates.json).

| Group | Repository | GitHub license metadata | Next action |
| --- | --- | --- | --- |
| Harness | [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Harness | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Unresolved | Backlog: identify a concrete missing capability before source review or installation. |
| Harness | [obra/superpowers](https://github.com/obra/superpowers) | MIT | First: bounded implementation plans, systematic debugging and staged code review; resolve workflow conflicts. |
| Harness | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Harness | [garrytan/gstack](https://github.com/garrytan/gstack) | MIT | First: product/design review and browser QA workflow candidates; adapt host requirements and release authorization. |
| Harness | [affaan-m/ECC](https://github.com/affaan-m/ECC) | MIT | First: inspect selected context, verification and review components; no wholesale hooks/config installation. |
| Harness | [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Harness | [coleam00/Archon](https://github.com/coleam00/Archon) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT | UI candidate after readability/onboarding acceptance criteria are defined. |
| Skills | [anthropics/skills](https://github.com/anthropics/skills) | Unresolved | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [wshobson/agents](https://github.com/wshobson/agents) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | Apache-2.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Skills | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | UI candidate; compare against current graph interaction constraints. |
| Skills | [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | Unresolved | Backlog: identify a concrete missing capability before source review or installation. |
| Memory | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Memory | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Apache-2.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Memory | [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | MIT | Benchmarked: strong blast-radius/source presentation; borrow ideas, do not maintain a third always-on index. |
| Memory | [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | Apache-2.0 | Selected second-stage broad/cross-asset graph after model-free bakeoff. |
| Memory | [yamadashy/repomix](https://github.com/yamadashy/repomix) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Memory | [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | Apache-2.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Memory | [gastownhall/beads](https://github.com/gastownhall/beads) | MIT | Selected target canonical task/DAG store after external-state dependency/claim/cycle bakeoff. |
| Tools | [multica-ai/multica](https://github.com/multica-ai/multica) | NOASSERTION | Backlog: identify a concrete missing capability before source review or installation. |
| Tools | [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | AGPL-3.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Tools | [farion1231/cc-switch](https://github.com/farion1231/cc-switch) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Tools | [upstash/context7](https://github.com/upstash/context7) | MIT | Optional documentation retrieval if native official docs tools leave a gap. |
| Tools | [BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban) | Apache-2.0 | UI/task lifecycle reference; do not add a second canonical task store by default. |
| Tools | [github/github-mcp-server](https://github.com/github/github-mcp-server) | MIT | Use only if existing GitHub connector/gh cannot satisfy the workflow. |
| Tools | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | Apache-2.0 | Use only if existing browser tooling cannot provide required validation. |
| Tools | [oraios/serena](https://github.com/oraios/serena) | GPL-3.0-or-later | Optional explicit semantic-refactor service only if native LSP/IDE tools leave a measured gap; do not duplicate normal retrieval. |
| Tools | [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | MIT | Provider/gateway reference and optional reviewed API/coding-plan fallback; never own provider auth implicitly. |
| Tools | [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Cost | [x1xhlol/system-prompts-and-models-of-ai-tools](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools) | GPL-3.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Cost | [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Cost | [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | Apache-2.0 | Backlog: identify a concrete missing capability before source review or installation. |
| Cost | [jarrodwatts/claude-hud](https://github.com/jarrodwatts/claude-hud) | MIT | Backlog: identify a concrete missing capability before source review or installation. |
| Cost | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Apache-2.0 | Selected first-stage command/test/log compression; model-free bakeoff preserved failure evidence with 98.49% byte reduction. |
| Cost | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Apache-2.0 | Selected conditional second-stage structured-context compression; not a universal proxy. |
| Cost | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | NOASSERTION | Backlog: identify a concrete missing capability before source review or installation. |

## Refresh safely

`python3 scripts/refresh_candidates.py` refreshes public metadata using an existing `gh` login. It never installs, runs or activates candidate code. An observed head is a review target, not an approved update. Review source diffs, tests, license changes, access requirements and rollback before activation.
