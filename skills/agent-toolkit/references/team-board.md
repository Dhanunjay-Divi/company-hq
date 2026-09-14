# Native team workflow

The shared Agent Team Board at
`/Users/uno/.local/share/agent-toolkit/teamboard/Agent Team Board.app` is a native
macOS viewer. It refreshes recorded activity every two seconds, makes no model
calls and has no network server. Native Codex tools perform the actual work
and communication. The board records concise workflow summaries, not every
internal message. Recorded state is not proof that a process is still running.

The executable is `/Users/uno/.local/bin/agent-team`; its source is
`/Users/uno/.local/share/agent-toolkit/teamboard/agent_team.py`.

## Starting and recording

When the parent or launcher provides a run UUID, reuse it. Otherwise call
`agent-team start --project <absolute-directory> --title <short-title>` and
read the returned `run_id`. This writes only external state and starts no
model workers. For simple tasks, skip the board unless the user wants it.

Use the following commands with actual observed values. Prefer structured
subprocess argument arrays; if using shell strings, quote arguments safely.
For message text `--text -` accepts stdin. Do not pipe untrusted text as code.

```text
agent-team agent --run UUID --id scout --name Scout --role Explorer --model gpt-5.6-luna --task "Bounded assignment" --runtime-id ACTUAL_ID --status running
agent-team update --run UUID --id scout --status completed --summary "Observed result and evidence"
agent-team message --run UUID --from lead --to scout --delivery sent --text "Sanitized summary of a message already sent with native tools"
agent-team finish --run UUID --status completed --summary "Result, verification and remaining limits"
agent-team status --run UUID
agent-team view
```

Register the lead as well, with its actual current model, or `unknown` if not
available. The recorder accepts provider/model IDs and `unknown`; labels report
observed configuration and do not prove that a provider is integrated.
Model labels are reported configuration, not measured provider usage.
Only register agents after a successful native dispatch; use the returned
runtime ID. Use queued for work that hasn't started and running only after
dispatch. If an agent fails or is stopped, record that explicitly. Finishing
requires every agent to be reconciled to completed, failed or stopped. A
failed attempt remains a recorded event after a later retry succeeds.

Use `coordinator`, `team`, `user`, or registered IDs as message endpoints.
`message` does not send anything. Call native `send_message`, `followup_task`,
or `spawn_agent` first, then record a short sent summary; record received
results after receiving them. `--delivery note` is for notes without delivery.
Parent-mediated handoffs are normal; do not fabricate peer-to-peer traffic.

State lives outside product repositories at
`~/.local/share/agent-toolkit/teamboard/runs/<UUID>/state.json`, with private
file permissions, serialized atomic updates, and the latest 500 events per
run. Older events are counted as trimmed. No automatic OS startup service,
MCP registration, account synchronization or transcript scraping is installed.
If the journal is unavailable, report the visibility gap and keep using the
native Codex task UI; don't block authorized product work on logging.

## Reusable launcher

For a user who wants a new **CLI session** for a project:

```text
agent-team work --project /absolute/project "Describe the task"
agent-team work --project /absolute/project --model gpt-5.5 "Describe the task"
```

`work` opens a native interactive Codex process, with `--model auto` selecting
the current reviewed, available Codex supervisor (currently Astra/high), and a
run ID in its prompt. It uses the existing native
Codex login and existing permission settings. Unlike `start`, it launches a
model task and can perform the requested project changes. Do not invoke it
inside an already-running Codex task simply to nest another lead: use native
subagents in the current task. `routing.json` and `discover.py` make supervisor
selection evolve rather than permanently pinning Astra. `--reason` is optional
context, not a required approval step. Supporting agents
still default to Terra/medium. Delegate routine execution to smaller workers.
A CLI process exiting zero is not recorded as completed unless its workflow
recorded a final outcome; unresolved exit state is marked blocked for review.

The installed personal roles are `team-scout` (Luna/low), `team-builder`
(Terra/medium), `team-reviewer` (Sol/high), in `~/.codex/agents/`. When the
available collaboration API lacks named role selection, pass its equivalent
model and role instructions in a bounded prompt.

## Project rules and tool selection

Follow the project's operating skill and instructions, including `pinky-ops`
for Pinky. Use separate worktrees for conflicting simultaneous writers. Team
setup never initializes a product repository, installs hooks, changes auth or
permissions, or authorizes deployments. See the shared `GUIDE.md` for upstream
tool decisions; `GRAFT.md` covers optional external code graph indexing.
