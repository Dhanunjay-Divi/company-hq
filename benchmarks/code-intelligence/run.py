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
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixture"
PROVIDER_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "MOONSHOT_API_KEY", "KIMI_API_KEY", "ZAI_API_KEY", "XAI_API_KEY",
)


def child_env(
    extra: dict[str, str] | None = None,
    *,
    isolated_home: Path | None = None,
) -> dict[str, str]:
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
    if isolated_home is not None:
        home = isolated_home.resolve()
        for directory in (home, home / ".config", home / ".cache", home / ".local" / "state"):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
        })
    if extra:
        env.update(extra)
    return env


def _captured_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


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
            "stdout": _captured_text(getattr(exc, "stdout", "")),
            "stderr": _captured_text(getattr(exc, "stderr", "")) or str(exc),
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
    candidate_root = work / candidate
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    project = candidate_root / "project"
    shutil.copytree(FIXTURE, project)

    git_home = candidate_root / "git-home"
    template = candidate_root / "empty-git-template"
    git_home.mkdir(parents=True, mode=0o700)
    template.mkdir(parents=True)
    git_env = os.environ.copy()
    git_env.update({
        "HOME": str(git_home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    })
    for key in list(git_env):
        if key.startswith("GIT_CONFIG_") and key not in {"GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"}:
            git_env.pop(key, None)

    subprocess.run(["git", "init", "-q", f"--template={template}"], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "config", "user.email", "bench@company-hq.local"], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "config", "user.name", "Company HQ Benchmark"], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "config", "commit.gpgSign", "false"], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "config", "core.hooksPath", os.devnull], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "add", "."], cwd=project, env=git_env, check=True)
    subprocess.run(["git", "commit", "--no-verify", "-qm", "fixture"], cwd=project, env=git_env, check=True)
    return project, snapshot(project)


def executable(env_name: str, fallback: str) -> str | None:
    raw = os.environ.get(env_name)
    if raw:
        path = Path(raw).expanduser().resolve()
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
    env = child_env({"GRAPHIFY_OUT": str(out)}, isolated_home=state / "home")
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
    }, isolated_home=state / "home")
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
    }, isolated_home=state / "home")
    commands = [run([sys.executable, str(wrapper), "build", str(project)], cwd=ROOT, env=env, timeout=120)]
    if commands[-1]["returncode"] == 0:
        commands.append(run([
            sys.executable, str(wrapper), "query", str(project),
            "where is authentication checked and what calls verify_token?",
        ], cwd=ROOT, env=env))
    return commands, commands[0]["returncode"] == 0, None


def _mcp_record(
    proc: subprocess.Popen[str],
    responses: "queue.Queue[str]",
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout: int = 120,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    started = time.perf_counter()
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
    proc.stdin.flush()
    deadline = time.monotonic() + timeout
    response: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            line = responses.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("id") == request_id:
            response = value
            break
    elapsed = round(time.perf_counter() - started, 4)
    if response is None:
        return {
            "command": ["mcp", method],
            "returncode": 124,
            "seconds": elapsed,
            "stdout": "",
            "stderr": "MCP response timed out or server exited",
        }, None
    failed = bool(response.get("error")) or bool(response.get("result", {}).get("isError"))
    return {
        "command": ["mcp", method],
        "returncode": 1 if failed else 0,
        "seconds": elapsed,
        "stdout": json.dumps(response, separators=(",", ":")) + "\n",
        "stderr": "",
    }, response


def cbm(project: Path, state: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    binary = executable("CBM_BIN", "codebase-memory-mcp")
    if not binary:
        return [], False, "codebase-memory-mcp executable not installed"
    # The caller gives CBM a deliberately short external state root because
    # its Unix-domain coordination endpoints can exceed socket path limits.
    short_root = state
    cache = short_root / "c"
    runtime = short_root / "r"
    config = short_root / "x"
    scratch = short_root / "t"
    home = short_root / "h"
    for directory in (short_root, cache, runtime, config, scratch, home):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    env = child_env({
        "CBM_CACHE_DIR": str(cache),
        "CBM_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(config),
        "TMPDIR": str(scratch),
        "CBM_LOG_LEVEL": "error",
    }, isolated_home=home)
    proc = subprocess.Popen(
        [binary, "--ui=false"],
        cwd=project,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    responses: "queue.Queue[str]" = queue.Queue()

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            responses.put(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    commands: list[dict[str, Any]] = []
    try:
        init_record, _ = _mcp_record(
            proc, responses, 1, "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "company-hq-bakeoff", "version": "1"},
            },
            timeout=15,
        )
        if init_record["returncode"] != 0:
            return [init_record], False, "MCP initialization failed"
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        index_record, index_response = _mcp_record(
            proc, responses, 2, "tools/call",
            {
                "name": "index_repository",
                "arguments": {"repo_path": str(project), "mode": "full", "persistence": False},
            },
        )
        commands.append(index_record)
        if index_record["returncode"] != 0 or index_response is None:
            return commands, False, "index_repository failed"

        project_name = parse_cbm_project(index_record["stdout"])
        if not project_name:
            return commands, False, "index succeeded but project id was not returned"

        search_record, _ = _mcp_record(
            proc, responses, 3, "tools/call",
            {
                "name": "search_graph",
                "arguments": {
                    "project": project_name,
                    "query": "authentication verify token login",
                    "limit": 20,
                },
            },
            timeout=30,
        )
        trace_record, _ = _mcp_record(
            proc, responses, 4, "tools/call",
            {
                "name": "trace_path",
                "arguments": {
                    "project": project_name,
                    "function_name": "verify_token",
                    "direction": "inbound",
                    "depth": 5,
                },
            },
            timeout=30,
        )
        commands.extend([search_record, trace_record])
        return commands, True, None
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        thread.join(timeout=1)


def relationship_evidence(candidate: str, text: str) -> bool:
    lower = text.lower()
    if "no path" in lower or "not found" in lower:
        return False
    if candidate == "graphify":
        return bool(re.search(
            r"shortest path[^\n]*:\s*\n\s*login_request\(\).*?--calls.*?"
            r"authenticate\(\).*?--calls.*?verify_token\(\)",
            lower,
            re.S,
        ))
    if candidate == "codegraph":
        return bool(re.search(
            r"flow.*?login_request.*?calls.*?authenticate.*?calls.*?verify_token",
            lower,
            re.S,
        ))
    if candidate == "codebase-memory-mcp":
        return (
            "function: verify_token" in lower
            and "direction: inbound" in lower
            and re.search(r"\bauthenticate\s+1\b", lower) is not None
            and re.search(r"\blogin_request\s+2\b", lower) is not None
        )
    if candidate == "graft":
        return bool(re.search(
            r"login_request.*?(?:calls|->).*?authenticate.*?(?:calls|->).*?verify_token",
            lower,
            re.S,
        ))
    return False


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
    removed = sorted(set(before) - set(after))
    changed = sorted(path for path in set(before) & set(after) if before[path] != after[path])
    text = aggregate(commands)
    lower = text.lower()
    symbols = {
        "verify_token": "verify_token" in lower,
        "authenticate": "authenticate" in lower,
        "login_request": "login_request" in lower,
    }
    relationship = sum(symbols.values()) == 3 and relationship_evidence(candidate, text)
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
            "removed_paths": removed,
            "changed_paths": changed,
            "clean": not added and not removed and not changed,
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
            external_state = False
            if candidate == "codebase-memory-mcp":
                state = Path(tempfile.mkdtemp(prefix="hq-cbm-", dir="/tmp"))
                state.chmod(0o700)
                external_state = True
            else:
                state = work / candidate / "state"
                state.mkdir(parents=True, exist_ok=True)
            try:
                try:
                    commands, indexed, reason = ADAPTERS[candidate](project, state)
                except Exception as exc:
                    commands, indexed, reason = [], False, f"adapter exception: {exc}"
                results.append(result_for(candidate, project, before, state, commands, indexed, reason))
            finally:
                if external_state:
                    shutil.rmtree(state, ignore_errors=True)

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
