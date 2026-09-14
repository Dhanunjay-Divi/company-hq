# codebase-memory-mcp 0.10.8

Pinned upstream release: `v0.10.8`, source commit
`46ae198fc11cda80e817acbc5f5908d7c2de7032`.

The installed executable came from the official GitHub release asset
`codebase-memory-mcp-darwin-arm64.tar.gz`. Its verified SHA-256 is
`9bd840dfb3ec7eaef4f310382057adaa5b0e904df883104d03ffcf39836afd07`, matching
both the release API digest and the release `checksums.txt`. `gh attestation
verify` also accepted the archive for repository
`DeusData/codebase-memory-mcp`.

The upstream `install` command was not run. It can edit detected coding-agent
configuration, instructions, skills, and hooks. The local MCP wrapper instead
uses a minimal environment, lowers logging, and passes `--ui=false` on every
launch. Its state is rooted at the owner-private
`/Users/Shared/agent-toolkit-codebase-memory-mcp-501`; `state/external` links to
that durable location. CBM rejected every path below the user's home because
that home has an inherited allow ACL. Its private-directory check was not
weakened.

The wrapper's stdio guard allows index and structural-query tools, forces
`index_repository.persistence=false`, and refuses indexing a repository that
already contains `.codebase-memory` because upstream refreshes that artifact
even with persistence false. It blocks `delete_project`, `manage_adr`, and
`ingest_traces`.

Persistent settings in `state/external/cache/_config.db`:

- `auto_index=false`
- `auto_watch=false`

Repository indexing must leave `persistence` omitted or explicitly set it to
`false`. In upstream 0.10.8 it defaults to false. Setting it true writes
`.codebase-memory/` and may modify `.gitattributes` and local Git configuration.

Suggested MCP registration:

```toml
[mcp_servers.codebase_memory]
command = "/Users/uno/.local/share/agent-toolkit/codebase-memory-mcp-0.10.8/bin/codebase-memory-mcp-mcp"
args = []
enabled_tools = ["index_repository", "search_graph", "query_graph", "trace_path", "get_code_snippet", "get_graph_schema", "get_architecture", "search_code", "list_projects", "index_status", "check_index_coverage", "detect_changes"]
```

The registration is intentionally global so it can index an explicitly chosen
project anywhere below an upstream-accepted root. `CBM_ALLOWED_ROOT` is not set
because one fixed path would conflict with the requested any-project behavior.
The binary still refuses filesystem roots, home, system trees, and recognized
credential directories as indexing roots. Treat `index_repository` as an
explicit, project-scoped operation.

## Verification

The durable synthetic fixture in `state/external/fixture/cbm-fixture` indexed
seven nodes and seven edges. A deliberately unsafe MCP request with
`persistence=true` was forced to false; source hashes remained identical and
no `.codebase-memory` or `.gitattributes` appeared. `search_graph` found the
fixture's `add` function, while a `manage_adr` request was blocked by the local
guard. A stdio `initialize` and `tools/list` smoke reported server version
0.10.8. The guard now filters `tools/list` itself to the same 12 tools for every
client. A mixed burst of six native queries and six locally denied calls produced
14 independently parsed JSON-RPC response lines with every expected ID, and a
non-object JSON message caused no guard exception. EOF left no frontend, guard,
or daemon process running.
