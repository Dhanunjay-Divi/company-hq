#!/usr/bin/env python3
"""Model-free comparison of structural code-intelligence candidates.

The benchmark intentionally uses a tiny synthetic fixture with known call
relationships. It measures whether each tool can surface the expected symbols,
how much output it emits, wall-clock latency, and whether it writes inside the
fixture repository. It never supplies model/provider credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "code-intel-fixture"
QUESTION = "where is session authorization checked?"
EXPECTED = ("authorize_session", "check_permission", "get_report")


def run(command, *, cwd, env, timeout=120):
    started = time.perf_counter()
    try:
        p = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
            "seconds": round(time.perf_counter() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nTIMEOUT",
            "seconds": round(time.perf_counter() - started, 3),
        }


def fixture_copy(base: Path, name: str) -> Path:
    target = base / name / "project"
    target.mkdir(parents=True)
    for rel in ("auth/session.py", "api/reports.py", "billing/invoice.ts"):
        src = FIXTURE / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (target / ".git").mkdir()
    return target


def source_digest(project: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(project.rglob("*")):
        if p.is_file() and ".git" not in p.parts and not any(part.startswith(".codegraph") for part in p.parts):
            h.update(str(p.relative_to(project)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def score_output(text: str):
    lower = text.lower()
    hits = [symbol for symbol in EXPECTED if symbol.lower() in lower]
    return hits, len(hits)


def pollution(project: Path):
    allowed = {".git", "auth", "api", "billing"}
    return sorted(p.name for p in project.iterdir() if p.name not in allowed)


def candidate_graphify(base: Path, env: dict[str, str]):
    exe = os.environ.get("BAKEOFF_GRAPHIFY")
    if not exe:
        return {"available": False, "reason": "BAKEOFF_GRAPHIFY not configured"}
    project = fixture_copy(base, "graphify")
    state = base / "graphify" / "state"
    local_env = env | {"GRAPHIFY_OUT": str(state)}
    before = source_digest(project)
    build = run([exe, "extract", str(project)], cwd=project, env=local_env)
    query = run([exe, "query", QUESTION], cwd=project, env=local_env) if build["ok"] else {
        "ok": False, "stdout": "", "stderr": "build failed", "seconds": 0
    }
    hits, score = score_output(query["stdout"] + "\n" + query["stderr"])
    return {
        "available": True,
        "version": "0.9.65",
        "build": {k: v for k, v in build.items() if k not in ("stdout", "stderr")},
        "query": {k: v for k, v in query.items() if k not in ("stdout", "stderr")},
        "query_output_bytes": len((query["stdout"] + query["stderr"]).encode()),
        "expected_hits": hits,
        "correctness_score": score,
        "source_unchanged": before == source_digest(project),
        "project_pollution": pollution(project),
        "output_excerpt": (query["stdout"] + query["stderr"])[-3000:],
    }


def candidate_codegraph(base: Path, env: dict[str, str]):
    exe = os.environ.get("BAKEOFF_CODEGRAPH")
    if not exe:
        return {"available": False, "reason": "BAKEOFF_CODEGRAPH not configured"}
    project = fixture_copy(base, "codegraph")
    local_env = env | {"CODEGRAPH_TELEMETRY": "0"}
    before = source_digest(project)
    run([exe, "telemetry", "off"], cwd=project, env=local_env, timeout=30)
    build = run([exe, "init", str(project)], cwd=project, env=local_env)
    query = run([exe, "explore", QUESTION], cwd=project, env=local_env) if build["ok"] else {
        "ok": False, "stdout": "", "stderr": "build failed", "seconds": 0
    }
    hits, score = score_output(query["stdout"] + "\n" + query["stderr"])
    return {
        "available": True,
        "version": "1.6.0",
        "build": {k: v for k, v in build.items() if k not in ("stdout", "stderr")},
        "query": {k: v for k, v in query.items() if k not in ("stdout", "stderr")},
        "query_output_bytes": len((query["stdout"] + query["stderr"]).encode()),
        "expected_hits": hits,
        "correctness_score": score,
        "source_unchanged": before == source_digest(project),
        "project_pollution": pollution(project),
        "output_excerpt": (query["stdout"] + query["stderr"])[-3000:],
    }


def candidate_graft(base: Path, env: dict[str, str]):
    install = os.environ.get("BAKEOFF_GRAFT_INSTALL")
    if not install:
        return {"available": False, "reason": "BAKEOFF_GRAFT_INSTALL not configured"}
    project = fixture_copy(base, "graft")
    state = base / "graft" / "state"
    local_env = env | {
        "COMPANY_HQ_GRAFT_INSTALL": install,
        "COMPANY_HQ_GRAFT_STATE_ROOT": str(state),
    }
    before = source_digest(project)
    build = run([sys.executable, str(ROOT / "graft.py"), "build", str(project)], cwd=ROOT, env=local_env)
    query = run(
        [sys.executable, str(ROOT / "graft.py"), "query", str(project), QUESTION, "--no-refresh"],
        cwd=ROOT,
        env=local_env,
    ) if build["ok"] else {"ok": False, "stdout": "", "stderr": "build failed", "seconds": 0}
    hits, score = score_output(query["stdout"] + "\n" + query["stderr"])
    return {
        "available": True,
        "version": "0.18.0",
        "build": {k: v for k, v in build.items() if k not in ("stdout", "stderr")},
        "query": {k: v for k, v in query.items() if k not in ("stdout", "stderr")},
        "query_output_bytes": len((query["stdout"] + query["stderr"]).encode()),
        "expected_hits": hits,
        "correctness_score": score,
        "source_unchanged": before == source_digest(project),
        "project_pollution": pollution(project),
        "output_excerpt": (query["stdout"] + query["stderr"])[-3000:],
    }


def main() -> int:
    for key in tuple(os.environ):
        if key.endswith("_API_KEY") or key in {
            "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "CODEX_HOME",
            "CLAUDE_CONFIG_DIR", "GEMINI_API_KEY",
        }:
            os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="company-hq-code-intel-") as td:
        base = Path(td)
        env = os.environ.copy()
        results = {
            "schema": 1,
            "question": QUESTION,
            "expected_symbols": list(EXPECTED),
            "graphify": candidate_graphify(base, env),
            "codegraph": candidate_codegraph(base, env),
            "graft": candidate_graft(base, env),
        }
    output = ROOT / "benchmarks" / "code-intel-results.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    usable = [v for k, v in results.items() if k not in {"schema", "question", "expected_symbols"} and v.get("available")]
    return 0 if usable else 2


if __name__ == "__main__":
    raise SystemExit(main())
