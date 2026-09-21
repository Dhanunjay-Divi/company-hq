# Company HQ native Codex bridge

'codex_bridge.py' owns one native Codex app-server connection per active
ClawTeam team. Import the process-local singleton with:

    from codex_bridge import get_codex_bridge
    bridge = get_codex_bridge(DATA_DIR / "runtime")

The singleton key is the resolved runtime-state path. The default is
'clawteam/state/runtime'. Do not construct one bridge per HTTP request.
The HTTP adapter may use 'from codex_bridge import get_bridge' followed by
'get_bridge(DATA_DIR)'; this convenience export appends the required 'runtime'
directory and returns the same singleton.

The bridge launches exactly:

    /Applications/ChatGPT.app/Contents/Resources/codex app-server --listen stdio://

'subprocess.Popen' receives 'env=None'. The bridge does not set or replace
'HOME', 'CODEX_HOME', auth variables, 'config.toml', MCP configuration, or
command-line '-c' overrides. The native process therefore inherits the user's
existing Codex home and globally registered Ruflo and codebase-memory MCP
servers.

## Python contract

- 'status(team)' returns the current safe snapshot.
- 'start(team, project, prompt, model)' binds the team to one resolved project,
  starts or resumes its persisted native thread, restores any already-approved
  execution mode, and begins a turn. A new binding always starts in read-only
  planning mode; callers cannot request execution directly.
- 'send(team, prompt)' uses 'turn/steer' while a turn is active and
  'turn/start' while the thread is idle. In planning mode, a new follow-up turn
  clears the previous plan-ready flag until that exact turn completes.
- 'begin_execution(team)' is the only plan-to-execute transition. It succeeds
  only after the latest planning turn completed successfully, persists the
  execution binding first, then starts a workspace-write turn.
- 'stop(team)' sends 'turn/interrupt' for that team's exact thread and turn.
- 'approve(team, request_id, decision)' accepts only 'approve' or 'reject'.
- 'events(team, after_seq=0)' returns the bounded event history after a sequence
  cursor.
- 'shutdown_all()' closes child app-server processes during server shutdown.

The intended HTTP adapter is:

- 'GET /api/runtime/{team}/status'
- 'GET /api/runtime/{team}/events?after=N'
- 'POST /api/runtime/{team}/start' with '{ "prompt": "...", "model": "gpt-5.6-luna" }'
- 'POST /api/runtime/{team}/send' with '{ "prompt": "..." }'
- 'POST /api/runtime/{team}/execute' with an empty JSON object after a
  successfully completed plan
- 'POST /api/runtime/{team}/stop'
- 'POST /api/runtime/{team}/approve' with
  '{ "requestId": "...", "decision": "approve" }'

The HTTP layer resolves 'company_profile.projectRoot' and supplies that path to
'start'; a caller cannot provide a project path in the start request body.

## JSON shapes

Status:

    {
      "team": "team-one",
      "state": "running",
      "connected": true,
      "project": "/approved/project",
      "model": "gpt-5.6-luna",
      "mode": "plan",
      "planReady": false,
      "threadId": "native-thread-id",
      "turnId": "native-turn-id",
      "lastEventSeq": 12,
      "pendingApprovals": [
        {
          "requestId": "opaque-id",
          "kind": "command",
          "reason": "Why approval is needed",
          "command": "command shown to the user",
          "cwd": "/approved/project",
          "availableDecisions": ["approve", "reject"]
        }
      ],
      "children": [
        {
          "threadId": "actual-child-thread-id",
          "state": "running",
          "source": "collabAgentToolCall"
        }
      ]
    }

States are 'offline', 'starting', 'idle', 'running', 'awaiting_approval',
'stopping', and 'error'.

Events:

    {
      "team": "team-one",
      "afterSeq": 7,
      "nextSeq": 12,
      "truncated": false,
      "events": [
        {
          "seq": 8,
          "time": 1789344000000,
          "type": "message.delta",
          "threadId": "native-thread-id",
          "turnId": "native-turn-id",
          "itemId": "native-item-id",
          "data": { "text": "streamed text" }
        }
      ]
    }

Event types include 'status', 'thread.started', 'turn.started',
'turn.completed', 'message.delta', 'message.completed', 'tool.started',
'tool.completed', 'approval.requested', 'approval.resolved', 'child.updated',
'usage', 'request.denied', and 'error'. Text events always use
'data.text'. Usage contains numeric counters only. Tool events expose tool names
and status, without raw arguments or results. Child events come only from native
'collabAgentToolCall' or 'subAgentActivity' items and preserve actual thread IDs.

## Boundaries

The first successful start atomically persists an owner-private binding in
'state/runtime/bindings/<sha256(team)>.json'. Later starts must resolve to the
same project. Each team has its own process, request IDs, thread, turn,
approvals, children, and event deque. Concurrent starts and mismatched thread or
turn approvals are rejected.

Threads and turns always request 'approvalPolicy: "on-request"' and
'approvalsReviewer: "user"'. New work starts with a read-only thread/turn
sandbox. Command/file-change approval requests that arrive during planning are
rejected by the bridge and are never surfaced as approvable UI actions. Only
'begin_execution' can persist 'mode: execute'; after that, turns use a
workspace-write sandbox limited to the bound project with network disabled and
normal user-reviewed command/file approvals.

The binding also persists 'planReady'. Only a successful planning-turn
completion sets it true. An interrupted/failed plan stays locked. Starting a new
planning follow-up clears it. Execution persistence occurs before the live
session switches mode, so a binding write failure cannot leave the process more
permissive than durable state. Cross-thread approvals are rejected
automatically. Unsupported permission, elicitation, user-input, client-tool,
token-refresh, attestation, and unknown server requests receive a deny, empty,
decline, failure, or JSON-RPC unsupported response.

Account APIs and account notifications are not called or surfaced. Free-form
text is bounded and common bearer/token patterns are redacted before it reaches
the UI.

The checked-in schema directory was generated by native Codex
'0.154.0-alpha.6.2' using 'app-server generate-json-schema'. Regenerate it after
a native Codex version change and rerun the bridge tests.

The one authorized live Luna smoke has completed. Its receipt is
'clawteam/verification/codex-bridge-luna-receipt.json'. The smoke script refuses
to run again while that receipt exists.

Protocol reference: https://learn.chatgpt.com/docs/app-server
