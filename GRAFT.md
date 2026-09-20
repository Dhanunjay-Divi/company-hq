# Isolated Graft 0.18.0

Graft is installed only as a deterministic structural code graph helper. It is
not initialized in any repository or coding-agent configuration, and its model,
brain, MCP, upgrade, and background integration paths are not enabled.

## Installed package

- Package: `@nanonets/graft@0.18.0`
- npm source commit: `de8456e892bad5aeee11403e47fb2227773eb27e`
- npm integrity:
  `sha512-sNshNND1Q/qSXiuSh9nW8NniWyaD+m55oJZ6oCGJsLzxot52WSJrdThsQ3NZVTNT+lqivlYkkqN8b/nf22S/Xw==`
- Install root: `<checkout>/graft-0.18.0`
- Wrapper: `<checkout>/graft.py`
- Graph state: `~/.local/state/company-hq/graft/projects/<sha256>/graph`
- Node requirement: Node.js 20 or newer
- npm lifecycle scripts were disabled with `--ignore-scripts`.

The SHA-256 directory name is calculated from the canonical absolute project
path. `project.json` records that mapping beside each graph. All graph output is
outside the source repository. A per-project advisory lock serializes builds and
queries because queries can refresh stale structural graph data; visualization
remains a separate read-only foreground process.

## Commands

Build a structural graph without a model or API key:

```bash
<checkout>/graft.py build /absolute/path/to/repository
```

Query the graph. A query refreshes stale structural data unless `--no-refresh`
is supplied:

```bash
<checkout>/graft.py query /absolute/path/to/repository "where is session authentication checked?"
```

Optional query flags are `--json`, `--source`, and `--no-refresh`.

The local visualization is never started automatically. An explicit invocation
serves the existing graph in the foreground on loopback only:

```bash
<checkout>/graft.py viz /absolute/path/to/repository --explicit --port 4400
```

Stop it with Ctrl-C. Upstream binds to `127.0.0.1` and tries up to nine following
ports if the requested port is occupied.

## Isolation controls

The wrapper always sets `DO_NOT_TRACK=1`, `GRAFT_NO_GITIGNORE=1`, and
`GRAFT_NO_IGNORE=1`. It removes Graft and common provider API/model variables
from the child environment as defense in depth around the reviewed structural
commands; this is not a network sandbox. It never offers `init`, `--deep`,
`brain`, `mcp`, `upgrade`, or arbitrary passthrough commands.

Graft 0.18.0 has no supported no-update-check flag. A normal build or query may
create or refresh `~/.graft/update-check.json` and contact the npm registry at
most daily. This metadata is the only expected write outside the install and
state paths listed above. It does not contain project source, prompts, model
keys, or Codex authentication.

Do not run the package binary directly for routine use. In particular, do not
run `graft init`; upstream documents that it can write repository instructions,
hooks, and user-level Codex configuration.

## Verification

Installation and the wrapper are verified with a synthetic repository under the
Graft state directory. No Pinky repository was indexed.

- `graft --version`: `0.18.0`
- npm production dependencies: 45
- `npm audit`: 0 known vulnerabilities at every severity
- Synthetic build: 2 JavaScript files, 4 graph nodes, 4 edges, 2 cards
- Synthetic query: found `authorizeSession` and its `handleRequest` caller
- Visualization probe: HTTP 200 on `127.0.0.1:45440`, graph schema 1 with 4
  nodes and 4 edges; the foreground process was then stopped
- Fixture source SHA-256 values were identical before and after build/query:
  `6460d181d0cd84cf4d36baa21ed19af344a00fea7a32354f8738910e475ba0a7`
  and `9e4861d3acd6f9fa8375aefb4cc97b79d2daf1ad24f2b842885797b67083ce2b`
- No `.gitignore` or `.ignore` was created in the fixture
- The expected `~/.graft/update-check.json` was the only observed
  write outside the owned install, state, wrapper, and documentation paths
- An eight-worker isolated regression observed at most one active writer,
  retained valid metadata with no temporary files, confirmed all three required
  environment flags and provider-key removal, and left the existing graph at
  SHA-256
  `a65e9540f9b27286af93c7eff59383ebab5d7b18bfa9250b5f3942b8b0e1134e`

Because lifecycle scripts were disabled, the package's nested Kotlin parser had
no native binary for Node 24 on macOS arm64. Its small local binding target was
inspected, then compiled from the installed package source with npm's bundled
`node-gyp` 11.2.0 and the installed Node 24.1.0 headers. No package lifecycle
script or downloaded build helper was run. The resulting binding SHA-256 is
`03be162de9ca93cb37d4b76498499cc60e2b3e78db8257347f98f9d03edcaa59`.

The exact dependency lock SHA-256 is
`2c4d3d56f1ff74a50d2e31aa40e9fe23ed9e30d941cce4b0516fe8138a27ad93`.
