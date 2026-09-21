#!/usr/bin/env python3
"""Deterministic, model-free bake-off for code-intelligence candidates.

The benchmark uses isolated copies of one synthetic repository. It records
latency, output size, expected symbol/call-chain evidence and product-tree
writes. It never calls an LLM and strips common provider credentials from child
processes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixture"
PROVIDER_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "MOONSHOT_API_KEY", "KIMI_API_KEY", "ZAI_API_KEY", "XAI_API_KEY",
)


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in PROVIDER_ENV:
        env.pop(key, None)
    env.update({
        "DO_NOT_TRACK": "1",
        "CODEGRAPH_TELEMETRY": "0",
        "CODEGRAPH_NO_UPDATE_CHECK": "1",
        "CODEGRAPH_NO_DAEMON": "1",
        "NO_COLOR": "1",
    })
    if extra:
        env.update(extra)
    return env


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int = 90,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "seconds": round(time.perf_counter() - started, 4),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "seconds": round(time.perf_counter() - started, 4),
            "stdout": getattr(exc, "stdout", "") or "",
            "stderr": str(exc),
        }


def snapshot(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or not path.is_file():
            continue
        values[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def prepare_fixture(work: Path, candidate: str) -> tuple[Path, dict[str, str]]:
    project = work / candidate / "project"
    shutil.copytree(FIXTURE, project)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "bench@company-hq.local"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Company HQ Benchmark"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    return project, snapshot(project)


def executable(env_name: str, fallback: str) -> str | None:
    raw = os.environ.get(env_name)
    if raw:
        path = Path(raw).expanduser()
        return str(path) if path.exists() else None
    return shutil.which(fallback)


def parse_cbm_project(text: str) -> str | None:
    try:
        value = json.loads(text)
        stack = [value]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                project = current.get("project")
                if isinstance(project, str) and project:
                    return project
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
            elif isinstance(current, str) and current.startswith("{"):
                try:
                    stack.append(json.loads(current))
                except json.JSONDecodeError:
                    pass
    except json.JSONDecodeError:
        pass
    match = re.search(r'"project"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else None


def aggregate(commands: list[dict[str, Any]]) -> str:
    return "\n".join(
        part for item in commands for part in (item.get("stdout", ""), item.get("stderr", "")) if part
    )


def graphify(project: Path, state: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    binary = executable("GRAPHIFY_BIN", "graphify")
    if not binary:
        return [], False, "graphify executable not installed"
    out = state / "graphify-out"
    out.parent.mkdir(parents=True, exist_ok=True)
    env = child_env({"GRAPHIFY_OUT": str(out)})
    commands = [
        run([binary, "extract", str(project)], cwd=project, env=env, timeout=120),
    ]
    if commands[-1]["returncode"] == 0:
        commands.append(run(
            [binary, "query", "authentication verify_token authenticate login_request"],
            cwd=project, env=env,
        ))
        commands.append(run(
            [binary, "path", "login_request", "verify_token"],
            cwd=project, env=env,
        ))
    return commands, commands[0]["returncode"] == 0, None


def codegraph(project: Path, state: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    binary = executable("CODEGRAPH_BIN", "codegraph")
    if not binary:
        return [], False, "codegraph executable not installed"
    install = state / "install"
    install.mkdir(parents=True, exist_ok=True)
    env = child_env({
        "CODEGRAPH_INSTALL_DIR": str(install),
        "CODEGRAPH_DIR": ".codegraph-bench",
    })
    commands = [run([binary, "init", str(project)], cwd=project, env=env, timeout=120)]
    if commands[-1]["returncode"] == 0:
        commands.extend([
            run([binary, "query", "verify_token", "--json"], cwd=project, env=env),
            run([binary, "callers", "verify_token", "--json"], cwd=project, env=env),
            run(
                [binary, "explore", "login_request authenticate verify_token authentication flow"],
                cwd=project, env=env,
            ),
        ])
    return commands, commands[0]["returncode"] == 0, None


def graft(project: Path, state: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    wrapper = ROOT / "graft.py"
    install = os.environ.get("COMPANY_HQ_GRAFT_INSTALL")
    if not wrapper.is_file() or not install:
        return [], False, "pinned Graft benchmark install not configured"
    env = child_env({
        "COMPANY_HQ_GRAFT_INSTALL": install,
        "COMPANY_HQ_GRAFT_STATE_ROOT": str(state / "graft-state"),
    })
    commands = [run([sys.executable, str(wrapper), "build", str(project)], cwd=ROOT, env=env, timeout=120)]
    if commands[-1]["returncode"] == 0:
        commands.append(run([
            sys.executable, str(wrapper), "query", str(project),
            "where is authentication checked and what calls verify_token?",
        ], cwd=ROOT, env=env))
    return commands, commands[0]["returncode"] == 0, None


def cbm(project: Path, state: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    binary = executable("CBM_BIN", "codebase-memory-mcp")
    if not binary:
        return [], False, "codebase-memory-mcp executable not installed"
    cache = state / "cache"
    runtime = state / "runtime"
    config = state / "config"
    for directory in (cache, runtime, config):
        directory.mkdir(parents=True, exist_ok=True)
    env = child_env({
        "CBM_CACHE_DIR": str(cache),
        "CBM_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(config),
        "CBM_LOG_LEVEL": "error",
    })
    payload = json.dumps({"repo_path": str(project), "mode": "full", "persistence": False})
    commands = [run([binary, "cli", "index_repository", payload], cwd=project, env=env, timeout=120)]
    project_name = parse_cbm_project(commands[0]["stdout"])
    if commands[-1]["returncode"] == 0 and project_name:
        commands.extend([
            run([
                binary, "cli", "search_graph",
                json.dumps({"project": project_name, "query": "authentication verify token login", "limit": 20}),
            ], cwd=project, env=env),
            run([
                binary, "cli", "trace_path",
                json.dumps({
                    "project": project_name,
                    "function_name": "verify_token",
                    "direction": "inbound",
                    "depth": 5,
                }),
            ], cwd=project, env=env),
        ])
    elif commands[-1]["returncode"] == 0:
        return commands, False, "index succeeded but project id was not returned"
    return commands, commands[0]["returncode"] == 0, None


ADAPTERS: dict[str, Callable[[Path, Path], tuple[list[dict[str, Any]], bool, str | None]]] = {
    "graphify": graphify,
    "codegraph": codegraph,
    "graft": graft,
    "codebase-memory-mcp": cbm,
}


def result_for(
    candidate: str,
    project: Path,
    before: dict[str, str],
    state: Path,
    commands: list[dict[str, Any]],
    indexed: bool,
    unavailable_reason: str | None,
) -> dict[str, Any]:
    after = snapshot(project)
    added = sorted(set(after) - set(before))
    changed = sorted(path for path in set(before) & set(after) if before[path] != after[path])
    text = aggregate(commands)
    lower = text.lower()
    symbols = {
        "verify_token": "verify_token" in lower,
        "authenticate": "authenticate" in lower,
        "login_request": "login_request" in lower,
    }
    relationship = sum(symbols.values()) == 3 and any(
        marker in lower for marker in ("call", "caller", "path", "->", "edge", "inbound")
    )
    query_commands = commands[1:] if len(commands) > 1 else []
    query_seconds = round(sum(float(x["seconds"]) for x in query_commands), 4)
    query_output = aggregate(query_commands)
    return {
        "candidate": candidate,
        "available": bool(commands),
        "indexed": indexed,
        "unavailable_reason": unavailable_reason,
        "index_seconds": commands[0]["seconds"] if commands else None,
        "query_seconds": query_seconds if query_commands else None,
        "query_output_bytes": len(query_output.encode("utf-8")),
        "query_token_proxy": math.ceil(len(query_output.encode("utf-8")) / 4),
        "expected_symbols": symbols,
        "relationship_evidence": relationship,
        "repo_pollution": {
            "added_paths": added,
            "changed_paths": changed,
            "clean": not added and not changed,
        },
        "state_bytes": sum(p.stat().st_size for p in state.rglob("*") if p.is_file()) if state.exists() else 0,
        "commands": [
            {
                "command": item["command"],
                "returncode": item["returncode"],
                "seconds": item["seconds"],
                "stdout_tail": item["stdout"][-4000:],
                "stderr_tail": item["stderr"][-2000:],
            }
            for item in commands
        ],
    }


def markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Code-intelligence bake-off",
        "",
        "Deterministic synthetic fixture; no LLM calls. Token proxy is output bytes / 4, not a provider-billed token count.",
        "",
        "| Candidate | Indexed | Symbols | Relation | Query token proxy | Repo clean | Index s | Query s |",
        "| --- | --- | ---: | --- | ---: | --- | ---: | ---: |",
    ]
    for row in results:
        hits = sum(1 for value in row["expected_symbols"].values() if value)
        lines.append(
            f"| {row['candidate']} | {'yes' if row['indexed'] else 'no'} | {hits}/3 | "
            f"{'yes' if row['relationship_evidence'] else 'no'} | {row['query_token_proxy']} | "
            f"{'yes' if row['repo_pollution']['clean'] else 'NO'} | "
            f"{row['index_seconds'] if row['index_seconds'] is not None else '-'} | "
            f"{row['query_seconds'] if row['query_seconds'] is not None else '-'} |"
        )
    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- A candidate that writes into the fixture is not eligible as Company HQ's default product-repo-safe index without additional isolation.",
        "- Missing/failed candidates are reported, never assigned a synthetic score.",
        "- Serena is evaluated separately because its main value is symbol-aware editing/refactoring, not persistent graph replacement.",
        "- README/vendor benchmark claims are not used to calculate this table.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results.json"))
    parser.add_argument("--markdown", type=Path, default=Path("benchmark-results.md"))
    parser.add_argument("--candidate", action="append", choices=sorted(ADAPTERS))
    args = parser.parse_args()

    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if args.work_root:
        work = args.work_root.resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        owned_temp = tempfile.TemporaryDirectory(prefix="company-hq-code-intel-")
        work = Path(owned_temp.name)

    selected = args.candidate or list(ADAPTERS)
    results: list[dict[str, Any]] = []
    try:
        for candidate in selected:
            project, before = prepare_fixture(work, candidate)
            state = work / candidate / "state"
            state.mkdir(parents=True, exist_ok=True)
            try:
                commands, indexed, reason = ADAPTERS[candidate](project, state)
            except Exception as exc:
                commands, indexed, reason = [], False, f"adapter exception: {exc}"
            results.append(result_for(candidate, project, before, state, commands, indexed, reason))

        payload = {
            "schema": 1,
            "fixture": "synthetic auth call chain",
            "expected_chain": ["handle_login", "login_request", "AuthService.authenticate", "verify_token", "normalize_token"],
            "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        rendered = markdown(results)
        args.markdown.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        print("\nJSON:", args.output)
        return 0
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
