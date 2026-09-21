# Token-efficiency bake-off

This benchmark measures two optional local compression candidates against raw
tool output. It never calls a provider model.

- **RTK**: deterministic Rust command-output compaction.
- **Headroom**: local library compression with Kompress disabled, so this test
  exercises structural/local transforms without downloading or invoking an LLM.

Fixtures cover noisy logs, test output, and repetitive JSON. Every fixture has
required failure evidence (file, error code, request id, failing test). A
candidate is not eligible for automatic use if it drops any required marker.

The benchmark records output bytes, a transparent bytes/4 token proxy, latency,
and exact evidence preservation. These numbers are only comparative input-size
proxies, not billing claims.

Run:

```sh
RTK_BIN=/path/to/rtk \
HEADROOM_PYTHON=/path/to/headroom-venv/bin/python \
python3 benchmarks/token-efficiency/run.py
```
