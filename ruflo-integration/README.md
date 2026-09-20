# Ruflo project memory for native Codex

This integration uses pinned Ruflo 3.41.2 as a local MCP task, decision-memory,
and coordination-metadata store. Native Codex remains the worker runtime. Ruflo
does not launch agents, call a model, execute shell commands, access a provider,
or initialize product repositories through this wrapper.

The wrapper binds a project identity from the first tool call's absolute
`project_root` argument (or an explicit `RUFLO_PROJECT_ROOT` fixed for a
per-project launch), then changes to an external runtime
directory under the external Company HQ state root under `ruflo/projects/<sha256>/`. Task and
coordination files, memory databases, and relative Ruflo state stay there. It
does not replace `HOME` or `CODEX_HOME`, read authentication, install hooks,
start a daemon, or register itself globally. `allowed-tools.json` is an exact
execution allowlist; tools hidden from `tools/list` are also rejected by
`tools/call`.

Useful tools are `task_create/status/list/update/complete/cancel`, exact
`memory_store/retrieve/list/stats`, and local coordination
metadata (`coordination_topology/sync/node/metrics`). Coordination metadata does
not execute agents or prove liveness. Record actual native Codex IDs and states.

The server command for an MCP client is:

```text
<checkout>/ruflo-integration/ruflo-mcp
```

The launcher strips inherited provider credentials, discovers or accepts an explicit Node executable, and applies `sandbox.sb`: no network, with writes only below the configured external Ruflo state directory. It fails closed when the reviewed macOS sandbox is unavailable. It does not change HOME/CODEX_HOME.
Tool descriptions omit upstream's repeated general-CLI guidance so this MCP
surface stays concise and describes the actual external-state behavior.

Every tool call should pass the current project's absolute path as
`project_root`. A server binds once and rejects a later call for another project;
start a separate MCP process per Codex task. This remains safe when a global MCP
client starts the server from its own app/home directory. It refuses `/` and the
user home directory as project scopes. Network-backed model downloads are
disabled. Exact memory remains authoritative. This machine currently reaches
Ruflo's deterministic hash/mock embedding fallback, so `memory_search` is not
enabled; hash-vector similarity must not be represented as semantic retrieval.

This pinned install's optional AgentDB bridge reports a successful write to
`agentdb-memory.db` while its public retrieval path reads `memory.db`. The
wrapper sets Ruflo's supported `CLAUDE_FLOW_DISABLE_BRIDGE=1` switch to keep all
public memory operations on one coherent `memory.db`. Re-evaluate that choice
after a reviewed upstream upgrade fixes and tests split-store continuity.

Ruflo remains pinned and carries the dependency-audit findings recorded in
`ruflo-3.41.2/INSTALLATION.json`. This narrow integration does not approve the
general Ruflo CLI, `init`, normal `--help` startup, agent execution, providers,
hooks, daemons, or auto-update paths.
