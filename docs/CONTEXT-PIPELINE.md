# Context evidence pipeline

Company HQ records command output only after the native sandbox has run the command. `ContextPipeline.record(team, project, captured)` never runs that command again. It retains a private, external, project-and-team-hashed raw record with an exit code, SHA-256 digest, capped raw text, and paginated recall. Raw output remains authoritative for failure evidence.

When `build/tools/rtk` is available, the pipeline passes the captured text to `rtk pipe --filter` with telemetry disabled, an external RTK database, and recall/tee disabled. It reports byte measurements only. A compact result is discarded if it loses failure markers; raw recall is then used.

Graphify is optional stage two. `build_graph(project)` and `query_graph(project, query, broad=True)` use a pinned Graphify virtual environment and `GRAPHIFY_OUT` outside the bound project. Codebase Memory MCP remains the primary narrow-recall path. No Graphify or RTK operation writes a project checkout or calls an LLM service.

`python scripts/hq_context.py --state-root /private/state --team team --project /project -- command args` is a local wrapper: it runs the command once in the invoking sandbox, stores its captured result, forwards output, and preserves the command exit code.

Supermemory is not added: its local self-hosting configuration requires either an LLM-provider key or an available local Ollama model. No Ollama server is present, and the pipeline must not silently introduce paid authentication or account migration. Ruflo remains unchanged until a local-model path is verified. See [Supermemory self-hosting configuration](https://supermemory.ai/docs/self-hosting/configuration).

## Local acceptance (2026-09-21)

The pinned `graphifyy==0.9.65` package was installed in ignored `build/graphify-venv`. A disposable Python fixture built with `graphify update --no-cluster` and queried `known_function`; `GRAPHIFY_OUT` held all Graphify artifacts outside the fixture and the source-file digest was unchanged. The pinned `build/tools/rtk` accepted captured pytest-shaped failure text through `rtk pipe --filter pytest` with telemetry, recall, and tee disabled. These checks establish local command compatibility only, not retrieval quality, savings, or LLM behavior.

When captured output exceeds 4 MiB, the record exposes `raw_truncated: true`, `raw_bytes`, and `original_raw_bytes`; recall therefore does not claim that it contains the full process output.
