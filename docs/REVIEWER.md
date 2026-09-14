# Reviewer contract

The original Codex supervisor that prepared this repository is the reviewer. During this initial phase, the implementer is authorized to commit and push directly to main, without a draft PR or advance reviewer approval. The implementer should report pushed commit links/SHAs. The original supervisor can review those commits and make follow-up changes directly; the human can send the checkpoint to that reviewer task. This repository does not silently create an always-running reviewer, a webhook or a subscription.

Review in this order:

1. Cross-project/account boundaries, approvals, native process lifecycle and unintended writes.
2. Actual goal-to-plan-to-delegation-to-result behavior and truthful UI states.
3. Restart/replay/idempotency, worker communication and cancellation races.
4. Customer-facing usability on narrow and desktop layouts; inspect the actual UI, not just snapshots or build output.
5. Measured token overhead, context size, model choice and usefulness of each added dependency.
6. Exact upstream provenance, license obligations, reproducible setup and rollback.

Require an implementation summary, changed paths, executed checks and results, a short recorded/manual walkthrough, known gaps, dependency changes and actual usage evidence where a live run was justified. Keep failure evidence and distinguish unit tests from live acceptance. Do not require a new paid model run for every stylistic fix. Review happens after pushed checkpoints, not as a blocking PR gate. Do not claim an approval that did not happen. Fetch before applying reviewer fixes and preserve concurrent work; never force-push shared history. User authorization still governs publishing, external communications, spending and deployment.
