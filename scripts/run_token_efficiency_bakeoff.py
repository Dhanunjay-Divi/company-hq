#!/usr/bin/env python3
"""Model-free token-efficiency benchmark for candidate compression layers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "LEDGER_MISMATCH_SENTINEL"


def run(command, *, cwd, env, timeout=90):
    started = time.perf_counter()
    p = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    text = (p.stdout or "") + (p.stderr or "")
    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "seconds": round(time.perf_counter() - started, 3),
        "bytes": len(text.encode()),
        "sentinel_preserved": SENTINEL in text,
        "text": text,
    }


def headroom_case():
    try:
        from headroom import compress
    except Exception as exc:
        return {"available": False, "reason": f"import failed: {exc}"}

    rows = []
    for i in range(250):
        rows.append({
            "id": i,
            "status": "ok",
            "service": "billing",
            "message": "request completed successfully",
            "latency_ms": 41 + (i % 4),
            "metadata": {"region": "us-east-1", "retry": 0, "worker": "fixture"},
        })
    rows[173] = {
        "id": 173,
        "status": "fatal",
        "service": "billing",
        "message": SENTINEL,
        "latency_ms": 9112,
        "metadata": {"region": "us-east-1", "retry": 4, "worker": "fixture"},
    }
    raw = json.dumps(rows, separators=(",", ":"))
    result = compress(
        [{"role": "tool", "content": raw}],
        model="gpt-4o",
        compress_user_messages=True,
        protect_recent=0,
        kompress_model="disabled",
    )
    compressed = "\n".join(str(m.get("content", "")) for m in result.messages)
    return {
        "available": True,
        "version": "0.37.0",
        "raw_bytes": len(raw.encode()),
        "compressed_bytes": len(compressed.encode()),
        "byte_reduction_ratio": round(1 - len(compressed.encode()) / len(raw.encode()), 4),
        "tokens_before": result.tokens_before,
        "tokens_after": result.tokens_after,
        "tokens_saved": result.tokens_saved,
        "token_reduction_ratio": round(result.compression_ratio, 4),
        "sentinel_preserved": SENTINEL in compressed,
        "transforms": result.transforms_applied,
        "excerpt": compressed[-2500:],
    }


def rtk_case(base: Path):
    exe = os.environ.get("BAKEOFF_RTK")
    if not exe:
        return {"available": False, "reason": "BAKEOFF_RTK not configured"}
    case = base / "rtk_case"
    case.mkdir()
    test_file = case / "test_many.py"
    lines = [
        "import pytest",
        "",
        "@pytest.mark.parametrize('i', range(200))",
        "def test_many_pass(i):",
        "    assert i >= 0",
        "",
        "def test_ledger_failure():",
        f"    raise AssertionError('{SENTINEL}')",
        "",
    ]
    test_file.write_text("\n".join(lines), encoding="utf-8")
    env = os.environ.copy()
    raw = run([sys.executable, "-m", "pytest", "-vv", str(test_file)], cwd=case, env=env)
    compact = run([exe, "pytest", "-vv", str(test_file)], cwd=case, env=env)
    return {
        "available": True,
        "version": "0.49.0",
        "raw": {k: v for k, v in raw.items() if k != "text"},
        "compact": {k: v for k, v in compact.items() if k != "text"},
        "byte_reduction_ratio": round(1 - compact["bytes"] / raw["bytes"], 4) if raw["bytes"] else 0,
        "sentinel_preserved": compact["sentinel_preserved"],
        "raw_excerpt": raw["text"][-1800:],
        "compact_excerpt": compact["text"][-1800:],
    }


def main() -> int:
    for key in tuple(os.environ):
        if key.endswith("_API_KEY") or key in {
            "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY",
            "CODEX_HOME", "CLAUDE_CONFIG_DIR",
        }:
            os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="company-hq-token-bakeoff-") as td:
        results = {
            "schema": 1,
            "sentinel": SENTINEL,
            "headroom": headroom_case(),
            "rtk": rtk_case(Path(td)),
        }
    out = ROOT / "benchmarks" / "token-efficiency-results.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    failures = []
    for name in ("headroom", "rtk"):
        value = results[name]
        if value.get("available") and not value.get("sentinel_preserved"):
            failures.append(f"{name}: sentinel lost")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
