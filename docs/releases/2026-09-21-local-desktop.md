# Local desktop release receipt

Application code checkpoint: `63bd09b0966e4813576c158dff8557873090d4f4`.
This receipt and the updated reusable skill were recorded after the application freeze.

Installed application: `~/Applications/Company HQ.app`.
Open it in Finder, choose New chat and type an outcome. A project folder is optional.
The default mode is Work automatically; broader Full access is a deliberate per-chat choice.

## Verification

- [Model-free CI](https://github.com/Dhanunjay-Divi/company-hq/actions/runs/35675625856): passed on the code checkpoint; 235 Python tests and source/portability checks.
- [End-to-end acceptance](https://github.com/Dhanunjay-Divi/company-hq/actions/runs/35675625839): passed on the same checkpoint. Real UI and HTTP APIs with a synthetic native provider, including image replay, account-window percentages, task metadata, native approvals, full access and narrow layout.
- Six JavaScript regressions passed; Rust cargo check and desktop build passed.
- Frozen backend launched from a temporary working directory with isolated state. Its bundled frontend/routing, decision catalog and source archive responded successfully. No model prompt was sent. SIGTERM shutdown exited 0 in 0.811 seconds.
- Native app restored an existing fixture chat, unsent text and Beads tasks across random loopback ports. The earlier quit failure was fixed and retained in the acceptance history. Final Command-Q closed its listening port and both owned backend processes; reopening succeeded. The app was left at a clean New chat screen.
- Installed launcher and sidecar hashes exactly match the build artifacts below.
- The installed agent-toolkit skill and portable copy now describe the current app, canonical Beads board, scoped memory and native worker controls. Both passed the skill validator. The previous installed skill was retained under the app's private skill-backups directory. No product repository or provider account configuration was changed.
- The repository remains private, with direct tested commits on main. No production deployment or PR was created.

## Artifact identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Bundled backend, macOS arm64 | 409923104 | `a76e0c5f061eaf6d0dfefbc16410956bd2a2bc43e1396c95e40891830e16d437` |
| DMG, macOS arm64 | 403802617 | `676d104ca9fa8cf36b0aa5e00eed3308c39a4acc03a7bebcd7a9e251e5b12766` |

Rust launcher SHA-256: `136723ebdbc5794d7cb61069e8d054e72c238f83eb083b9054fc2ac5bd01ac66`.
The DMG is at `company-hq/src-tauri/target/release/bundle/dmg/Company HQ_0.1.0_aarch64.dmg` in the source checkout.

## Remaining limits

This is a local macOS arm64 development build, without Apple distribution signing/notarization. Windows and Linux desktop packages are not validated. Claude Code has a tested protocol adapter, but this machine is signed out; a real Claude turn needs the user's login and acceptance. Kimi, Z.ai, Grok, Cursor and Ollama are not verified executable choices in HQ's provider hub. Claude worker hierarchy/control is not verified. Native Codex computer-use access remains subject to plugin and OS permissions; Chrome was exercised, arbitrary desktop control was not. Local microphone recognition requires supported hardware/browser acceptance and is unavailable in the installed WebKit view. Account windows are shown only when reported; local token allowances are not hard spending limits, and prior over-budget HQ runs remain failures. Weekly toolkit maintenance was already paused and was left paused.

See [Usage](../USAGE.md), [Status](../STATUS.md), and [acceptance history](../RELEASE-ACCEPTANCE.md). Do not describe this release as complete parity with every Codex, Claude or third-party provider capability.
