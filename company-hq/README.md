# Company HQ

An isolated local workspace combining the actual Agent Teams AI graph package,
ClawTeam tasks/inboxes, Ruflo decision memory and native Codex execution.

All application changes are outside product repositories. Connecting a workspace
records its existing folder. Starting the supervisor executes the user's stated
request in that folder through native Codex, with per-action approvals when
requested. No alternate account home or credential copying is used.

## Build

Use Node 24 or newer. Install exact dependencies with `npm ci --ignore-scripts`
and build with `npm run build`. The graph source is retained in
`vendor/agent-graph`, not fetched implicitly. Browser builds target current
Chromium used by Codex. The live local server is the shared toolkit's
`clawteam/integration/secure_board.py`; run `team-ui` to start/reuse it.

The HTTP layer serves the built `dist` directory and guarded APIs from
`clawteam/integration/hq_api.py`. Runtime integration and tests are described in
`clawteam/integration/CODEX-BRIDGE.md`. Build dependencies are isolated under
`deps/node_modules` on this installation, linked as `node_modules`.

## License and source

Company HQ frontend and adaptations are distributed under AGPL-3.0-only;
see LICENSE. Agent Teams AI graph and avatar assets are copyright © 2026
Илия (777genius), retained from c2e9212e7a1a8daed34d7464432fc18eec62b238.
See vendor/UPSTREAM.md. ClawTeam components retain their MIT license.
The software is provided without warranty. The interface's How this works
panel links to a local source archive including this app's source, graph/assets,
licenses, build configuration and integration source. No accounts, model
conversations, bindings, user project files or private state belong in that archive.
