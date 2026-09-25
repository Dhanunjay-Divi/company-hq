# Native ZCode integration

Company HQ uses the official installed ZCode CLI and its own native login. Credentials remain with ZCode; HQ never reads or copies the credential file. The account/model catalog is observed from initialization, not inferred from desktop presence.

## Compatibility boundary

Reviewed runtime bundle: installed `glm/zcode.cjs` SHA-256 `b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529`. `zcode_standalone.cjs` applies four uniquely matched adaptations in memory. It does not modify the installed application. The native terminal bootstrap starts its standalone credential provider, but the public app-server bootstrap initializes its provider registry without that context. HQ supplies the same public standalone context there, forwards its native headers port, and translates legacy plan mode to the runtime's independent plan flag and snapshot. None reads credentials, bypasses provider authorization, or overrides tool permission decisions. The hash and unique matches must pass; an application update requires review before execution resumes.

`session/create` and `session/resume` preserve project binding. Models are validated against the native catalog. A different model starts a new session with its reported default reasoning level. Completion waits for the native turn count, not an initial idle snapshot. Cumulative session usage is counted once, with cached tokens already included. Kimi/GLM account-wide five-hour and weekly allowances remain unknown unless their supported interfaces report them.

## Upstream provenance

- Source: https://github.com/zai-org/ZCode
- Reviewed source reference: `872ad960de7ec172591f7e1952f7849229f94521`
- License: Apache-2.0; preserved in `licenses/ZCODE-APACHE-2.0.txt`. Small compatibility match fragments derive from the installed release. The full vendor runtime is not redistributed in Company HQ.
- CLI architecture: https://github.com/zai-org/ZCode/tree/main/apps/zcode-cli

## Runtime boundaries

Ruflo and Codebase Memory are attached as scoped native MCP servers. Native provider plugins and skill discovery remain provider-owned. Browser/desktop host callbacks are not silently forwarded to a different provider or granted OS permissions. Native approvals and questions must be surfaced to the user. The known ZCode version is intentionally pinned rather than automatically activating unreviewed protocol updates.
