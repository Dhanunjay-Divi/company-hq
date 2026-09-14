# Team extension verification — 2026-09-13

**Current model policy:** after initial acceptance below, the user explicitly
requested GPT-6 Astra as supervisor. The installed default and CLI launcher
were updated to Astra/high; supporting agents remain Terra/medium with
Luna/Sol specialist roles. Earlier Sol-lead verification below is historical
evidence, superseded only for the selected lead model and effort.
Follow-up verification passed: the installed CLI's strict `config/read`
returned Astra/high, Terra/medium and the three-worker cap. The same 14
team/config regressions passed after the change, as did skill/runbook checks.
The project working tree remained clean.

This extends the earlier staged toolkit. It does not retroactively change the
earlier Ruflo/runtime findings. For Pinky work, follow `pinky-ops`; no Pinky
product files or releases were changed by this extension.

## Installed and observed

- Original native SwiftUI Agent Team Board compiled successfully for macOS 13
  on this Apple Silicon Mac. Info.plist lint, executable inspection and build
  script syntax checks passed. The app has no network listener/model calls;
  it reads only shared toolkit run JSON. No startup service was installed.
- Live UI acceptance through native accessibility and screenshots: actual
  three-agent setup run, tasks, model labels, messages and completed reviewer
  shown; Messages filter and Graft search returned the correct recorded
  communication. Relative times update, completed agents show Final update,
  and last-reported state is distinguished from process liveness.
- Two real native GPT-5.6 Sol agents performed repository evaluation/Graft
  installation and native UI implementation/independent review. This existing
  lead remained GPT-6 Astra; no claim of switching its active model is made.
- Global `~/.codex/config.toml` now selects GPT-5.6 Sol/medium, with supporting
  Terra/medium and a three-agent concurrency cap. The actual installed CLI
  0.154.0-alpha.6.2 accepted and returned these via strict app-server
  initialization and `config/read`, without starting another model task.
- Three personal TOML roles installed: team-scout, team-builder, team-reviewer.
  Existing unrelated parsed config fields were preserved. Original user
  instruction/config files have private backups under `backups/`.
- Global user instructions and discoverable agent-toolkit skill request useful
  native delegation and recorded activity. Skill Creator validation passed.
  Pinky runbook reference check passed. Future invocation is instruction-driven;
  already-running tasks and explicit settings can retain their prior choices.
- Team/config test suite: **14 passed**. Coverage includes real concurrent
  process journal writes, path/symlink rejection, private atomic files,
  no product writes, truncation disclosure, failed-update rollback, process
  ownership after journal failure, preserving completed results, failed spawn,
  config/permission preservation, idempotence, role conflicts, config symlink
  refusal, and serialization of two installer calls.
- Existing upstream checker suite: **5 passed**. All 13 catalog metadata checks
  succeeded, covering the user's eleven repositories and two previously
  tracked entries. Updates remain review candidates, not automatic upgrades.
- Graft 0.18.0 installed with exact npm lock; structural build/query and a
  loopback visualization tested against synthetic source. Source files stayed
  unchanged; the test listener was stopped. Zero known vulnerabilities reported
  by npm audit for 45 production dependencies. An additional eight-worker
  wrapper regression proved serialized graph writes and atomic metadata.
  Details and the local Kotlin binding build are in `../GRAFT.md` and its receipt.
- `product-integrity.json` compares SHA-256 for all 1,888 tracked/nonignored
  Pinky files before and after: no changed, added or missing files; clean git
  status. No preprod/prod deployment, release/signing or GitHub Actions run.

## Failures caught during implementation

- `codex --strict-config features list` is unsupported. Configuration validation
  was corrected to strict native app-server `config/read`, which succeeded.
- Independent launcher review found that a journal error after process creation
  could escape before waiting, and that an unresolved run could overwrite a
  completed lead status. Both corrected with focused failing-path regressions.
- Independent path review found run-directory/lock symlink traversal; replaced
  path-following writes with owned directory descriptors and no-follow opens.
- The first hardened concurrent test failed on macOS during simultaneous
  first creation of `.lock`. Corrected by creating the lock once before exposing
  a new run. The same multi-process regression then passed.
- Config symlink refusal initially failed, then passed after explicit rejection.
  Installer invocations now use an advisory lock; this is not a universal
  compare-and-swap guarantee against arbitrary external config editors. Do not
  edit Codex Settings simultaneously with an explicit installer rerun.
- One independent mocked launcher test initially wrote a fixture journal into
  the real run directory because default arguments retained the original base.
  Its Popen was fake; no model worker launched. The original journal is preserved
  in `verification-fixtures/`, outside visible runs. Current regressions pass
  explicit temporary directories. Fixture activity is not represented as real work.
- Graft's disabled install scripts initially left a Kotlin parser binding absent
  for local Node/macOS. After source inspection, the exact installed binding
  was compiled with local headers/tools; the real structural fixture then passed.

## Practical limits

The native board is an event recorder/viewer. Agents must follow the supplied
workflow to record summaries; it does not automatically intercept every native
tool call, cross-task message or transcript. Native Codex remains authoritative
for delivery, controls, live task state and usage. No private reasoning is shown.
Only the latest 500 events per run are retained, with an explicit trim count.

The reusable `agent-team work` interactive launcher has fixture-tested argument
and process/error behavior. A separate interactive paid/model session was not
launched solely to smoke-test it; actual subagent work was tested through this
task's native collaboration tools. Full role discovery in a fresh app task and
future instruction adherence remain subject to that task's loaded configuration.

Ruflo remains staged/inactive. Agent Teams AI, Orkas, DSH, Squad, ClawTeam,
Agent Squad, MeshClaw, codebase-memory-mcp, and the full Agency Agents roster
were not installed. See `../REPOSITORY-DECISIONS.md` for each disposition.
No claim of measured token savings, full audit of all upstream behavior,
Windows UI support or automatic setup in other agent clients is made.
