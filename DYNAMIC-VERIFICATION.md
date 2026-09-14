# Dynamic policy follow-up — 2026-09-13

User steering supersedes permanent Astra selection: choose the best reviewed
available supervisor over time and initialize useful teams automatically for
any project. The later value discussion favors a lean implementation rather
than speculative integration with every provider. For Pinky, `pinky-ops` and
product rules still apply; this follow-up changed no product files.

- `routing.json` is the maintained preference, rather than a permanent model
  ID in the launcher. Current verified supervisor is Codex GPT-6 Astra/high.
- `discover.py` obtains native `model/list` without launching inference, records
  installed client capabilities, caches for 24h, follows verified available
  official upgrade hints, and flags unreviewed models. It does not lexically
  rank model names or claim a universally measured best model.
- `agent-team work` now defaults to `--model auto` and verifies explicit models
  against the available Codex catalog. The recorder accepts future/provider
  model labels without pretending they are executable through Codex.
- `kickoff.py --project <path>` ran successfully against Pinky: cached model
  selection, all catalog metadata available, default unchanged, no workers
  launched and no product initializer. It synchronizes a changed managed
  supervisor default for future tasks while preserving manual changes.
- Live capability check: Codex catalog verified; Ollama client detected (server
  unavailable in the separate provider check); Claude/Cursor/Kimi/OpenCode/
  Grok/GLM CLIs not installed. Grok Bot is desktop-only for this toolkit.
  Other providers are future integration candidates, not enabled workers.
- Weekly Sunday 09:00 local Codex heartbeat created and viewed successfully:
  `maintain-shared-agent-toolkit`. It follows `MAINTENANCE.md`, reviews useful
  candidate updates, stages/tests before activation and keeps rollback. It
  stays quiet for unchanged/non-actionable state. It uses Codex scheduling;
  it is not an always-running OS daemon or a guarantee of immediate updates.
- Seven discovery tests, five existing upstream-checker tests and fourteen
  team/config tests pass: **26 total**. Discovery coverage includes official
  upgrade hints, missing model/client cases, non-lexical selection, reasoning
  compatibility and persistence when policy changes under a cached catalog.
- Skill validation and Pinky runbook checks pass. Final SHA-256 comparison
  still shows all 1,888 Pinky files unchanged and clean Git status.

The first automation create call omitted `destination=thread` and was rejected;
the corrected call created exactly one heartbeat, subsequently viewed. No
failed call is counted as a scheduled automation.

No provider account, subscription or extra CLI was installed. No claim of
automatic universal cross-provider orchestration or measured productivity/token
savings is made. Test the existing setup on real work before expanding it.
