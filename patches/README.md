# Historical Agent Teams AI compatibility patch

Base: https://github.com/777genius/agent-teams-ai at `c2e9212e7a1a8daed34d7464432fc18eec62b238`.

This patch preserves seven custom source/test files, including two originally untracked tests. It is **inactive reference material**, not the runtime used by Company HQ. The full upstream application remained blocked after compatibility work because its opaque runtime's account-home/auth behavior was unresolved. Never enable it merely because this patch exists. Preserve AGPL attribution.

Apply only in an isolated checkout of the exact base, inspect source and test before considering adoption. Current Company HQ instead uses the native Codex bridge and upstream graph package.
