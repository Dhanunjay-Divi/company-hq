# 2026-09-25 — Provider sign-in and desktop startup

The Claude connection sheet previously offered “Begin sign-in” when only
Claude Desktop was present. Opening that app did not establish a Claude Code
runtime, yet the modal still presented a long activity log and an ambiguous
“Not installed” account row. The same installed-versus-ready confusion could
affect other providers. This round keeps provider-owned login and credentials
in the official clients. HQ now shows one useful next step: official runtime
setup if the adapter is unavailable, otherwise native sign-in and connection
check. Desktop launch is an optional action under details and is no longer
described as an HQ sign-in. Diagnostics and the last five activity entries are
behind a disclosure. Provider inventory preserves desktop presence even when a
runtime probe reports that no CLI is installed; native connect actions reject
an unavailable runtime before launching a login process.

An attached macOS crash report showed an abort during Tauri startup. A local
reproduction exposed the underlying error: another, orphaned development
backend held the private app-data lock, so the packaged backend exited without
printing its loopback address. Tauri then panicked because the setup hook
returned an error. The shell now detects early backend exit, recognizes this
known lock conflict, and navigates to a bundled recovery page instead of
returning a setup error. Raw backend diagnostics are not shown in the UI. The
orphaned backend was stopped cleanly after verifying it was idle and had no
responsive HTTP endpoint.

Verification: the full model-free check passed 23 discovery, 35 root and 317
integration tests plus JavaScript, source-bundle and portability checks.
Focused provider tests passed after the final readiness guard. The browser
acceptance flow passed with synthetic transports through settings, tasks,
folders, planning, permissions and Full access. `cargo check` and the Vite
production build passed. A packaged macOS app showed the recovery page for the
lock conflict without aborting, then launched normally after the stale backend
was stopped. The native Claude sheet showed the setup guide and did not offer
sign-in without a ready Claude Code runtime. The 0.1.1 DMG passed `hdiutil
verify`; its SHA-256 is
`2a3e60de9a93988cae3cda042168cfa4217eae6e1924695e22b49f85f0a86371`.

No model turn or provider login was attempted. Live Claude, Kimi and Z Code
authentication on another account remains unverified; the available coding
runtime and entitlement depend on that user's provider installation. The
macOS artifact remains unsigned and unnotarized; Windows and Linux bundles
were not built. This round changed the local source build and the packaged
artifact, not customer projects or account files.
