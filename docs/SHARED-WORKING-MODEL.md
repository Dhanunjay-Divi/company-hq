# One project context, accountable teams

The user gives goals to the outer Codex reviewer for now. That reviewer leads delivery, dispatches bounded work through Company HQ, reviews evidence and decides which model or integration upgrades to activate. HQ's supervisor coordinates useful department leads and specialists beneath that direction. A newly connected or newly discovered model does not replace the supervisor automatically.

## Shared source of truth

- **Work:** the existing canonical Beads board for the HQ workspace. Native workers and department leads refer to its task IDs. Recorded tasks are not proof that agents are running or tests passed.
- **Decisions:** project-scoped Ruflo memory, linked to source files and verification evidence. Memory is not another scheduler and does not hold credentials.
- **Skills:** one reviewed library, served on demand through `hq_skills` and `hq_skill_read`; Codex client tools and the other providers' context MCP call the same implementation. The Agency Agents library is reference guidance, not 100 automatically running models. Load only the relevant role.
- **Code:** the actual checkout is authoritative. Codebase Memory is the structural index; optional Graphify/Graft references are not additional source repositories. Refresh an index when its source changes.
- **Delivery:** `docs/rounds/` records each meaningful round, including observed failures, corrective work, checks and remaining gates. The release record distinguishes fixtures, live runtime evidence and OS/account checks.

Context MCP is read-only and bound to the exact persisted workspace/project. It cannot change tasks, execute commands, switch accounts or grant permissions. Codex's existing HQ task tools remain the mutation interface; other runtimes can read the same board while their supervisor records updates. Full cross-provider task mutation/control is not claimed.

## Shared access without copied secrets

Agents working for this user may use an already-authorized GitHub CLI or connector identity through its native credential manager. They do not need separate GitHub accounts per role. Project scope, organization policies, credential scopes and the user's authorization still apply. A shared login is not a blanket authorization to publish, delete or message people.

Do not copy login files between providers, export passwords into prompts, save API keys in Ruflo, or commit account/session databases. GitHub and provider sessions stay with the official client or OS credential storage. DeepSeek's entered API key is currently session-only memory; quitting HQ clears it. Claude, Codex, Kimi and ZCode each retain their native account ownership.

## Routing and updates

The saved preferred supervisor is stable. Workers use suitable smaller models where evidence supports that choice. Optional automatic continuation uses only explicitly enrolled models and observed native quota failures, after confirming the old turn, tools and children are stopped. It preserves the project, transcript and task board. Uncertain action outcomes require review, and image-bearing handoffs currently remain manual.

Account windows are shown only when the provider reports them. Different models may share one account allowance. Optional local token ceilings are independent controls, disabled by default; they are not billing guarantees. Use available capacity for approved useful work, not to consume quota for its own sake.

Candidate updates may be discovered automatically. The outer reviewer and HQ supervisor review changes, test compatibility and record the activation decision before replacing an active top model, runtime adapter or shared skill version. Do not pull upstream code into a running task or replace credentials during work.
