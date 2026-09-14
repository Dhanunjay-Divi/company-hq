#!/usr/bin/python3
"""Narrow stdio guard for the shared codebase-memory MCP registration."""

import json
import os
import subprocess
import sys
import threading


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


def error_response(request_id, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        },
    }


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
    if name != "index_repository":
        return request, None

    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
        params["arguments"] = arguments
    repo_path = arguments.get("repo_path")
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
