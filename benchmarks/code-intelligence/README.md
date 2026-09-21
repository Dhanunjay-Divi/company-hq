# Code-intelligence bake-off

This benchmark compares code-intelligence candidates for Company HQ without
calling an LLM. It exists so upstream marketing numbers, stars, and model
preferences cannot decide the default integration.

## Fixture

Each candidate receives a fresh Git repository containing the same Python call
chain:

```text
handle_login
  -> login_request
     -> AuthService.authenticate
        -> verify_token
           -> normalize_token
```

The benchmark asks each tool to locate `verify_token` and recover evidence for
the authentication call chain.

## What is measured

- whether a clean pinned install can index/build the fixture;
- index/build latency;
- structural query latency;
- query output bytes and a transparent bytes/4 token proxy;
- presence of `verify_token`, `authenticate`, and `login_request`;
- call/path/edge evidence;
- files added or changed inside the product repository;
- external state size.

The token proxy is only a normalization for tool output. It is **not** a claim
about provider-billed tokens.

## Candidates

- **Graft 0.18.0** — the current deterministic Company HQ structural wrapper.
  The benchmark deliberately installs the npm package with lifecycle scripts
  disabled, matching the safer fresh-clone posture; missing native parser
  readiness is therefore visible rather than repaired invisibly.
- **Codebase Memory MCP 0.10.8** — downloaded from its immutable release and
  verified against SHA-256
  `6eef49652bc0c7820f43114125044d40bf7f4d97c11b2592f6b0f6a307702325`.
- **Graphify 0.9.65** — installed from release commit
  `7ca736cf94cd2fe8564704e31aa0e9b9f6e04fc6`; output is redirected outside
  the fixture with `GRAPHIFY_OUT`.
- **CodeGraph 1.6.0** — exact npm version. Telemetry, update checks, and the
  background daemon are disabled for the test. Its current design requires the
  per-project index directory to live in the project root, so any such write is
  intentionally counted as pollution.

Serena is not included in this table because its strongest differentiator is
symbol-aware editing/refactoring via LSP/JetBrains, not being a drop-in
persistent graph replacement. It gets a separate acceptance test before being
enabled as an editing capability.

## Run locally

Install any candidates you want to test, export their binary paths if they are
not on PATH, then run:

```sh
python3 benchmarks/code-intelligence/run.py
```

Supported overrides are `GRAPHIFY_BIN`, `CODEGRAPH_BIN`, `CBM_BIN`, and
`COMPANY_HQ_GRAFT_INSTALL`.

The public GitHub workflow installs all four pinned candidates and prints both a
Markdown summary and the complete JSON result to the job log.

## Adoption rule

No single score selects a winner. A Company HQ default must:

1. return correct structural evidence;
2. save context/tool calls on representative tasks;
3. remain model/provider independent;
4. keep product files clean by default;
5. work within the account/project/permission boundary;
6. have acceptable license and maintenance risk.

A candidate that fails the product-tree isolation requirement may still be used
inside an explicit disposable worktree or as an optional specialist, but it
does not become the default index.
