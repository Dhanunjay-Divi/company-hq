# 2026-09-25 — Linked teammate chats and custom API

## Request and delivery

The user asked for company-style coordination: a project coordinator chat with
individual leads and specialists visible as separate, inspectable conversations.
They also supplied a Qwen-compatible endpoint and requested a public source
release. This round used a real GLM-5.3 HQ lead for the four-file custom API
adapter, with the outer reviewer wiring the API, UI, tests and release.

HQ now persists an explicit parent link and assignment for a teammate project
chat. The sidebar nests its conversation beneath the coordinator; Office shows
its observed runtime state and opens the actual chat. The create flow starts a
connected model with a bounded assignment. A parent link is presentation and
coordination metadata, not proof that different provider runtimes exchange
messages or that the coordinator has reviewed the result.

The custom provider verifies the exact model through `/models` or an explicitly
requested generation probe. Only text turns and reported token usage are
supported; image, file, browser and worker tools are absent. Its secret is
process-memory-only, and it is excluded from automatic coding handoffs. No
endpoint or credential from the user's request is hardcoded in public source.
The supplied remote endpoint timed out from this machine and no local SSH
tunnel was listening, so live Qwen generation remains unverified.

## Verification and remaining work

The full model-free check passed 314 Python integration tests plus root,
JavaScript, source-bundle and portability checks. The React production build
passed. Focused custom adapter tests use a fake transport and cover URL,
redirect, secret, model and turn boundaries. A live UI pass confirmed a GLM
lead with its own conversation under its project coordinator. An unsigned
macOS development app must be rebuilt after this source change; a real Qwen
turn depends on reachability of the user's service or tunnel.
