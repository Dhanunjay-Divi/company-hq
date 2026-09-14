# Agent Teams AI v2.14.2-source native Codex compatibility build

- Source commit: `c2e9212e7a1a8daed34d7464432fc18eec62b238` (`v2.14.2`)
- Source branch: `codex/native-codex-profile`
- App path: `mac-arm64/Agent Teams AI.app`
- Internal app version: `2.1.2` (`CFBundleShortVersionString` and `CFBundleVersion` inherited from the tagged source package)
- App type: local arm64 build, ad-hoc linker signature; the official signed/notarized app under `../upstream/` was not modified
- `app.asar` SHA-256: `504df56e65525aea60da90f2150e593bb0b764fce20c5567c44e0a243f2677f5`
- Bundled runtime SHA-256: `c91e3479f5390235f85a2f9616fa9127742f78452f52779841896ae6ec69c1b1`
- Selected Codex: `/Applications/ChatGPT.app/Contents/Resources/codex`
- Selected Codex version: `0.154.0-alpha.6.2`
- Selected Codex SHA-256: `ecad78dbf98adb89ec475edac86630406cbe59d9f3070b17d88065f136b94bcb`

## Status: UI build complete, execution blocked

The app was built and packaged without being opened. The source-side modern account profile
prevents Agent Teams account snapshots from copying modern account credentials into legacy
`auth.json` and converts every forced token refresh request into a non-refreshing account read.
That protection is useful but does not cover the separately bundled orchestration runtime.

Static inspection of the pinned runtime found that each native Codex turn creates a temporary
`CODEX_HOME`, links or copies entries from the existing Codex home, specially handles `accounts`
and `auth.json`, and deletes the temporary home afterward. That violates the required existing-home,
no-auth-copy execution model. The runtime source repository named by `runtime.lock.json`
(`777genius/agent_teams_orchestrator`, ref `v0.0.95`) is unavailable from this host, and no local
source checkout exists. The compiled runtime was not patched. A source-controlled runtime seam
that invokes the selected native Codex against its existing home is required before launch.

New team dialogs default Auto-approve tools to off. An explicitly saved or selected true value
is still honored. In approval mode the bundled runtime uses Codex app-server with on-request
approval, user review, and a read-only sandbox. It only selects approval-never and
danger-full-access when the user explicitly enables Auto-approve tools.

The bundled runtime creates a temporary Codex home for each native Codex turn and intentionally
does not copy `config.toml`. It translates the app-generated MCP JSON into Codex `mcp_servers.*`
overrides. Global Codex MCP registrations therefore are not inherited automatically; Ruflo and
codebase-memory must be present in the app-generated MCP policy/config if they are required in an
Agent Teams run.

Agent Teams' bundled runtime, IPC, and MCP layer must own any future in-app spawning so its agents
remain connected to the team board and runtime state. A second native collaboration tree would be
disconnected from that state.

## Updater behavior

The local directory build contains no `Contents/Resources/app-update.yml`, so electron-updater has
no packaged feed configuration. Upstream also sets `autoDownload = false`; checking cannot silently
download an update. An update can only be downloaded through the explicit UI/IPC download action,
after which upstream sets `autoInstallOnAppQuit = true`. Because this compatibility build has no
feed file and its launcher blocks execution, it cannot be silently replaced by the updater in its
current state.

`launch-native-codex.sh --print-config` is read-only. Every other invocation exits with the runtime
blocker and never starts the app. It also refuses if the selected native Codex binary hash changes.
