# Repository verification — 2026-09-14 UTC

This verifies the new source checkout, not a deployment or completion of every product milestone.

- Fresh `npm ci --ignore-scripts` in `company-hq/`: passed. Exact lock reused; no install lifecycle scripts run.
- `npm run build`: passed, 1,806 modules transformed, app JavaScript about 464 kB before gzip. Upstream Radix `use client` bundling notices remain warnings, not build failures.
- `python3 -m unittest -q test_check_updates test_discover`: 12 passed.
- `python3 -W error::ResourceWarning -m unittest discover -s clawteam/integration -p test_codex_bridge.py`: 12 passed using fake native transport; no model turn started.
- `python3 scripts/check_source_bundle.py`: no forbidden tracked artifacts or common credential signatures found. This does not claim a comprehensive secret/security audit.
- Source archive integrity and existing UI acceptance were verified in the preceding installation task; those historical details are retained in `company-hq/VERIFICATION.md`.
- Public metadata: all 40 Notion-listed GitHub repositories returned metadata successfully. README-level assessment performed for ECC, gstack and Superpowers. Full source/install/compatibility audit of all 40 is not claimed.
- Seven-file historical Agent Teams compatibility patch preserved, including two files that were untracked in its original checkout.

Not repeated here: full HTTP suite, native privileged approval, another live model turn, full multi-team idea-to-launch scenario, Windows/Linux runtime, original Swift build or optional Graft native binding. These are scoped future acceptance gates, not implied passes.

The live toolkit, account configuration and product source were not replaced. This checkout is a source baseline for the implementing agent; portability and remaining UI/runtime gaps are in STATUS.md. No production deployment occurred.
