# Portable setup and isolation

Company HQ keeps four boundaries separate:

1. **Source checkout** — this repository and pinned source/provenance.
2. **Runtime state** — tasks, bindings, local memory and generated graphs, outside the checkout.
3. **Product workspace** — the user-selected repository that agents may edit only through the approved runtime.
4. **Provider account home** — existing Claude/Codex/etc. authentication and configuration, which Company HQ does not copy or replace.

## First run

Model-free onboarding:

```sh
python3 scripts/hq.py bootstrap --demo
```

Normal local workspace:

```sh
python3 scripts/hq.py bootstrap
```

The bootstrap command creates the ignored `clawteam/venv`, installs the pinned
ClawTeam requirements, runs `npm ci --ignore-scripts`, builds the frontend and
starts the loopback-only board. Demo mode creates only a clearly labeled
synthetic project beneath Company HQ state and disables model start/send/approve
routes.

Runtime state defaults to:

- `$XDG_STATE_HOME/company-hq` when `XDG_STATE_HOME` is set.
- otherwise `~/.local/state/company-hq`.

`COMPANY_HQ_STATE_ROOT` can select another private state location. The runtime
rejects the filesystem root, the account home itself, and the Company HQ source
checkout as a state root.

## Optional configuration

| Variable | Purpose |
| --- | --- |
| `COMPANY_HQ_STATE_ROOT` | Company HQ state root |
| `COMPANY_HQ_PYTHON` | Python used by the board/ClawTeam wrapper |
| `COMPANY_HQ_CODEX_PATH` | Existing native Codex executable |
| `COMPANY_HQ_ROUTING_PATH` | Reviewed model-routing policy |
| `COMPANY_HQ_SAVED_PROJECTS_PATH` | Optional local project-picker metadata |
| `COMPANY_HQ_RUFLO_LAUNCHER` | Reviewed Ruflo MCP launcher |
| `COMPANY_HQ_RUFLO_STATE_ROOT` | Ruflo state directory |
| `COMPANY_HQ_GRAFT_INSTALL` | Pinned Graft package root |
| `COMPANY_HQ_GRAFT_STATE_ROOT` | Graft graph state |
| `COMPANY_HQ_CODEBASE_MEMORY_LAUNCHER` | Reviewed codebase-memory launcher |
| `COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT` | codebase-memory cache/runtime state |
| `COMPANY_HQ_NODE` | Node binary for the reviewed Ruflo wrapper |

These are path/capability settings, not credential injection. Provider login
continues to belong to the provider's supported runtime.

## Fail-closed behavior

- The secure board remains loopback-only, validates Host, and requires matching
  Origin for POSTs.
- Native Codex keeps the existing account environment; Company HQ does not set
  `HOME`, `CODEX_HOME` or auth overrides.
- Native execution remains workspace-write with explicit user approvals and
  network disabled by the bridge policy.
- Ruflo strips inherited provider credentials and currently requires the
  reviewed macOS `sandbox-exec` path. If that sandbox is unavailable, Ruflo is
  reported unavailable rather than launched unsandboxed.
- codebase-memory reports unavailable unless both its reviewed wrapper/guard and
  pinned executable are present.
- Graft graphs are external to product repositories and its structural wrapper
  strips common provider model/API variables.

Open **System status** in Company HQ, or run:

```sh
python3 scripts/hq.py health
```

to see what is actually available without starting a provider.

## Portability checks

```sh
python3 scripts/check_portability.py
python3 scripts/check_source_bundle.py
```

The first rejects original-machine paths in active runtime/source guidance.
Historical verification, archived experiments and immutable installation
provenance can still describe the machine on which they were produced.

## Platform limits

The frontend and model-free Python configuration are intended to be portable.
Native provider/runtime acceptance is still platform-specific. Ruflo is
deliberately macOS-only until an equivalently restrictive sandbox is reviewed.
The bundled codebase-memory provenance describes a Darwin arm64 binary, but the
repository does not ship that binary. Graft's optional native parser may also
need a platform-specific build.

No live installation is changed by these source changes. Deployment or migration
of an existing installation remains a separate reviewed action.
