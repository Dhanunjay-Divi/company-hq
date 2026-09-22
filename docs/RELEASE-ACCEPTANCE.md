# Company HQ integrated release acceptance

Date: 2026-09-21. Scope: the private Company HQ repository and its local desktop build. Pinky and other product repositories are outside this change.

## What changed

The previous interface presented more recorded metadata than usable controls. This release connects the conversation to real Beads plans/tasks, observed native workers, a project editor, native sandboxed commands, durable text drafts/history, and explicit Codex/Claude provider boundaries. A Rust desktop shell owns the frozen backend process. See [STATUS](STATUS.md) for feature and platform limits.

Reviewed corrections include atomic/retryable plan application, task ownership and dependency checks, file descriptor based path handling and revision checks, serialized evidence writes, stale native request rejection, dynamic-tool cancellation races, and nonfatal archival failures after a prompt has already been accepted. These fixes prevent duplicate sends and misleading state from ordinary failures; they do not create provider-side budget guarantees.

## HQ building HQ

HQ's native pipeline produced the native task metadata module and composer recovery/local-voice components in isolated checkouts. The outer reviewer integrated the results and corrected response shapes, the speech API spelling, and draft persistence across random local ports. These were real provider turns and source changes, not simulated team activity.

The earlier task-library run reported 329,132 native tokens against a 200,000 local allowance. The composer run reported 181,390 against 160,000 and was interrupted. The earlier Chrome acceptance reported 70,531 against 50,000. Useful output does not make those efficiency tests pass. The UI and documentation retain the failures; no token or cost saving is claimed. Smaller bounded assignments and raw-output compression are implemented, but must be evaluated on representative work before a savings claim.

## Evidence categories

- Automated fixtures exercise real adapter stdin/stdout protocols, canonical task storage, plan DAGs, recovery, conflict detection, permissions, cancellation, images, and provider selection. Fixtures do not prove model quality or entitlement.
- A real model-free Codex protocol probe accepted the new supervisor client tools and executed a bounded `command/exec` under a workspace-write sandbox. The observed command returned the expected marker without starting a model turn.
- Existing native evidence verifies supervisor → lead → worker delegation and HQ → Chrome browser use. Native desktop app control remains unverified. The embedded Codex browser was unavailable from HQ's standalone runtime.
- The reviewed Claude Code CLI reports its installed version and signed-out state. Protocol fixture tests pass; authenticated Claude execution requires the user to finish sign-in.
- The packaged backend includes its Python runtime. Optional Ruflo memory uses the existing reviewed shared installation and its dependencies; no source-checkout or product files are silently copied into private state.

## Final verification record

- Final `python3 scripts/hq.py check`: **235 Python tests passed** (23 root, 31 supporting, 181 integration); source archive, portability and capability checks passed. The **6 JavaScript tests** also passed. The earlier local integration checkpoint passed 231 Python tests before the added shutdown regressions.
- The final Finder ownership correction passed its **11 focused tests**. Production frontend build passed. The independent reviewer reported no remaining P0/P1 issues in the reviewed integration.
- Actual CUA interaction verified Claude's signed-out connection status without a prompt, the model-provider tabs, retained text after reload, image selection/preview/removal, project file inspection, and plan preview/application.
- Native Finder chooser initially timed out behind other windows. The corrected Finder-owned dialog passed both cancellation and canonical folder selection into a disposable project.
- Actual Beads-backed UI rejected starting a blocked task, then moved it to ready after its prerequisite was completed. These manual fixture transitions are not presented as agent work.
- Official Claude SDK metadata browsing completed without a prompt and reported zero local sessions on this machine.

The first pushed integration commit passed model-free CI but its second CI job exposed a shutdown race: the launcher returned after signaling, and shutdown could instantiate a new runtime while fixture cleanup ran. The fix waits for process exit and only closes existing runtime objects. The lifecycle test and a no-state-creation shutdown regression cover the correction. The failure remains recorded in run 35673658220.

A real screenshot also revealed overlapping team-map/worker controls at a narrow desktop size. Both now use normal page flow; the corrected screenshot has separate header, graph and worker panel. An old cached lazy chunk after a local update previously produced a blank window; a recovery boundary now offers a reload.

Desktop artifact and GitHub check results are recorded with the release commit. Historical baseline counts in older reports describe their own commits.

### Final corrections and code checkpoint

Both [Model-free CI](https://github.com/Dhanunjay-Divi/company-hq/actions/runs/35675625856) and [End-to-end acceptance](https://github.com/Dhanunjay-Divi/company-hq/actions/runs/35675625839) passed for code checkpoint `63bd09b0966e4813576c158dff8557873090d4f4`.

The initially stalled browser runs exposed a real Chromium renderer crash, not a successful test: calling the on-device speech availability API on mount triggered bad IPC reason 123 in Chromium's headless build. Speech discovery now runs only after a microphone click, has a timeout, and never falls back to cloud recognition. Disabling the composer stops an active microphone. The final browser run exercises the actual application without suppressing this speech API. Real voice recognition on supported hardware remains unverified.

The installed app's first macOS Quit test left its backend running. The corrected launcher handles both native exit variants and has an owned-child drop fallback. A real native-menu Quit then closed the app, both backend processes and the listening port. The independent Rust process-group fixture also proved graceful cleanup (108 ms) and forced fallback (30.987 s), including descendant termination in the owned group. Cached/runtime rows are not used as proof of termination.

The native app restored the pre-existing test conversation, Beads tasks and unsent draft after moving from the source server to a new random port. A separate source-free frozen-backend smoke verified bundled frontend, routing, decision data and source download without a model call. The source archive is regenerated automatically before packaging. See the local release receipt for final artifact identities; this acceptance record is maintained after the artifact's code checkpoint.

## User setup that cannot be inferred

Open Settings to connect Claude Code and load its actual models. Enable computer-use/MCP plugins in the native provider, then grant macOS Accessibility and Screen Recording if desired. HQ's Full access setting is a per-chat native execution mode, not an operating-system grant. Apple signing/notarization credentials are required for a distributable signed release; this is a local development application.
