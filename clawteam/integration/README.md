# Company HQ and ClawTeam coordination

Company HQ reuses the actual Agent Teams AI graph package for the team map and
uses ClawTeam 0.3.0's task store and file inboxes for coordination records. Ruflo
holds shared decision memory. Native Codex remains the only agent executor: after
an approved workspace is attached, the UI can start, continue, or stop its
supervisor and present native runtime approval requests for user review. Creating
a ClawTeam task or delivering an inbox message does not launch, wake, interrupt,
or steer a Codex task automatically. Agents check inboxes at safe checkpoints.

ClawTeam is upstream work from HKUDS, distributed under the MIT License. The
pinned source and license are retained in `clawteam/upstream`; the adapted HTML
in this directory is derived from its shipped board UI.

## Launch

```sh
team-ui
team-ui status
```

Port `0` selects an available non-default loopback port and prints the URL. The
server accepts only exact localhost Host headers, requires a matching Origin on
POST requests, omits broad CORS, and disables upstream's GitHub proxy. State is
fixed at `/Users/uno/.local/share/agent-toolkit/clawteam/state`.

`~/.local/bin/team-ui` points to the owner-private launcher. Repeated starts
reuse a healthy tracked server. `team-ui stop` only signals a process whose
command line matches this exact secure-board script.

The served UI is the Company HQ build under `company-hq/dist`. Its graph source
is retained under `company-hq/vendor/agent-graph`; its board and inbox views read
ClawTeam's guarded local APIs. Delivery responses say `delivered_to_inbox` and
`wakes_agent: false`. Native runtime controls and approval payloads are documented
in `CODEX-BRIDGE.md`. The full Agent Teams AI application runtime remains blocked
because it substitutes account-home state and manages authentication artifacts.

## Safe CLI

Use `integration/clawteam-meta` for team definitions, tasks, inboxes, and terminal
board views. It has a strict command allowlist; spawn, launch, runtime, hooks,
plugins, harnesses, sessions, and upstream `board serve` are disabled. The facade
also disables config-loaded event hooks and Redis wakeups, fixes transport to the
local file store, and never writes `~/.clawteam/config.json`.

Examples:

```sh
clawteam/integration/clawteam-meta team create product-team overall-head \
  --leader-id codex-task-id --description "Actual team definition"
clawteam/integration/clawteam-meta team add-member product-team engineering-head \
  --agent-id codex-task-id --agent-type supervisor
clawteam/integration/clawteam-meta task create product-team "Review release gate" \
  --owner engineering-head
clawteam/integration/clawteam-meta inbox send product-team engineering-head \
  "Please report the gate result" --from overall-head
clawteam/integration/clawteam-meta inbox receive product-team \
  --agent engineering-head
```

`CLAWTEAM_USER` defaults to `local`. Set a stable value before team creation when
multiple local identities need separate inbox namespaces.

## Company map and everyday use

The dashboard opens on the team map. Choose a project/team, select a person to
see their assigned work and conversation, then leave them an inbox message.
Messages from the dashboard are attributed to `user`; agents keep their own
identity when replying with the safe CLI. Task creation records a request and
does not itself start a model. Give a new project idea or immediate direction
in the supervising Codex conversation, which creates and steers actual agents.

Reporting lines and model labels are explicit recorded metadata, not inferred
from messages or proof of liveness. Before displaying a team, its supervisor
records the actual assignment hierarchy under the external state directory:
use `company_profile.profile_path(state, team_name)` to locate the JSON and
`validate_profile(value, registered_member_names)` before writing atomically
with private permissions. The shape is:

```json
{
  "projectLabel": "Readable project name",
  "goal": "Customer outcome for this effort",
  "members": {
    "head": {"displayName": "Overall head", "department": "Direction", "model": "Actual dispatched model", "reportsTo": null},
    "research": {"displayName": "Research lead", "department": "Customer research", "model": "Actual dispatched model", "reportsTo": "head"}
  }
}
```

Use registered member names; unknown models stay blank and unknown reporting
lines stay unset. Cycles and cross-team references are rejected. The current
integration team represents real setup work, not a fictional staffed company.
Other projects get their own team, metadata and task records when real work starts.
