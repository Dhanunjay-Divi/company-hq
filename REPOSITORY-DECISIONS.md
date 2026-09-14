# Shared agent tooling selection — 2026-09-13

The user's objective is useful cross-project teams, economical models, visible
work and communication, with setup outside product repositories. For Pinky,
follow `pinky-ops` and the existing project instructions as well.

| Requested repository | Actual disposition | Reason / useful part |
| --- | --- | --- |
| [Ruflo](https://github.com/ruvnet/ruflo) | Enabled: pinned 3.41.2 narrow MCP | Fourteen actual upstream task, exact-memory and coordination tools. Sandboxed external state; cross-process tests passed. General CLI/model-worker paths stay disabled. |
| [Agent Teams AI](https://github.com/777genius/agent-teams-ai) | Official app and tested compatibility build installed; execution blocked | Opaque bundled runtime still replaces account home and manages auth artifacts. Launcher remains blocked. ClawTeam is the enabled UI. |
| [DSH Agent Teams](https://github.com/NanmiCoder/dsh-agent-teams) | Not installed | Built for DeepSeek Harness; installing it does not upgrade native Codex. |
| [Orkas](https://github.com/Orkas-AI/Orkas) | Not installed | Alternative local orchestration app with its own commander/provider setup; duplicates the current native execution layer. |
| [Squad](https://github.com/bradygaster/squad) | Not installed | Copilot-centered team runtime; consider for an actual Copilot workflow. |
| [ClawTeam](https://github.com/HKUDS/ClawTeam) | Installed pinned 0.3.0 existing board/tasks/inboxes | Guarded local adapter with real inbox composer. Native Codex executes workers; no automatic wake, framework spawn, plugins or proxy. |
| [Agent Squad](https://github.com/2FastLabs/agent-squad) | Not globally installed | Application multi-agent conversation SDK; add to a product only when that product needs the SDK. |
| [MeshClaw](https://github.com/Seeed-Solution/MeshClaw) | Not installed | Meshtastic/LoRa/OpenClaw hardware use case, outside ordinary app development. |
| [Graft](https://github.com/trailhq/Graft) | Installed: 0.18.0, isolated wrapper | Deterministic structural graph, caller/dependency search and optional local code graph UI; no model/deep features enabled. |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Installed and registered: 0.10.8 | Primary structural code knowledge MCP, twelve guarded tools, durable external cache, fixture/caller query and concurrent protocol checks passed. |
| [Agency Agents](https://github.com/msitarzewski/agency-agents) | Actual pinned upstream source installed | On-demand research, product, design, engineering, QA, marketing and operations guidance; shared hierarchy adds native department supervisors. |

The original native Team Board is a fallback summary viewer. The user requests
existing upstream tooling and an overall head, departmental supervisors and
specialists working from one customer-focused plan through launch. Source,
runtimes and memory live outside product repositories; none of these framework
files were merged into Pinky or another product. No claim is made that
all eleven upstreams are installed, tested or safe in every runtime mode.

## Current primary evidence

- [Official Codex subagent docs](https://developers.openai.com/codex/multi-agent/):
  delegation through applicable instructions, per-agent/default model settings,
  personal role files and native activity views.
- [Official configuration reference](https://developers.openai.com/codex/config-reference/):
  `agents.default_subagent_model`, reasoning default and concurrency cap. The
  installed CLI 0.154.0-alpha.6.2 accepted these through a strict config read.
- [Graft 0.18.0 source](https://github.com/trailhq/Graft/tree/de8456e892bad5aeee11403e47fb2227773eb27e)
  and [telemetry contract](https://github.com/trailhq/Graft/blob/de8456e892bad5aeee11403e47fb2227773eb27e/TELEMETRY.md).
  Local lock, native build and fixture evidence: `graft-0.18.0/INSTALLATION.json`.
- [Agent Teams current auth-artifact synchronization](https://github.com/777genius/agent-teams-ai/blob/43764e1df31fccb3a8ba793e7d8637af15aa10ea/src/features/codex-account/main/infrastructure/detectCodexLocalAccountArtifacts.ts)
  and [refresh options](https://github.com/777genius/agent-teams-ai/blob/43764e1df31fccb3a8ba793e7d8637af15aa10ea/src/features/codex-account/main/composition/codexSnapshotRefreshOptions.ts).
- [Codebase memory 0.10.8](https://github.com/DeusData/codebase-memory-mcp/tree/46ae198fc11cda80e817acbc5f5908d7c2de7032)
  and [Agency Agents reviewed content](https://github.com/msitarzewski/agency-agents/tree/ad9264e309bd5e5422c04784372d7841b1e5d604).

Reviewed refs and upstream metadata are in `catalog.json` and
`upstream-status.json`. Update checks only refresh public metadata; they do not
automatically install or execute new versions.
