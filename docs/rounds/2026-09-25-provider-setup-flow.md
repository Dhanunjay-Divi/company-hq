# 2026-09-25 — Provider setup that leads somewhere

The 0.1.1 Claude sheet used an external link for “Set up Claude Code.” In the
packaged app this could appear to do nothing, and it did not tell the user
which command to run or when HQ could check the connection. Claude Desktop
presence alone was insufficient for the official Claude Code CLI adapter.

The sheet now gives numbered install, sign-in and check steps. Claude and Kimi
show current official macOS/Linux commands in selectable text with Copy and
Open Terminal actions. Official setup guides open through a bounded macOS
backend action instead of relying on a webview pop-up. Codex and Z Code show
their official guides where a single portable CLI command is not appropriate.
On a Mac with Homebrew, Claude also offers an explicit approval dialog before
HQ runs the fixed `brew install --cask claude-code` command. Installation runs
without a shell, reports progress and failure, and checks Claude's CLI after
completion; the user still signs in with the provider. Normal Claude CLI
discovery now includes its standard native and Homebrew paths. The installer
never reads or copies provider account files.

Verification: the focused 28-test provider/API suite and full model-free check
passed. Browser acceptance exercised the guide, Terminal and approved-install
routes with a synthetic provider, then observed the sign-in step; it never
installed a real provider or used a model. The Vite production build passed.
Actual Homebrew installation and provider sign-in on another user's Mac remain
unverified. The packaged 0.1.2 backend reported the setup inventory and
rejected an unapproved install request. `cargo check`, desktop package
contracts, and `hdiutil verify` passed. The DMG SHA-256 is
`5f7401837fe5c0f582903cbf7e279938e23897d869d0b63593b24fdac06cee32`.
The macOS package remains unsigned and unnotarized.
