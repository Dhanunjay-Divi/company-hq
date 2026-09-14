# Company HQ

A local AI team workspace for taking an idea through planning, implementation, review and launch. It combines the actual Agent Teams AI graph with ClawTeam task/inbox records, Ruflo decision memory and native Codex supervisor execution.

This private repository preserves the shared toolkit source built on 13–14 September 2026. **It is a working local prototype and a development handoff, not a finished portable product.** The live installation is separate from this checkout; committing here does not deploy or change a product project.

## Start here

- [Implementation handoff and acceptance criteria](docs/IMPLEMENTER-HANDOFF.md)
- [What works and what remains](docs/STATUS.md)
- [Architecture and source map](docs/ARCHITECTURE.md)
- [New upstream candidates: ECC, gstack, Superpowers and the 40-repo list](docs/UPSTREAM-REVIEW.md)
- [Reviewer instructions](docs/REVIEWER.md)
- [Packaging provenance](docs/PACKAGING.md)

During this initial phase, the implementer can commit and push directly to main without draft PRs. The original Codex supervisor reviews pushed checkpoints afterward and can commit corrections.

The user talks primarily to the overall supervisor. Useful functional leads and specialists should be allocated according to the actual goal, available account access, complexity and cost. A visible roster is not proof that those agents are running.

## Source layout

| Path | Contents |
| --- | --- |
| `company-hq/` | React/Vite interface, upstream graph and avatars, source archive builder |
| `clawteam/integration/` | Loopback HTTP API, native Codex bridge, task/inbox adapter, tests, native protocol schemas |
| `ruflo-integration/` | Narrow project-scoped MCP adapter, allowlist and macOS sandbox |
| `codebase-memory-mcp-0.10.8/` | MCP guard/launcher and installation provenance; no binary or indexes |
| `teamboard/` | Earlier Swift/macOS audit board and configuration/test utilities |
| root Python files | Model/client discovery, kickoff, reviewed update checks, isolated Graft wrapper |
| `skills/`, `roles/` | Reusable operating guidance and native role templates when applicable |
| `patches/` | Earlier custom upstream compatibility changes; inactive reference material |
| `catalog.json` | Previously reviewed integration pins and dispositions |
| `docs/repository-candidates.json` | All 40 supplied candidates with observed public metadata; not an activation list |

## Build and checks

Node 24+ and Python 3.10+ are the starting prerequisites. Native runtime verification was on macOS with the installed Codex app; other platforms are not verified.

```sh
cd company-hq
npm ci --ignore-scripts
npm run build
```

From the repository root, model-free checks:

```sh
python3 -m unittest -v test_check_updates test_discover
python3 -m unittest discover -s clawteam/integration -p test_codex_bridge.py
python3 scripts/check_source_bundle.py
```

The full HTTP suite also needs the pinned ClawTeam dependency environment at `clawteam/venv` and the frontend build. See [portability limits](docs/STATUS.md) before starting the server: several copied integration paths still target the original installation. Do not point a fresh clone at another project's live state by accident. Refactor these paths in the first implementation milestone; don't change HOME or CODEX_HOME to compensate.

The original local installation can be opened using its `clawteam/integration/team-ui` launcher. That existing installation is not replaced by cloning this repository.

## Cost and data

Opening the board does not start an agent. Pressing Start working does. Native work uses the existing account and may consume its allowance; the prototype has reported token counts, not a complete bill or enforced spending budget. Multiple agents are not automatically cheaper. Keep simple work with one agent, use bounded smaller workers, and retain concise shared decisions.

No credentials, Codex conversations, runtime bindings, local task/message databases, user project lists, product files, downloaded binaries, virtual environments or dependency caches are intentionally included.

## License

Company HQ and its original adaptations are AGPL-3.0-only, with upstream notices retained. Agent Teams AI graph/avatar code is copyright © 2026 Илия (777genius). ClawTeam and other dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md). Private visibility does not erase third-party license obligations. New candidate repositories have not been copied or activated merely because they appear in the catalog.
