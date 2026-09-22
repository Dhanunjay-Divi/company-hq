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

- Full `python3 scripts/hq.py check`: **231 Python tests passed** (23 root, 31 supporting, 177 integration), plus **6 JavaScript tests**; source archive, portability and capability checks passed.
- The final Finder ownership correction passed its **11 focused tests**. Production frontend build passed. The independent reviewer reported no remaining P0/P1 issues in the reviewed integration.
- Actual CUA interaction verified Claude's signed-out connection status without a prompt, the model-provider tabs, retained text after reload, image selection/preview/removal, project file inspection, and plan preview/application.
- Native Finder chooser initially timed out behind other windows. The corrected Finder-owned dialog passed both cancellation and canonical folder selection into a disposable project.
- Actual Beads-backed UI rejected starting a blocked task, then moved it to ready after its prerequisite was completed. These manual fixture transitions are not presented as agent work.
- Official Claude SDK metadata browsing completed without a prompt and reported zero local sessions on this machine.

Desktop artifact and GitHub check results are recorded with the release commit. Historical baseline counts in older reports describe their own commits.

## User setup that cannot be inferred

Open Settings to connect Claude Code and load its actual models. Enable computer-use/MCP plugins in the native provider, then grant macOS Accessibility and Screen Recording if desired. HQ's Full access setting is a per-chat native execution mode, not an operating-system grant. Apple signing/notarization credentials are required for a distributable signed release; this is a local development application.
