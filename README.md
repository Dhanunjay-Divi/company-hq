# Company HQ

A local AI team workspace for taking an idea through planning, implementation, review and launch. It combines the actual Agent Teams AI graph with ClawTeam task/inbox records, Ruflo decision memory and native Codex supervisor execution.

This public repository preserves the shared toolkit source built on 13–14 September 2026. **It is a working prototype and development handoff.** The portability work keeps runtime state outside the checkout and does not deploy or modify the original live installation merely by cloning or starting this source.

## Start here

- [Implementation handoff and acceptance criteria](docs/IMPLEMENTER-HANDOFF.md)
- [What works and what remains](docs/STATUS.md)
- [Architecture and source map](docs/ARCHITECTURE.md)
- [New upstream candidates: ECC, gstack, Superpowers and the 40-repo list](docs/UPSTREAM-REVIEW.md)
- [Reviewer instructions](docs/REVIEWER.md)
- [Portable setup and isolation](docs/PORTABILITY.md)
- [Packaging provenance](docs/PACKAGING.md)

For the current user-requested implementation sequence, portable setup, onboarding, worker communication/visibility, and usage controls are kept in separate bounded PRs so the original Codex supervisor can review them independently.

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

Node 24+ and Python 3.10+ are the starting prerequisites. Native Codex execution and the Ruflo OS sandbox have been verified only on macOS; unavailable capabilities are shown honestly in **System status**.

For a clean model-free first run:

```sh
python3 scripts/hq.py bootstrap --demo
```

For the normal local workspace after reviewing the setup:

```sh
python3 scripts/hq.py bootstrap
```

Both commands keep runtime state outside this checkout (default: `~/.local/state/company-hq`, or `$XDG_STATE_HOME/company-hq`). They do not rewrite `HOME`/`CODEX_HOME`, copy authentication, start a provider in demo mode, or initialize the attached product repository. See [portable setup](docs/PORTABILITY.md).

From the repository root, run the complete model-free validation suite with:

```sh
python3 scripts/hq.py check
```

That command uses the system interpreter for root utilities and the pinned
`clawteam/venv` interpreter for integration tests, then checks the source
bundle, portability boundaries and truthful capability status.

The original live installation remains a separate deployment target. Running this checkout does not replace it.

## Cost and data

Opening the board does not start an agent. Pressing Start working does. Native work uses the existing account and may consume its allowance; the prototype has reported token counts, not a complete bill or enforced spending budget. Multiple agents are not automatically cheaper. Keep simple work with one agent, use bounded smaller workers, and retain concise shared decisions.

No credentials, Codex conversations, runtime bindings, local task/message databases, user project lists, product files, downloaded binaries, virtual environments or dependency caches are intentionally included.

## License

Company HQ and its original adaptations are AGPL-3.0-only, with upstream notices retained. Agent Teams AI graph/avatar code is copyright © 2026 Илия (777genius). ClawTeam and other dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md). Public visibility does not change third-party license obligations. New candidate repositories have not been copied or activated merely because they appear in the catalog.
