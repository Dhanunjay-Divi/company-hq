#!/usr/bin/python3
"""Narrow stdio guard for the shared codebase-memory MCP registration."""

import json
import os
import subprocess
import sys
import threading
import hashlib
import stat
from pathlib import Path


def prepare_runtime_dir():
    """Keep Unix socket paths short without sharing project state or sockets."""
    if sys.platform != 'darwin':
        return
    configured = os.environ.get('CBM_RUNTIME_DIR', '')
    if not configured or len(os.fsencode(configured)) < 65:
        return
    base = Path('/private/tmp') / f'chq-cbm-{os.getuid()}'
    target = base / hashlib.sha256(configured.encode()).hexdigest()[:24]
    for folder in (base, target):
        try:
            folder.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info=folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Codebase Memory runtime directory is not private')
    os.environ['CBM_RUNTIME_DIR']=str(target)


ALLOWED_TOOLS = {
    "index_repository",
    "search_graph",
    "query_graph",
    "trace_path",
    "get_code_snippet",
    "get_graph_schema",
    "get_architecture",
    "search_code",
    "list_projects",
    "index_status",
    "check_index_coverage",
    "detect_changes",
}
PATH_ARGUMENTS = {"repo_path", "project_path", "workspace_path", "root_path", "directory", "cwd", "path", "file_path"}


def error_response(request_id, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        },
    }


def launch_root():
    value = os.environ.get("COMPANY_HQ_CONTEXT_PROJECT", "").strip()
    if not value:
        return None
    try:
        root = Path(value).resolve(strict=True)
    except OSError:
        return False
    return root if root.is_dir() else False


def path_is_bound(value, root):
    try:
        candidate = Path(value)
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve(strict=False)
        return resolved.is_relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False


def has_unbound_path(value, root):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PATH_ARGUMENTS and isinstance(child, str) and child and not path_is_bound(child, root):
                return True
            if has_unbound_path(child, root):
                return True
    elif isinstance(value, list):
        return any(has_unbound_path(child, root) for child in value)
    return False


def guard_request(request):
    if not isinstance(request, dict):
        return request, None
    if request.get("method") != "tools/call":
        return request, None
    params = request.get("params")
    if not isinstance(params, dict):
        return request, None
    name = params.get("name")
    if name not in ALLOWED_TOOLS:
        return None, error_response(request.get("id"), f"Tool disabled by local MCP policy: {name}")
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
        params["arguments"] = arguments
    root = launch_root()
    if root is False:
        return None, error_response(request.get("id"), "Tool refused: launch project binding is invalid.")
    if name != "index_repository":
        if root and has_unbound_path(arguments, root):
            return None, error_response(request.get("id"), "Tool refused: path is outside the launch project binding.")
        return request, None

    repo_path = arguments.get("repo_path")
    if root:
        if repo_path is None or repo_path == "":
            repo_path = str(root)
            arguments["repo_path"] = repo_path
        try:
            candidate = Path(repo_path).resolve(strict=True)
        except OSError:
            return None, error_response(request.get("id"), "Index refused: repository path is invalid for the launch project.")
        if candidate != root:
            return None, error_response(request.get("id"), "Index refused: repository path differs from the launch project binding.")
        if has_unbound_path(arguments, root):
            return None, error_response(request.get("id"), "Index refused: path is outside the launch project binding.")
    if isinstance(repo_path, str) and repo_path:
        artifact_path = os.path.join(os.path.realpath(repo_path), ".codebase-memory")
        if os.path.lexists(artifact_path):
            return None, error_response(
                request.get("id"),
                "Index refused: repository already contains .codebase-memory, which upstream may refresh even when persistence=false.",
            )
    arguments["persistence"] = False
    return request, None


def relay_stderr(stream):
    for chunk in iter(lambda: stream.read(8192), b""):
        sys.stderr.buffer.write(chunk)
        sys.stderr.buffer.flush()


def write_line(payload, output_lock):
    if not isinstance(payload, bytes):
        payload = json.dumps(payload, separators=(",", ":")).encode()
    if not payload.endswith(b"\n"):
        payload += b"\n"
    with output_lock:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()


def relay_stdout(stream, output_lock, tools_list_ids, state_lock):
    for raw_line in iter(stream.readline, b""):
        output = raw_line
        try:
            response = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = None
        if isinstance(response, dict):
            response_id = response.get("id")
            with state_lock:
                is_tools_list = response_id in tools_list_ids
                if is_tools_list:
                    tools_list_ids.discard(response_id)
            if is_tools_list:
                result = response.get("result")
                tools = result.get("tools") if isinstance(result, dict) else None
                if isinstance(tools, list):
                    result["tools"] = [
                        tool
                        for tool in tools
                        if isinstance(tool, dict) and tool.get("name") in ALLOWED_TOOLS
                    ]
                    output = json.dumps(response, separators=(",", ":")).encode() + b"\n"
        write_line(output, output_lock)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: mcp_guard.py <server> [args...]")
    prepare_runtime_dir()
    child = subprocess.Popen(sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output_lock = threading.Lock()
    state_lock = threading.Lock()
    tools_list_ids = set()
    stderr_thread = threading.Thread(target=relay_stderr, args=(child.stderr,), daemon=True)
    stdout_thread = threading.Thread(
        target=relay_stdout,
        args=(child.stdout, output_lock, tools_list_ids, state_lock),
        daemon=True,
    )
    stderr_thread.start()
    stdout_thread.start()
    try:
        for raw_line in sys.stdin.buffer:
            try:
                request = json.loads(raw_line)
                request, response = guard_request(request)
            except (UnicodeDecodeError, json.JSONDecodeError):
                request, response = None, None
            if response is not None:
                if response.get("id") is not None:
                    write_line(response, output_lock)
                continue
            if request is None:
                child.stdin.write(raw_line)
            else:
                if (
                    isinstance(request, dict)
                    and request.get("method") == "tools/list"
                    and request.get("id") is not None
                ):
                    with state_lock:
                        tools_list_ids.add(request["id"])
                child.stdin.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            child.stdin.flush()
    finally:
        child.stdin.close()
    try:
        return_code = child.wait(timeout=30)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:
            return_code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            return_code = child.wait(timeout=5)
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
