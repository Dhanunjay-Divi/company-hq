"""Minimal stdio MCP adapter for :mod:`project_context`; read-only by design."""
from __future__ import annotations

import json
import sys

from project_context import ContextError, launched_context


TOOLS = [
    {"name": "hq_context", "description": "Read the launch-bound project identity and canonical task-board status.", "inputSchema": {"type": "object", "properties": {"cursor": {"type": "integer"}, "limit": {"type": "integer"}}}},
    {"name": "hq_skills", "description": "List reviewed project and installed skill references by name and description.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "hq_skill_read", "description": "Read a paged, registered skill reference. References are not permissions.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "path": {"type": "string"}, "cursor": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["name"]}},
]
for tool in TOOLS:
    tool['annotations'] = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}


def call(context, name, arguments):
    args = arguments if isinstance(arguments, dict) else {}
    if name == "hq_context":
        return {**context.identity(), "board": context.board(cursor=args.get("cursor", 0), limit=args.get("limit", 50))}
    if name == "hq_skills": return {"skills": context.skills()}
    if name == "hq_skill_read": return context.skill_read(args.get("name"), args.get("path", "SKILL.md"), cursor=args.get("cursor", 0), limit=args.get("limit", 24_000))
    raise ContextError("unknown context tool")


def handle(context, request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        raise ContextError("invalid JSON-RPC request")
    has_id = "id" in request
    request_id = request.get("id")
    if has_id and (isinstance(request_id, bool) or not isinstance(request_id, (str, int))):
        raise ContextError("invalid JSON-RPC request id")
    method = request["method"]
    if method == "initialize": result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "hq-project-context", "version": "1"}}
    elif method == "ping": result = {}
    elif method == "tools/list": result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        if not isinstance(params, dict): raise ContextError("invalid tool parameters")
        try: value = call(context, params.get("name"), params.get("arguments")); result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
        except ContextError as exc: result = {"content": [{"type": "text", "text": str(exc)[:200]}], "isError": True}
    elif method == "notifications/initialized": return None
    else: raise ContextError("unsupported method")
    return {"jsonrpc": "2.0", "id": request_id, "result": result} if has_id else None


def main() -> int:
    try: context = launched_context()
    except ContextError: return 2
    for line in sys.stdin:
        request_id = None; request = None
        try:
            if len(line.encode("utf-8")) > 1_048_576: raise ContextError("MCP input exceeds 1 MiB")
            request = json.loads(line)
            response = handle(context, request)
            if response is not None: print(json.dumps(response), flush=True)
        except (ContextError, ValueError, TypeError) as exc:
            if isinstance(request, dict) and isinstance(request.get("id"), (str, int)) and not isinstance(request.get("id"), bool): request_id = request["id"]
            if request_id is not None: print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": str(exc)[:200]}}), flush=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
