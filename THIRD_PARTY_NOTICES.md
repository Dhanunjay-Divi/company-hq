# Third-party provenance

- **Agent Teams AI** graph and avatar assets, copyright © 2026 Илия (777genius), AGPL-3.0, commit `c2e9212e7a1a8daed34d7464432fc18eec62b238`. Source and license are in `company-hq/vendor`; the camera-fit modification is documented there. Earlier compatibility patches retain that upstream provenance.
- **ClawTeam**, HKUDS, MIT, commit `01198332ef9270c32c5460b8a178f964fc0df451`. Installed separately from the pinned requirements; license retained as `company-hq/vendor/CLAWTEAM-MIT.txt`.
- **Ruflo 3.41.2 / @claude-flow/cli 3.33.0** remain separately installed dependencies. npm lock and sandboxed wrapper source are included; original packages and their transitive licenses govern those packages.
- **codebase-memory-mcp 0.10.8**, commit `46ae198fc11cda80e817acbc5f5908d7c2de7032`, has its official license/notices retained under `codebase-memory-mcp-0.10.8/licenses`. The reviewed guard is source; no executable or index is committed.
- **Graft 0.18.0** is an optional separately installed navigation dependency. Only our isolation wrapper and operational documentation are included.
- **Agency Agents**, commit `ad9264e309bd5e5422c04784372d7841b1e5d604`, is vendored as on-demand role/playbook markdown under `agency-agents/upstream`. MIT, copyright (c) 2025 AgentLand Contributors; license retained there. `agency-agents/REFERENCE-MANIFEST.json` records file hashes. No upstream installer, hook or executable is adopted.
- **Codex app-server** protocol schemas are retained as generated API/schema reference from local runtime `0.154.0-alpha.6.2`; no Codex executable, authentication material or conversation is included. OpenAI Codex source is Apache-2.0; corresponding license is retained in `licenses/CODEX-APACHE-2.0.txt`.
- **react-markdown 10.1.0**, copyright Espen Hovlandsdal, MIT. Used for conversation rendering; raw HTML is disabled. License retained in `company-hq/vendor/REACT-MARKDOWN-MIT.txt`.
- npm and Python dependencies remain separately licensed; lockfiles are not a relicensing of those dependencies.

Company HQ and original integration code use the root AGPL-3.0-only license. A private repository does not itself change upstream license obligations. A candidate's catalog entry does not authorize copying all of its files. Resolve mixed, custom, unknown and file-level licenses before adopting new code.
