"""Private, content-free persistence and normalization for native worker metadata."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


MAX_WORKERS = 200
SOURCE_KINDS = [
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
]
VALID_THREAD_STATES = {"notLoaded", "idle", "systemError", "active"}


class WorkerDataError(ValueError):
    pass


def _text(value: object, limit: int = 200) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    return value


def normalize_thread(value: object) -> dict[str, Any] | None:
    """Return only bounded metadata needed to prove hierarchy and liveness."""
    if not isinstance(value, dict):
        return None
    thread_id = _text(value.get("id"), 200)
    session_id = _text(value.get("sessionId"), 200)
    if not thread_id or not session_id:
        return None
    raw_status = value.get("status")
    status = raw_status.get("type") if isinstance(raw_status, dict) else None
    if status not in VALID_THREAD_STATES:
        return None
    result: dict[str, Any] = {
        "threadId": thread_id,
        "sessionId": session_id,
        "parentThreadId": _text(value.get("parentThreadId"), 200),
        "status": status,
        "model": _text(value.get("model"), 200),
        "role": _text(value.get("agentRole"), 100),
        "nickname": _text(value.get("agentNickname"), 100),
        "updatedAt": value.get("updatedAt")
        if isinstance(value.get("updatedAt"), int) and not isinstance(value.get("updatedAt"), bool)
        else None,
        "source": "native-metadata",
    }
    if status == "active":
        flags = raw_status.get("activeFlags")
        if isinstance(flags, list):
            result["activeFlags"] = [item for item in flags[:20] if isinstance(item, str)]
    return result


def descendant_workers(root: object, rows: object) -> list[dict[str, Any]]:
    """Build only the native parent-linked tree rooted at ``root``.

    Codex assigns a distinct session identifier to a spawned child thread.  The
    explicit parent thread identifier is therefore the hierarchy authority;
    requiring a child's session to equal its parent drops real descendants.
    """
    normalized_root = normalize_thread(root)
    if normalized_root is None:
        raise WorkerDataError("native root thread metadata is invalid")
    if not isinstance(rows, list):
        raise WorkerDataError("native thread listing is invalid")
    candidates: dict[str, dict[str, Any]] = {}
    for raw in rows:
        item = normalize_thread(raw)
        if (
            item is not None
            and item["threadId"] != normalized_root["threadId"]
            and item.get("parentThreadId")
        ):
            # Input is newest-first and exact known-ID reads are placed first.
            # Preserve that authoritative row if a later page repeats the ID.
            candidates.setdefault(item["threadId"], item)
            if len(candidates) >= MAX_WORKERS:
                break
    descendants: list[dict[str, Any]] = []
    accepted = {normalized_root["threadId"]}
    remaining = dict(candidates)
    while remaining:
        found = [
            item for item in remaining.values()
            if item.get("parentThreadId") in accepted
        ]
        if not found:
            break
        found.sort(key=lambda item: (item.get("updatedAt") or 0, item["threadId"]))
        for item in found:
            accepted.add(item["threadId"])
            descendants.append(item)
            remaining.pop(item["threadId"], None)
    return descendants


def latest_active_turn(value: object) -> str | None:
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        return None
    for turn in value["data"]:
        if (
            isinstance(turn, dict)
            and turn.get("status") == "inProgress"
            and isinstance(turn.get("id"), str)
            and 0 < len(turn["id"]) <= 200
        ):
            return turn["id"]
    return None


class WorkerStore:
    """Persist a bounded metadata snapshot without prompts, paths, or transcript."""

    def __init__(self, state_dir: Path):
        self.directory = Path(state_dir) / "workers"
        self.available = False
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.directory.is_symlink() or not self.directory.is_dir():
                return
            os.chmod(self.directory, 0o700)
            self.available = True
        except OSError:
            return

    def _path(self, team: str) -> Path:
        return self.directory / f"{hashlib.sha256(team.encode('utf-8')).hexdigest()}.json"

    def save(self, team: str, root_thread_id: str, workers: list[dict[str, Any]]) -> None:
        if not self.available:
            return
        value = {
            "version": 1,
            "team": team,
            "rootThreadId": root_thread_id,
            "reconciledAtMs": int(time.time() * 1000),
            "workers": workers[:MAX_WORKERS],
        }
        encoded = (json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        if len(encoded) > 512 * 1024:
            raise WorkerDataError("native worker metadata snapshot is too large")
        fd, temporary = tempfile.mkstemp(prefix=".workers-", dir=self.directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path(team))
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def load(self, team: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        path = self._path(team)
        try:
            if (
                not path.exists()
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > 512 * 1024
            ):
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or value.get("team") != team
            or not _text(value.get("rootThreadId"), 200)
            or not isinstance(value.get("workers"), list)
            or (
                value.get("reconciledAtMs") is not None
                and (
                    isinstance(value.get("reconciledAtMs"), bool)
                    or not isinstance(value.get("reconciledAtMs"), int)
                )
            )
        ):
            return None
        workers = []
        for raw in value["workers"][:MAX_WORKERS]:
            if not isinstance(raw, dict):
                return None
            # Stored values already use the public normalized shape. Reject
            # unknown fields so a tampered file cannot surface arbitrary data.
            if set(raw) - {
                "threadId", "sessionId", "parentThreadId", "status", "model",
                "role", "nickname", "updatedAt", "source", "activeFlags",
                "activeTurnId",
            }:
                return None
            if not _text(raw.get("threadId"), 200) or not _text(raw.get("sessionId"), 200):
                return None
            if raw.get("status") not in VALID_THREAD_STATES:
                return None
            for key, limit in (
                ("parentThreadId", 200), ("model", 200), ("role", 100),
                ("nickname", 100), ("activeTurnId", 200),
            ):
                if raw.get(key) is not None and not _text(raw.get(key), limit):
                    return None
            if raw.get("source") != "native-metadata":
                return None
            if raw.get("updatedAt") is not None and (
                isinstance(raw.get("updatedAt"), bool)
                or not isinstance(raw.get("updatedAt"), int)
            ):
                return None
            if raw.get("activeFlags") is not None and (
                not isinstance(raw.get("activeFlags"), list)
                or len(raw["activeFlags"]) > 20
                or any(not _text(item, 100) for item in raw["activeFlags"])
            ):
                return None
            workers.append(dict(raw))
        return {
            "rootThreadId": value["rootThreadId"],
            "reconciledAtMs": value.get("reconciledAtMs"),
            "workers": workers,
        }
