"""Safe, read-only task projections from the native Codex app-server."""

from __future__ import annotations

import math
import re
from typing import Any


_ID = re.compile(r"[A-Za-z0-9_-]{1,100}", re.ASCII)
_STATUS_TYPES = frozenset(("notLoaded", "idle", "systemError", "active"))
_BASE_SOURCE_KINDS = ("cli", "vscode", "exec", "appServer", "unknown")
_AGENT_SOURCE_KINDS = (
    "subAgent", "subAgentReview", "subAgentCompact", "subAgentThreadSpawn",
    "subAgentOther",
)


def _invalid(message: str = "Invalid Codex task request.") -> ValueError:
    return ValueError(message)


def _is_id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _bounded_string(value: object, limit: int, fallback: Any) -> Any:
    """Keep bounded metadata whole; paths and source labels are never truncated."""
    return value if isinstance(value, str) and len(value) <= limit else fallback


def _number_or_none(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) and value >= 0 else None
    except (OverflowError, TypeError):
        return None


def _project(thread: object) -> dict[str, Any] | None:
    if not isinstance(thread, dict) or not _is_id(thread.get("id")):
        return None
    name = thread.get("name")
    title = name.strip()[:180] if isinstance(name, str) and name.strip() else "Untitled Codex task"
    raw_status = thread.get("status")
    status_type = raw_status.get("type") if isinstance(raw_status, dict) else None
    status = status_type if isinstance(status_type, str) and status_type in _STATUS_TYPES else "unknown"
    return {
        "id": thread["id"],
        "title": title,
        "project": _bounded_string(thread.get("cwd"), 4096, None),
        "updatedAt": _number_or_none(thread.get("updatedAt")),
        "status": status,
        "source": _bounded_string(thread.get("source"), 80, "unknown"),
    }


def _validate_list_inputs(cursor: object, search: object, archived: object, include_agents: object) -> None:
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 2048):
        raise _invalid()
    if not isinstance(search, str) or len(search) > 200:
        raise _invalid()
    if not isinstance(archived, bool) or not isinstance(include_agents, bool):
        raise _invalid()


def list_tasks(rpc, *, cursor=None, search="", archived=False, include_agents=False) -> dict[str, Any]:
    """Return one bounded page without scanning native rollout history."""
    _validate_list_inputs(cursor, search, archived, include_agents)
    source_kinds = _BASE_SOURCE_KINDS + (_AGENT_SOURCE_KINDS if include_agents else ())
    params = {
        "limit": 30,
        "sortKey": "updated_at",
        "sortDirection": "desc",
        "useStateDbOnly": True,
        "archived": archived,
        "sourceKinds": list(source_kinds),
    }
    if cursor:
        params["cursor"] = cursor
    if search:
        params["searchTerm"] = search
    try:
        response = rpc("thread/list", params)
    except Exception:
        raise RuntimeError("The Codex task runtime could not be reached.") from None
    if not isinstance(response, dict) or not isinstance(response.get("data"), list):
        raise _invalid("The Codex task runtime returned an invalid response.")
    next_cursor = response.get("nextCursor")
    if next_cursor is not None and (not isinstance(next_cursor, str) or len(next_cursor) > 2048):
        raise _invalid("The Codex task runtime returned an invalid response.")
    tasks = []
    for row in response["data"][:30]:
        projected = _project(row)
        if projected is not None:
            tasks.append(projected)
    return {"provider": "codex", "readOnly": True, "tasks": tasks, "nextCursor": next_cursor}


def read_task(rpc, thread_id: str) -> dict[str, Any]:
    """Read metadata only.  ``includeTurns`` remains false so this never resumes work."""
    if not _is_id(thread_id):
        raise _invalid()
    try:
        response = rpc("thread/read", {"threadId": thread_id, "includeTurns": False})
    except Exception:
        raise RuntimeError("The Codex task runtime could not be reached.") from None
    if not isinstance(response, dict):
        raise _invalid("The Codex task runtime returned an invalid response.")
    task = _project(response.get("thread"))
    if task is None or task["id"] != thread_id:
        raise _invalid("The Codex task runtime returned an invalid response.")
    preview = response["thread"].get("preview")
    summary = preview[:2000] if isinstance(preview, str) else ""
    task["summary"] = summary
    return {"provider": "codex", "readOnly": True, "task": task}
