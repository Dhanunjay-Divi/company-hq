# Provider runtimes

Company HQ is the control plane, not an account gateway. Every adapter uses the
provider's official local client and inherits `HOME`, provider configuration,
and sign-in state. It does not copy credentials, substitute API keys, read chat
history, or claim that application detection is a live connection.

## Runtime contract

`create_runtime(provider, ...)` returns a provider adapter with this interface:

- `start(prompt, project, model, images)` starts or resumes one project-bound
  session, performs its protocol handshake, and accepts the first turn.
- `send(prompt, images)` accepts another turn on the persistent transport.
- `respond(request_id, response)` answers a native permission or question.
- `set_access(plan|workspace|full)` applies the explicit per-chat access choice.
- `stop()` interrupts queued/running work and closes the child process.
- `status()` exposes bounded connection, session, model, access, and capability
  metadata; `events(after)` returns a 300-record monotonic in-memory ring.

Accepted user turns and assistant events include a local `turnId` and stable
`itemId`; Claude's native assistant message ID replaces the provisional item ID
when it arrives. Events also carry `sessionId`. The HQ provider hub adds the HQ
chat/team identity and persists records it needs for restart replay. Hub status
includes `providerBound`; once true, a chat cannot be resubmitted through a
different provider even if the native process is offline or the first turn
failed after its provider binding was saved.

All event payloads are recursively bounded. Provider stderr is drained but not
put in replay because it can contain private source context. A
`runtime.started` event proves a successful transport handshake, not remaining
quota, a completed model turn, or a provider charge.

## Claude Code

Claude runs through the official persistent bidirectional stream-json protocol:

```text
claude -p --input-format stream-json --output-format stream-json --verbose \
  --replay-user-messages --permission-prompt-tool stdio
```

On every process launch Company HQ sends an SDK `initialize` control request
before the first user message. Its response supplies the actual available model
rows and pending permission requests. The adapter never invents a static model
catalog. It records the `system/init` session ID, and a later process launch
uses that ID with `--resume`.

Claude tool permission prompts arrive as `control_request` records with subtype
`can_use_tool`. They remain pending until `respond` sends the matching
`control_response`; duplicate, cancelled, and stale IDs fail closed.
`AskUserQuestion` is surfaced as `question.requested`, and structured answers
are returned in the tool's `updatedInput.answers`. Other unimplemented control
request subtypes receive an explicit error response so the CLI does not
deadlock or silently gain authority.

When a resumed session reports an already-pending permission in its initialize
response, the adapter assigns a deterministic recovered turn identity bound to
that native session and request. HQ can then approve or reject the request once;
it does not treat an unrelated replay record as permission authority.

Text and PNG/JPEG/WebP/GIF images are sent as Anthropic message content blocks.
HQ-resolved image files or validated base64 records are accepted, up to 6 MiB
each. Attachment bytes never appear in runtime events.

Access maps as follows:

| HQ choice | Claude launch/runtime behavior |
| --- | --- |
| Plan | Native `--permission-mode plan` |
| Workspace | Native default/manual permissions, bound to the selected cwd |
| Full | Explicit launch-time `--allow-dangerously-skip-permissions` plus `--permission-mode bypassPermissions` |

Workspace mode is accurately described as **Native permissions**. The cwd is a
project binding, not an OS filesystem sandbox. Claude Code's native boundary
checks and HQ's visible permission responses remain active. Full access is only
enabled by an explicit per-chat selection before process launch. Any transition
into or out of full access restarts the native process, so a workspace downgrade
cannot retain the launch-time bypass flag.

`probe()` uses only `claude --version` and `claude auth status --json`. It
returns sanitized installed/auth/version metadata and an empty model list;
models become available only after the real initialize handshake. Login is the
official interactive `claude auth login` command returned by `login_command()`.
The UI host must run it in a PTY and may expose only validated provider URLs and
bounded status metadata. The adapter does not automate login.

The reviewed source-checkout dependencies are installed locally and ignored by
git:

- `build/providers/claude-code`: `@anthropic-ai/claude-code@2.1.278`
- `build/providers/claude-agent-sdk`: `@anthropic-ai/claude-agent-sdk@0.3.278`

The runtime uses the official Claude Code binary. The SDK package is both the
pinned protocol/type reference and the provider metadata/session implementation
used by HQ's native-task adapter. Recreate the source-checkout install without a
global package:

```sh
npm install --prefix build/providers/claude-code --ignore-scripts --no-audit --no-fund --save-exact @anthropic-ai/claude-code@2.1.278
node build/providers/claude-code/node_modules/@anthropic-ai/claude-code/install.cjs
npm install --prefix build/providers/claude-agent-sdk --ignore-scripts --no-audit --no-fund --save-exact @anthropic-ai/claude-agent-sdk@0.3.278
```

The desktop builder stages the pinned platform-specific Claude binary and Agent
SDK as provider dependencies. They continue to inherit the user's account home;
the package does not copy, bundle, or rewrite provider credentials.

## Ollama

Ollama uses local `/api/chat` with streaming enabled. It keeps the successful
user/assistant history for later turns, emits turns asynchronously, and closes
the active HTTP response on stop. Generation IDs suppress late completion or
error events after cancellation. The adapter never routes to a paid API.

Ollama image input is currently reported unsupported because model-specific
image capability discovery and mapping have not been integrated.

This adapter is implemented and fixture-tested at the runtime layer, but the HQ
provider hub and current desktop provider picker do not advertise it as an
available chat provider. Hub availability remains limited to the reviewed Codex
and Claude end-to-end paths.

## ACP providers

The generic `AcpRuntime` exercises the core JSON-RPC sequence against a
deterministic fixture, but generic ACP is not advertised as provider readiness.
Cursor, Kimi, and Z.ai remain `UnavailableRuntime` through the provider registry
even when an arbitrary command is supplied. A direct ACP instance requires the
explicit `experimental_acp=True` escape hatch and reports
`support=experimental_fixture_only` / `verifiedProvider=false`.

Each named ACP provider needs a provider-specific reviewed executable, protocol
version, account behavior, permission mapping, images, resume, cancellation,
and live acceptance before Company HQ can mark it connected.

## Verification boundary

The automated fixture drives the actual stdin/stdout wire for initialize,
models, text and image messages, multiple turns, permission and question
responses, resume, access changes, interrupt, and stop. It also checks the
pinned official CLI's `--version` and `--help` when the ignored dependency is
installed. These checks make no model request. A separately authorized live
account run is still required to establish provider entitlement, quota, and
real-model behavior.

Protocol reference: the pinned official Agent SDK `sdk.d.ts`, plus the official
[Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
and [Agent SDK documentation](https://docs.anthropic.com/en/docs/claude-code/sdk).
