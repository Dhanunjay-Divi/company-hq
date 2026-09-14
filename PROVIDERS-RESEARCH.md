# Provider launcher research

Verified 2026-09-13. This is a control-surface inventory, not an installation or authentication record. No model request was run and no credential/session file was read.

## Local availability

| Adapter | Local state | Version evidence |
|---|---|---|
| Codex | available at `/Applications/ChatGPT.app/Contents/Resources/codex` | `codex-cli 0.154.0-alpha.6.2`; `codex --version` |
| Ollama | client available at `/opt/homebrew/bin/ollama`, server unreachable during the check | client `0.9.0`; `ollama --version` |
| Claude Code | unavailable (`claude` absent) | use `claude --version` after installation; upstream latest observed: `v2.1.269` |
| Cursor Agent | unavailable (`agent` and `cursor-agent` absent) | use `agent --version` after installation |
| Kimi Code | unavailable (`kimi` absent) | use `kimi --version`; upstream latest observed: `0.42.0` |
| OpenCode | unavailable (`opencode` absent) | use `opencode --version` |
| Grok Bot | GUI app installed, no documented/bundled CLI found | app `0.47.0`, bundle `com.anysphere.sand`, signed by Anysphere; URL schemes `grokbot` and `sand` |

Grok Bot contains one executable, `/Applications/Grok Bot.app/Contents/MacOS/Grok Bot`, plus Electron `app.asar`. The registered URL schemes establish app navigation only. They do not establish model selection, working-directory launch, headless execution, or a provider API. Keep Grok Bot UI-only until Anysphere publishes a control contract or ships a CLI.

## Verified adapter surfaces

### Codex

- Inspect: `codex --version`, `codex --help`, `codex exec --help`.
- Launch: `codex exec -C <project> -m <model> --json "<prompt>"`; use `--ephemeral` when the caller explicitly wants no saved session.
- Model discovery: this CLI build exposes no `models` command. The Codex desktop host supplies an account-specific supported-model set to its native task tools; outside that host, treat model availability as unknown until a supported catalog surface is available. The public API model catalog describes API offerings and does not prove Codex account access.
- Current OpenAI guidance says `gpt-6-astra` for the hardest work, `gpt-5.6-terra` for balanced work, and `gpt-5.6-luna` for cost-sensitive volume. `gpt-5.6` is an alias for `gpt-5.6-sol`; prefer explicit IDs when reproducibility matters. Source: [OpenAI model catalog](https://developers.openai.com/api/docs/models), [Codex releases](https://github.com/openai/codex/releases).

### Claude Code

- Inspect: `claude --version`; readiness can use the vendor-supported `claude auth status` without opening credential files.
- Launch from the project as the subprocess working directory: `claude -p --model <alias-or-full-id> --output-format stream-json "<prompt>"`. The general session command has no documented `--cwd`; `--cwd` in the CLI reference belongs to `claude agents` filtering.
- Discovery: `/model` is interactive. There is no documented noninteractive general account-model listing command. Aliases `best`, `opus`, `sonnet`, and `haiku` move to recommended/current provider versions; a full model ID pins the choice. `default` is account-tier dependent and can fall back. Source: [Claude CLI reference](https://code.claude.com/docs/en/cli-usage), [model configuration](https://code.claude.com/docs/en/model-config), [releases](https://github.com/anthropics/claude-code/releases).

### Cursor Agent

- Inspect: `agent --version` (current primary entry point); `cursor-agent` is retained as a compatibility alias.
- Launch from the project as the subprocess working directory: `agent -p --model <catalog-id> --output-format stream-json "<prompt>"`. No working-directory flag is documented.
- Discovery: `agent models` or `agent --list-models` was added in January 2026; current interactive selection uses `/model` (the later changelog removed `/models`). Treat returned names and `Auto` as live account catalog values, not stable version pins; Cursor promises access to current models but does not document stable alias semantics for every vendor model. Source: [Cursor CLI overview](https://cursor.com/docs/cli/overview), [parameters](https://docs.cursor.com/en/cli/reference/parameters), [model-list changelog](https://cursor.com/changelog/cli-jan-08-2026), [current `/model` behavior](https://cursor.com/changelog/cli-jan-16-2026).

### Kimi Code

- Inspect: `kimi --version`; `kimi doctor` validates configuration but is not a model catalog command.
- Launch with the project as subprocess working directory: `kimi -m <configured-alias> -p --output-format stream-json "<prompt>"`. Current Kimi Code starts in the current directory and has no documented `--work-dir`; that flag belonged to the older `kimi-cli` documentation.
- Discovery: `/model` selects configured aliases; `/provider` or `kimi provider` manages/imports providers and models. Managed login provisions aliases. A custom provider import does not set a default automatically. Model aliases are configured mappings, so refresh and review their target metadata rather than assuming an alias means “latest.” Current release observed: `0.42.0` (2026-09-09). Source: [Kimi command reference](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/reference/kimi-command.md), [provider reference](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/providers.md), [releases](https://github.com/MoonshotAI/kimi-code/releases).

### OpenCode for GLM or Kimi

- Inspect: `opencode --version`.
- Discover: `opencode models [provider]`; use `opencode models --refresh` to refresh the Models.dev cache. Output is `provider/model`; `--verbose` adds metadata.
- Launch: `opencode run --dir <project> --model <provider/model> --format json "<prompt>"`. Add `--pure` for discovery/launches that must exclude external plugins.
- OpenCode documents Moonshot AI and Z.AI (including the GLM Coding Plan) as provider choices. Exact provider/model identifiers must come from the installed CLI's refreshed catalog; do not synthesize IDs from display names such as “GLM-4.7” or “Kimi K2.” Source: [OpenCode CLI](https://opencode.ai/docs/cli/), [providers](https://opencode.ai/docs/providers), [models command source](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/cli/cmd/models.ts).

## Provider-neutral contract

Each adapter should report structured capabilities: `installed`, `version`, `ready_status_command`, `catalog_command`, `catalog_age`, `model_ids`, `alias_semantics`, `cwd_mode`, `noninteractive_command`, `stream_format`, and `supports_native_teams`. Discovery may run documented version/help/catalog/status commands; it must never parse credential or session files.

At project kickoff, and during a reviewed maintenance pass, refresh only the catalogs of installed adapters. Choose a supervisor from models that are both returned by the live adapter and allowed by a human-reviewed workload policy. Do not choose by lexical version sorting and do not hardcode Astra forever. Record the selected provider, exact returned model ID or deliberately dynamic alias, CLI version, and discovery time with the run.

Native Codex collaboration can select only the Codex host's advertised model IDs. It cannot turn a Codex subagent into Claude, Cursor, Kimi, GLM, or Grok. Those require their own CLI process and a separate handoff/activity bridge. Until that bridge exists, use native Codex teams on demand and add one external adapter only when a project has a concrete benefit that justifies its install, account, permissions, and operational surface.
