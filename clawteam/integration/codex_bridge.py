#!/usr/bin/env python3
"""Native Codex app-server bridge for the local Company HQ UI.

The child process inherits the caller environment. This module never sets HOME,
CODEX_HOME, auth variables, or Codex configuration overrides.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from runtime_config import REPO_ROOT, codex_executable, runtime_dir

CODEX_PATH = codex_executable()
DEFAULT_STATE_DIR = runtime_dir()
SUPPORTED_MODELS = frozenset({
    "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
    "gpt-5.5", "gpt-5.3-codex-spark",
})
TEAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_PROMPT = 40_000
MAX_TEXT = 24_000
DEFAULT_TOKEN_BUDGET = 200_000
MAX_TOKEN_BUDGET = 20_000_000
MAX_EVENT_SNAPSHOT_BYTES = 4 * 1024 * 1024


class BridgeError(RuntimeError):
    """Safe bridge failure suitable for the local UI."""


class BridgeProtocolError(BridgeError):
    """The app-server rejected or timed out during a request."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_text(value: object, limit: int = MAX_TEXT) -> str:
    text = value if isinstance(value, str) else str(value)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[redacted]", text)
    text = re.sub(
        r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[redacted-email]",
        text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password)"
        r"\s*[:=]\s*([^\s,;]+)",
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )
    return text[:limit]


def _validate_team(team: str) -> str:
    if not isinstance(team, str) or not TEAM_RE.fullmatch(team):
        raise BridgeError("team must be a registered identifier")
    return team


def _validate_prompt(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise BridgeError("prompt must be non-empty text")
    if len(prompt) > MAX_PROMPT:
        raise BridgeError(f"prompt exceeds {MAX_PROMPT} characters")
    return prompt.strip()


def _validate_model(model: str) -> str:
    if model not in SUPPORTED_MODELS:
        raise BridgeError("model is not enabled for Company HQ")
    return model


def _validate_mode(mode: str) -> str:
    if mode not in {"plan", "execute", "full"}:
        raise BridgeError("mode must be plan, execute or full")
    return mode


def _numeric_tree(value: object) -> object:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(key): clean
            for key, item in value.items()
            if (clean := _numeric_tree(item)) is not None
        }
    if isinstance(value, list):
        return [clean for item in value if (clean := _numeric_tree(item)) is not None]
    return None


def _usage_summary(counts: dict[str, Any]) -> dict[str, Any]:
    """Summarize a native token usage payload without claiming billing facts.

    The Codex app-server payload shape can evolve. Treat a top-level ``total``
    object as the authoritative latest cumulative report when it exists, then
    recognize common token field names. The raw numeric tree stays available for
    inspection, but account-wide quota and billed cost remain outside this
    bridge.
    """
    source = counts.get("total") if isinstance(counts.get("total"), dict) else counts
    totals = {
        "inputTokens": 0,
        "cachedInputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
    }
    seen: set[str] = set()

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    if "cached" in normalized and "token" in normalized:
                        totals["cachedInputTokens"] += item
                        seen.add("cachedInputTokens")
                    elif "cache" in normalized and "input" in normalized:
                        totals["cachedInputTokens"] += item
                        seen.add("cachedInputTokens")
                    elif ("input" in normalized or "prompt" in normalized) and "token" in normalized:
                        totals["inputTokens"] += item
                        seen.add("inputTokens")
                    elif ("output" in normalized or "completion" in normalized) and "token" in normalized:
                        totals["outputTokens"] += item
                        seen.add("outputTokens")
                    elif normalized in {"totaltokens", "tokens"}:
                        totals["totalTokens"] = max(totals["totalTokens"], item)
                        seen.add("totalTokens")
                else:
                    visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(source)
    if totals["totalTokens"] == 0 and (
        totals["inputTokens"] or totals["outputTokens"]
    ):
        totals["totalTokens"] = totals["inputTokens"] + totals["outputTokens"]
        seen.add("totalTokens")
    summary = {
        key: int(value) if isinstance(value, float) and value.is_integer() else value
        for key, value in totals.items()
        if key in seen
    }
    summary["coverage"] = (
        "Latest native runtime token report only; not account quota, billing, or savings."
        if seen
        else "Native runtime reported token usage, but the fields were not recognized."
    )
    summary["latestCounts"] = counts
    return summary


def _supervisor_instructions(team: str, project: Path) -> str:
    return f"""You are the native Codex supervisor for Company HQ team {team!r}.
The approved project root is {str(project)!r}. Keep project writes inside that root.
Read the repository operating resources under {str(REPO_ROOT)!r} when useful.
For specialist work, consult agency-agents/USE.md under that repository and load
only the relevant role from its pinned upstream library. Product, research, UX,
marketing, engineering and QA guidance is selected as needed, never loaded as an
entire roster. Native skills and MCP tools must be actually available to use them.
Use registered Ruflo and codebase-memory tools when available; do not replace the
user's Codex configuration or account environment. Treat ClawTeam team IDs, task IDs, member IDs,
inboxes, and events as canonical coordination state. Delegate useful independent work
through native Codex collaboration tools. Company HQ's controlled routing selects the
overall supervisor model (currently gpt-6-astra). When nested delegation is useful,
prefer gpt-5.6-terra or gpt-5.6-sol for department leads and reserve gpt-5.6-luna for
small bounded leaf tasks. Do not promote Luna to a department lead without verified
nested-delegation capability. Report actual child thread IDs and observed states.
Keep task packets compact and use fork_turns="none" for delegated work. Do not
re-read all operating documents in every worker or spawn a scout for a trivial
lookup. During read-only planning, normally plan alone and create implementation
workers only after execution is enabled. A worker created during planning keeps
its original read-only permissions: do not ask it to bypass or escalate those
permissions. Start a fresh execution worker with a concise handoff if needed.
Never invent workers, liveness, completion, or tool results.
Never bypass approvals or sandbox protections."""


def _turn_input(prompt: str, attachments: list[dict] | None) -> list[dict]:
    return [{"type": "text", "text": prompt}] + [
        {"type": "localImage", "path": image["path"]} for image in (attachments or [])
    ]


def _user_message(prompt: str, attachments: list[dict] | None) -> dict:
    value = {"text": _safe_text(prompt)}
    if attachments:
        # File paths and raw image content are not copied into chat events.
        value['attachments'] = [{k: image[k] for k in ('id', 'name', 'url')} for image in attachments]
    return value


class _StdioConnection:
    def __init__(self, codex_path: Path):
        self.codex_path = codex_path
        self.process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._write_lock = threading.Lock()

    def start(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_exit: Callable[[str], None],
    ) -> None:
        if not self.codex_path.is_file() or not os.access(self.codex_path, os.X_OK):
            raise BridgeError(f"native Codex is unavailable: {self.codex_path}")
        # env=None deliberately preserves the original HOME/CODEX_HOME/auth context.
        self.process = subprocess.Popen(
            [str(self.codex_path), "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=None,
        )
        self._reader = threading.Thread(
            target=self._read_loop,
            args=(on_message, on_exit),
            name="company-hq-codex-reader",
            daemon=True,
        )
        self._reader.start()

    def _read_loop(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_exit: Callable[[str], None],
    ) -> None:
        assert self.process is not None and self.process.stdout is not None
        reason = "native Codex app-server closed its output"
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    on_message(message)
        except (OSError, ValueError) as exc:
            reason = f"native Codex reader stopped: {_safe_text(exc, 500)}"
        on_exit(reason)

    def send(self, message: dict[str, Any]) -> None:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None:
            raise BridgeError("native Codex app-server is not connected")
        line = json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
        with self._write_lock:
            process.stdin.write(line)
            process.stdin.flush()

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def close(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


@dataclass
class _PendingCall:
    ready: threading.Event = field(default_factory=threading.Event)
    result: object | None = None
    error: str | None = None


@dataclass
class _Approval:
    public_id: str
    wire_id: object
    method: str
    thread_id: str
    turn_id: str
    data: dict[str, Any]


@dataclass
class _TeamSession:
    team: str
    project: Path
    model: str
    connection: Any
    events: deque[dict[str, Any]]
    replay_events: deque[dict[str, Any]]
    mode: str = "plan"
    state: str = "starting"
    thread_id: str | None = None
    turn_id: str | None = None
    error: str | None = None
    next_request_id: int = 1
    next_event_seq: int = 1
    pending_calls: dict[object, _PendingCall] = field(default_factory=dict)
    approvals: dict[str, _Approval] = field(default_factory=dict)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed_turns: set[str] = field(default_factory=set)
    last_turn_status: str | None = None
    plan_ready: bool = False
    usage_summary: dict[str, Any] | None = None
    usage_event_count: int = 0
    pending_turn_notifications: list[tuple[Any, ...]] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    operation_lock: threading.Lock = field(default_factory=threading.Lock)
    closing: bool = False


class _BudgetStore:
    def __init__(self, state_dir: Path):
        self.directory = state_dir / "budgets"
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self._lock = threading.RLock()

    def _path(self, team: str) -> Path:
        digest = hashlib.sha256(team.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def _default(self, team: str) -> dict[str, Any]:
        return {
            "version": 1,
            "team": team,
            "limitTokens": DEFAULT_TOKEN_BUDGET,
            "enforced": True,
            "usedTokens": 0,
            "threadId": None,
            "lastNativeTotalTokens": 0,
            "exhaustedNotified": False,
            "updatedAtMs": _now_ms(),
        }

    def _clean_policy(self, limit_tokens: object, enforced: object) -> tuple[int, bool]:
        if isinstance(enforced, str):
            enforced = enforced.strip().lower() in {"1", "true", "yes", "on"}
        enforced = bool(enforced)
        if isinstance(limit_tokens, bool) or not isinstance(limit_tokens, (int, float, str)):
            raise BridgeError("token budget must be a number")
        try:
            limit = int(limit_tokens)
        except (TypeError, ValueError) as exc:
            raise BridgeError("token budget must be a number") from exc
        if limit < 0 or limit > MAX_TOKEN_BUDGET:
            raise BridgeError(f"token budget must be between 0 and {MAX_TOKEN_BUDGET}")
        return limit, enforced

    def _read_unlocked(self, team: str) -> dict[str, Any]:
        path = self._path(team)
        if not path.exists():
            return self._default(team)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
            raise BridgeError("budget state is not a regular small file")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeError("budget state is unreadable") from exc
        if not isinstance(value, dict) or value.get("team") != team:
            raise BridgeError("budget state does not match the requested team")
        default = self._default(team)
        limit, enforced = self._clean_policy(value.get("limitTokens", default["limitTokens"]), value.get("enforced", True))
        used = value.get("usedTokens", 0)
        last = value.get("lastNativeTotalTokens", 0)
        if isinstance(used, bool) or not isinstance(used, (int, float)) or used < 0:
            used = 0
        if isinstance(last, bool) or not isinstance(last, (int, float)) or last < 0:
            last = 0
        return {
            **default,
            "limitTokens": limit,
            "enforced": enforced,
            "usedTokens": int(used),
            "threadId": value.get("threadId") if isinstance(value.get("threadId"), str) else None,
            "lastNativeTotalTokens": int(last),
            "exhaustedNotified": bool(value.get("exhaustedNotified", False)),
            "updatedAtMs": value.get("updatedAtMs") if isinstance(value.get("updatedAtMs"), int) else _now_ms(),
        }

    def _write_unlocked(self, value: dict[str, Any]) -> dict[str, Any]:
        value = {**value, "updatedAtMs": _now_ms()}
        path = self._path(value["team"])
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        return value

    def set_policy(self, team: str, limit_tokens: object, enforced: object) -> dict[str, Any]:
        team = _validate_team(team)
        limit, enforce = self._clean_policy(limit_tokens, enforced)
        with self._lock:
            value = self._read_unlocked(team)
            value["limitTokens"] = limit
            value["enforced"] = enforce
            value["exhaustedNotified"] = False
            return self._write_unlocked(value)

    def status(self, team: str) -> dict[str, Any]:
        team = _validate_team(team)
        with self._lock:
            value = self._read_unlocked(team)
        return self._public(value)

    def authorize(self, team: str) -> dict[str, Any]:
        team = _validate_team(team)
        status = self.status(team)
        if status["blocked"]:
            raise BridgeError(status["reason"])
        return status

    def record_usage(self, team: str, thread_id: str | None, native_total_tokens: int | None) -> tuple[dict[str, Any], bool]:
        team = _validate_team(team)
        if native_total_tokens is None or native_total_tokens < 0:
            return self.status(team), False
        with self._lock:
            value = self._read_unlocked(team)
            previous_thread = value.get("threadId")
            previous_total = int(value.get("lastNativeTotalTokens") or 0)
            if previous_thread == thread_id:
                delta = max(0, native_total_tokens - previous_total)
            else:
                delta = native_total_tokens
            value["usedTokens"] = int(value.get("usedTokens") or 0) + delta
            value["threadId"] = thread_id
            value["lastNativeTotalTokens"] = native_total_tokens
            status = self._public(value)
            notify = bool(status["blocked"] and not value.get("exhaustedNotified"))
            if notify:
                value["exhaustedNotified"] = True
            self._write_unlocked(value)
        return status, notify

    def _public(self, value: dict[str, Any]) -> dict[str, Any]:
        limit = int(value.get("limitTokens") or 0)
        used = int(value.get("usedTokens") or 0)
        enforced = bool(value.get("enforced", True))
        remaining = None if limit <= 0 else max(0, limit - used)
        blocked = bool(enforced and limit > 0 and used >= limit)
        return {
            "limitTokens": limit,
            "usedTokens": used,
            "remainingTokens": remaining,
            "usedPercent": round(100 * used / limit, 1) if limit > 0 else None,
            "remainingPercent": round(max(0, 100 * (limit - used) / limit), 1) if limit > 0 else None,
            "enforced": enforced,
            "blocked": blocked,
            "reason": (
                f"Chat budget exhausted: {100 * used / limit:.0f}% used, 0% remaining. Adjust this chat's allowance to continue. Account limits are separate."
                if blocked else None
            ),
            "enforcement": "native-goal-best-effort + Company HQ action gate",
            "coverage": "Counts provider-reported native totalTokens. This is not billed money or account-wide quota.",
        }


def _native_total_tokens(counts: dict[str, Any]) -> int | None:
    total = counts.get("total") if isinstance(counts.get("total"), dict) else counts
    if isinstance(total, dict):
        for key in ("totalTokens", "tokens"):
            value = total.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    value = counts.get("totalTokens")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def _safe_event_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_safe_event_value(item) for item in value[:500]]
    if isinstance(value, dict):
        return {
            _safe_text(key, 200): _safe_event_value(item)
            for key, item in list(value.items())[:500]
        }
    return _safe_text(value)


class _EventStore:
    """Small private replay snapshots; never a copy of provider history."""

    def __init__(self, state_dir: Path, max_events: int):
        self.directory = state_dir / "events"
        self.max_events = max_events
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

    def _cursor_path(self, team: str) -> Path:
        return self.directory / f"{hashlib.sha256(team.encode('utf-8')).hexdigest()}.cursor.json"

    def next_sequence(self, team: str, fallback: int) -> int:
        if not self.available:
            return fallback
        path = self._cursor_path(team)
        try:
            if not path.exists() or path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
                return fallback
            value = json.loads(path.read_text(encoding="utf-8"))
            next_seq = value.get("nextSeq") if isinstance(value, dict) and value.get("team") == team else None
            if isinstance(next_seq, int) and not isinstance(next_seq, bool) and next_seq >= fallback:
                return next_seq
        except (OSError, json.JSONDecodeError):
            pass
        return fallback

    def record_next_sequence(self, team: str, next_seq: int) -> None:
        if not self.available:
            return
        try:
            temporary = self.directory / f".{self._cursor_path(team).name}.{uuid.uuid4().hex}.tmp"
            temporary.write_text(json.dumps({"team": team, "nextSeq": next_seq}, separators=(",", ":")), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self._cursor_path(team))
        except OSError:
            return

    def load(self, team: str) -> list[dict[str, Any]]:
        if not self.available:
            return []
        path = self._path(team)
        try:
            if not path.exists() or path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVENT_SNAPSHOT_BYTES:
                return []
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(value, dict) or value.get("team") != team or not isinstance(value.get("events"), list):
            return []
        events = []
        previous_seq = 0
        for event in value["events"][-self.max_events:]:
            if not isinstance(event, dict):
                return []
            seq = event.get("seq")
            if not isinstance(seq, int) or isinstance(seq, bool) or seq <= previous_seq:
                return []
            event_type = event.get("type")
            if not isinstance(event_type, str) or len(event_type) > 200 or not isinstance(event.get("data"), dict):
                return []
            previous_seq = seq
            events.append({
                "seq": seq,
                "time": event.get("time") if isinstance(event.get("time"), int) else 0,
                "type": event_type,
                "threadId": event.get("threadId") if isinstance(event.get("threadId"), str) else None,
                "turnId": event.get("turnId") if isinstance(event.get("turnId"), str) else None,
                "itemId": event.get("itemId") if isinstance(event.get("itemId"), str) else None,
                "data": _safe_event_value(event["data"]),
            })
        return events

    def save(self, team: str, events: list[dict[str, Any]]) -> None:
        if not self.available:
            return
        clean = [_safe_event_value(event) for event in events[-self.max_events:]]
        kept = []
        for event in reversed(clean):
            candidate = {"version": 1, "team": team, "events": [event, *kept]}
            try:
                if len(json.dumps(candidate, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > MAX_EVENT_SNAPSHOT_BYTES:
                    break
            except (TypeError, ValueError):
                return
            kept.insert(0, event)
        payload = {"version": 1, "team": team, "events": kept}
        try:
            temporary = self.directory / f".{self._path(team).name}.{uuid.uuid4().hex}.tmp"
            temporary.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self._path(team))
        except OSError:
            return


class CodexBridge:
    """Synchronous, thread-safe facade over asynchronous app-server JSONL."""

    def __init__(
        self,
        state_dir: Path = DEFAULT_STATE_DIR,
        codex_path: Path = CODEX_PATH,
        max_events: int = 500,
        request_timeout: float = 15.0,
        connection_factory: Callable[[Path], Any] | None = None,
    ) -> None:
        if not 20 <= max_events <= 5000:
            raise ValueError("max_events must be between 20 and 5000")
        self.state_dir = Path(state_dir).resolve()
        self.binding_dir = self.state_dir / "bindings"
        self.binding_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        os.chmod(self.binding_dir, 0o700)
        self.codex_path = Path(codex_path)
        self.max_events = max_events
        self.request_timeout = request_timeout
        self.connection_factory = connection_factory or _StdioConnection
        self._sessions: dict[str, _TeamSession] = {}
        self._sessions_lock = threading.RLock()
        self._binding_lock = threading.Lock()
        self._budget = _BudgetStore(self.state_dir)
        self._event_store = _EventStore(self.state_dir, max_events)
        atexit.register(self.shutdown_all)

    def _binding_path(self, team: str) -> Path:
        digest = hashlib.sha256(team.encode("utf-8")).hexdigest()
        return self.binding_dir / f"{digest}.json"

    def _read_binding(self, team: str) -> dict[str, Any] | None:
        path = self._binding_path(team)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
            raise BridgeError("runtime binding is not a regular small file")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeError("runtime binding is unreadable") from exc
        if not isinstance(value, dict) or value.get("team") != team:
            raise BridgeError("runtime binding does not match the requested team")
        if not isinstance(value.get("projectRoot"), str):
            raise BridgeError("runtime binding is invalid")
        if value.get("threadId") is not None and not isinstance(value["threadId"], str):
            raise BridgeError("runtime binding is invalid")
        if value.get("mode") not in {None, "plan", "execute", "full"}:
            raise BridgeError("runtime binding is invalid")
        if value.get("planReady") not in {None, True, False}:
            raise BridgeError("runtime binding is invalid")
        return value

    def _write_binding(
        self,
        team: str,
        project: Path,
        thread_id: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        plan_ready: bool | None = None,
    ) -> None:
        path = self._binding_path(team)
        previous = self._read_binding(team) or {}
        value = {
            "team": team,
            "projectRoot": str(project),
            "threadId": thread_id if thread_id is not None else previous.get("threadId"),
            "model": model if model is not None else previous.get("model"),
            "mode": mode if mode is not None else previous.get("mode"),
            "planReady": (
                plan_ready
                if plan_ready is not None
                else bool(previous.get("planReady", False))
            ),
            "updatedAtMs": _now_ms(),
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)

    def set_budget(self, team: str, limit_tokens: object, enforced: object = True) -> dict[str, Any]:
        team = _validate_team(team)
        value = self._budget.set_policy(team, limit_tokens, enforced)
        with self._sessions_lock:
            session = self._sessions.get(team)
        if session and session.thread_id:
            self._set_native_goal(session)
        return self._budget.status(team)

    def _set_native_goal(self, session: _TeamSession) -> None:
        budget = self._budget.status(session.team)
        if not budget["enforced"] or budget["limitTokens"] <= 0 or not session.thread_id:
            return
        remaining = budget["remainingTokens"]
        if not isinstance(remaining, int) or remaining <= 0:
            return
        try:
            self._rpc(session, "thread/goal/set", {
                "threadId": session.thread_id,
                "tokenBudget": remaining,
            })
            self._event(session, "budget.goal", {
                "text": "Native token goal applied",
                "remainingTokens": remaining,
            })
        except Exception as exc:
            self._event(session, "budget.goal_failed", {
                "text": _safe_text(exc, 1000),
                "remainingTokens": remaining,
            })

    def _bind_project(self, team: str, project: Path) -> tuple[Path, dict[str, Any] | None]:
        try:
            resolved = project.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise BridgeError("approved project root does not exist") from exc
        if not resolved.is_dir():
            raise BridgeError("approved project root must be a directory")
        with self._binding_lock:
            binding = self._read_binding(team)
            if binding:
                try:
                    bound = Path(binding["projectRoot"]).resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise BridgeError("bound project root is unavailable") from exc
                if bound != resolved:
                    raise BridgeError("team is already bound to a different project root")
            else:
                self._write_binding(team, resolved, mode="plan", plan_ready=False)
        return resolved, binding

    def _new_session(
        self,
        team: str,
        project: Path,
        model: str,
        mode: str,
        plan_ready: bool = False,
    ) -> _TeamSession:
        restored = self._event_store.load(team)
        next_event_seq = self._event_store.next_sequence(
            team, (restored[-1]["seq"] + 1) if restored else 1,
        )
        session = _TeamSession(
            team=team,
            project=project,
            model=model,
            mode=mode,
            plan_ready=plan_ready,
            connection=self.connection_factory(self.codex_path),
            events=deque(restored, maxlen=self.max_events),
            replay_events=deque(restored, maxlen=self.max_events),
            next_event_seq=next_event_seq,
        )
        with self._sessions_lock:
            current = self._sessions.get(team)
            if current is not None and (
                current.connection.running()
                or current.state not in {"offline", "error"}
            ):
                raise BridgeError("team already has a connected native supervisor")
            if current is not None:
                current.connection.close()
            self._sessions[team] = session
        self._event(session, "status", {"text": "Starting native Codex supervisor"})
        session.connection.start(
            lambda message: self._on_message(session, message),
            lambda reason: self._on_exit(session, reason),
        )
        return session

    def _rpc(self, session: _TeamSession, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with session.lock:
            request_id = session.next_request_id
            session.next_request_id += 1
            pending = _PendingCall()
            session.pending_calls[request_id] = pending
        try:
            session.connection.send({"method": method, "id": request_id, "params": params})
        except Exception:
            with session.lock:
                session.pending_calls.pop(request_id, None)
            raise
        if not pending.ready.wait(self.request_timeout):
            with session.lock:
                session.pending_calls.pop(request_id, None)
            raise BridgeProtocolError(f"native Codex timed out during {method}")
        if pending.error:
            raise BridgeProtocolError(pending.error)
        return pending.result if isinstance(pending.result, dict) else {}

    def _notify(self, session: _TeamSession, method: str, params: dict[str, Any]) -> None:
        session.connection.send({"method": method, "params": params})

    def start(
        self,
        team: str,
        project: str | Path,
        prompt: str,
        model: str,
        *,
        work_mode: str = "plan",
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        team = _validate_team(team)
        prompt = _validate_prompt(prompt)
        model = _validate_model(model)
        if work_mode not in {"plan", "auto", "full"}:
            raise BridgeError("choose plan, auto or full work mode")
        self._budget.authorize(team)
        project_path, binding = self._bind_project(team, Path(project))
        # New chats may use the user's explicit automatic-work choice. A
        # resumed chat keeps its persisted permission boundary; a new UI
        # preference must not silently upgrade an existing planning chat.
        mode = (
            binding.get("mode") or "plan"
            if binding and binding.get("threadId")
            else ("full" if work_mode == "full" else "execute" if work_mode == "auto" else "plan")
        )
        mode = _validate_mode(mode)
        plan_ready = bool(binding.get("planReady", False)) if binding else False
        session = self._new_session(
            team, project_path, model, mode, plan_ready=plan_ready
        )
        try:
            self._rpc(session, "initialize", {
                "clientInfo": {
                    "name": "company_hq_clawteam",
                    "title": "Company HQ ClawTeam",
                    "version": "1.0.0",
                }
            })
            self._notify(session, "initialized", {})
            common = {
                "cwd": str(project_path),
                "model": model,
                "approvalPolicy": "never" if mode == "full" else "on-request",
                "approvalsReviewer": "user",
                "sandbox": "danger-full-access" if mode == "full" else "read-only" if mode == "plan" else "workspace-write",
                "developerInstructions": _supervisor_instructions(team, project_path)
                + (
                    "\nThis session begins in read-only planning mode. Clarify only material unknowns, "
                    "inspect efficiently, and return a concise plan with deliverables, owners, likely "
                    "model tier, verification, risks, and user decisions. Do not attempt project writes "
                    "until Company HQ explicitly changes the session to execution mode."
                    if mode == "plan"
                    else "\nThe user enabled automatic work in this workspace. Plan proportionately and proceed with the requested implementation and checks; do not wait for a separate plan approval. Native sandbox and permission requirements still apply."
                ),
            }
            previous_thread = binding.get("threadId") if binding else None
            if isinstance(previous_thread, str) and previous_thread:
                result = self._rpc(
                    session, "thread/resume", {"threadId": previous_thread, **common}
                )
            else:
                result = self._rpc(session, "thread/start", common)
            thread = result.get("thread")
            thread_id = thread.get("id") if isinstance(thread, dict) else None
            if not isinstance(thread_id, str) or not thread_id:
                raise BridgeProtocolError("native Codex did not return a thread ID")
            with session.lock:
                session.thread_id = thread_id
                session.state = "idle"
            with self._binding_lock:
                self._write_binding(
                    team,
                    project_path,
                    thread_id,
                    model,
                    mode,
                    plan_ready=session.plan_ready,
                )
            self._set_native_goal(session)
            self._event(session, "thread.started", {
                "text": "Native supervisor connected",
                "mode": mode,
            })
            self._start_turn(session, prompt, attachments=attachments)
            return self.status(team)
        except Exception as exc:
            with session.lock:
                session.state = "error"
                session.error = _safe_text(exc, 1000)
            self._event(session, "error", {"text": session.error})
            session.connection.close()
            raise

    def _start_turn(
        self,
        session: _TeamSession,
        prompt: str,
        *,
        record_user_message: bool = True,
        attachments: list[dict] | None = None,
    ) -> str:
        if not session.thread_id:
            raise BridgeError("team has no native Codex thread")
        self._budget.authorize(session.team)
        self._begin_turn_notification_buffer(session)
        try:
            result = self._rpc(session, "turn/start", {
                "threadId": session.thread_id,
                "input": _turn_input(prompt, attachments),
                "cwd": str(session.project),
                "model": session.model,
                "approvalPolicy": "never" if session.mode == "full" else "on-request",
                "approvalsReviewer": "user",
                "sandboxPolicy": (
                    {"type": "dangerFullAccess"} if session.mode == "full" else
                    {"type": "readOnly"}
                    if session.mode == "plan"
                    else {
                        "type": "workspaceWrite",
                        "writableRoots": [str(session.project)],
                        "networkAccess": False,
                    }
                ),
            })
            turn = result.get("turn")
            turn_id = turn.get("id") if isinstance(turn, dict) else None
            if not isinstance(turn_id, str) or not turn_id:
                raise BridgeProtocolError("native Codex did not return a turn ID")
            with session.lock:
                session.turn_id = turn_id
                session.last_turn_status = None
                if session.mode == "plan":
                    session.plan_ready = False
                session.state = "idle" if turn_id in session.completed_turns else "running"
                session.error = None
            if session.mode == "plan":
                with self._binding_lock:
                    self._write_binding(
                        session.team,
                        session.project,
                        session.thread_id,
                        session.model,
                        session.mode,
                        plan_ready=False,
                    )
            # The native runtime accepted this exact input. Emit it only after
            # the response supplies a valid turn ID and before its output.
            if record_user_message:
                self._event(session, "message.user", _user_message(prompt, attachments), turn_id=turn_id)
            self._event(session, "turn.started", {
                "text": "Supervisor turn started",
                "mode": session.mode,
            })
            return turn_id
        finally:
            self._flush_turn_notification_buffer(session)

    def begin_execution(
        self,
        team: str,
        prompt: str = (
            "The user approved the current plan. Begin bounded execution now. "
            "Do not repeat planning or ask for plan approval again. Existing workers "
            "created in read-only planning retain read-only permissions. Do not resume "
            "them for writes or ask them to escape their sandbox. If delegation is "
            "useful, create a fresh execution worker now with fork_turns=none and a "
            "compact task packet containing the approved scope and findings. Use the "
            "smallest capable authorized worker; avoid extra management for simple "
            "work. Verify changes and honor native permission requests."
        ),
    ) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        prompt = _validate_prompt(prompt)
        self._budget.authorize(team)
        with session.operation_lock:
            with session.lock:
                if session.state != "idle" or not session.thread_id:
                    raise BridgeError(
                        "wait for the planning turn to finish before starting execution"
                    )
                if session.mode != "plan":
                    raise BridgeError("execution is already enabled for this session")
                if session.last_turn_status != "completed" or not session.plan_ready:
                    raise BridgeError(
                        "the planning turn must complete successfully before execution"
                    )
                thread_id = session.thread_id
                project = session.project
                model = session.model
            # Persist first. If this write fails, the live session remains in
            # read-only planning mode rather than becoming less restrictive
            # than the durable binding.
            with self._binding_lock:
                self._write_binding(
                    team,
                    project,
                    thread_id,
                    model,
                    "execute",
                    plan_ready=False,
                )
            with session.lock:
                session.mode = "execute"
                session.plan_ready = False
            self._event(session, "mode.changed", {
                "text": "Plan approved; execution enabled",
                "mode": "execute",
            })
            turn_id = self._start_turn(session, prompt, record_user_message=False)
        return {
            "accepted": True,
            "mode": "execute",
            "threadId": thread_id,
            "turnId": turn_id,
        }

    def send(self, team: str, prompt: str, *, attachments: list[dict] | None = None) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        prompt = _validate_prompt(prompt)
        self._budget.authorize(team)
        with session.operation_lock:
            with session.lock:
                state, thread_id, turn_id = session.state, session.thread_id, session.turn_id
            if not thread_id or state in {"starting", "stopping", "error", "offline"}:
                raise BridgeError(f"team supervisor cannot accept input while {state}")
            if state in {"running", "awaiting_approval"} and turn_id:
                self._budget.authorize(team)
                self._begin_turn_notification_buffer(session)
                try:
                    result = self._rpc(session, "turn/steer", {
                        "threadId": thread_id,
                        "expectedTurnId": turn_id,
                        "input": _turn_input(prompt, attachments),
                    })
                    if result.get("turnId") != turn_id:
                        raise BridgeProtocolError("native Codex steered a different turn")
                    self._event(session, "message.user", _user_message(prompt, attachments), turn_id=turn_id)
                    mode = "turn/steer"
                finally:
                    self._flush_turn_notification_buffer(session)
            else:
                turn_id = self._start_turn(session, prompt, attachments=attachments)
                mode = "turn/start"
        return {"accepted": True, "mode": mode, "threadId": thread_id, "turnId": turn_id}

    def tools(self, team: str) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        with session.lock:
            thread_id = session.thread_id
        if not thread_id or not session.connection.running():
            raise BridgeError('Connect this chat before checking its runtime tools')
        from native_tools import inventory
        return inventory(lambda method, params: self._rpc(session, method, params), thread_id, str(session.project), REPO_ROOT)

    def stop(self, team: str) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        with session.operation_lock:
            with session.lock:
                thread_id, turn_id, state = session.thread_id, session.turn_id, session.state
                if state not in {"running", "awaiting_approval"} or not thread_id or not turn_id:
                    return {"accepted": False, "threadId": thread_id, "turnId": turn_id}
                session.state = "stopping"
            self._event(session, "status", {"text": "Stopping supervisor turn"})
            self._rpc(session, "turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
        return {"accepted": True, "threadId": thread_id, "turnId": turn_id}

    def set_access(self, team: str, access: str) -> dict[str, Any]:
        """Explicit per-chat selection; never changes global provider defaults."""
        if access not in {'workspace', 'full'}:
            raise BridgeError('Choose workspace or full access')
        session = self._require_session(_validate_team(team))
        with session.operation_lock:
            with session.lock:
                if session.state != 'idle' or not session.thread_id:
                    raise BridgeError('Finish or stop the current turn before changing access')
                if session.mode == 'plan':
                    raise BridgeError('Approve the plan before changing execution access')
                mode = 'full' if access == 'full' else 'execute'
                with self._binding_lock:
                    self._write_binding(team, session.project, session.thread_id, session.model, mode, plan_ready=False)
                session.mode = mode
            self._event(session, 'mode.changed', {'text': 'Full access selected for this chat' if access == 'full' else 'Workspace access selected for this chat', 'mode': 'execute', 'accessMode': access})
        return self.status(team)

    def approve(self, team: str, request_id: str, decision: str) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        if decision not in {"approve", "reject"}:
            raise BridgeError("decision must be approve or reject")
        self._budget.authorize(team)
        with session.operation_lock:
            with session.lock:
                if session.mode == "plan":
                    raise BridgeError("approvals cannot be granted during read-only planning")
                if session.state != "awaiting_approval":
                    raise BridgeError("team is not awaiting an approval")
                approval = session.approvals.get(request_id)
                if not approval:
                    raise BridgeError("approval request is unknown or already resolved")
                if approval.thread_id != session.thread_id or approval.turn_id != session.turn_id:
                    raise BridgeError("approval request does not belong to the active team turn")
            result = self._approval_response(approval.method, decision)
            session.connection.send({"id": approval.wire_id, "result": result})
            with session.lock:
                session.approvals.pop(request_id, None)
                session.state = "awaiting_approval" if session.approvals else "running"
            self._event(session, "approval.resolved", {
                "text": "Approval resolved",
                "requestId": request_id,
                "decision": decision,
            })
        return {"accepted": True, "requestId": request_id, "decision": decision}

    @staticmethod
    def _approval_response(method: str, decision: str) -> dict[str, Any]:
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            return {"decision": "accept" if decision == "approve" else "decline"}
        if method in {"execCommandApproval", "applyPatchApproval"}:
            return {"decision": "approved" if decision == "approve" else "denied"}
        raise BridgeError("unsupported approval request")

    def status(self, team: str) -> dict[str, Any]:
        team = _validate_team(team)
        with self._sessions_lock:
            session = self._sessions.get(team)
        if not session:
            binding = self._read_binding(team)
            budget = self._budget.status(team)
            return {
                "team": team,
                "state": "offline",
                "connected": False,
                "project": binding.get("projectRoot") if binding else None,
                "model": binding.get("model") if binding else None,
                "mode": "execute" if binding and binding.get("mode") == "full" else binding.get("mode", "plan") if binding else "plan",
                "accessMode": "full" if binding and binding.get("mode") == "full" else "workspace",
                "planReady": bool(binding.get("planReady", False)) if binding else False,
                "threadId": binding.get("threadId") if binding else None,
                "turnId": None,
                "lastEventSeq": 0,
                "pendingApprovals": [],
                "children": [],
                "usageSummary": None,
                "budget": budget,
                "limits": {"blockedReason": budget["reason"]} if budget["blocked"] else {},
            }
        with session.lock:
            budget = self._budget.status(team)
            result = {
                "team": team,
                "state": session.state,
                "connected": bool(session.connection.running()),
                "project": str(session.project),
                "model": session.model,
                "mode": "execute" if session.mode == "full" else session.mode,
                "accessMode": "full" if session.mode == "full" else "workspace",
                "planReady": session.plan_ready,
                "threadId": session.thread_id,
                "turnId": session.turn_id,
                "lastEventSeq": session.next_event_seq - 1,
                "pendingApprovals": [dict(item.data) for item in session.approvals.values()],
                "children": [dict(value) for value in session.children.values()],
                "usageSummary": dict(session.usage_summary) if session.usage_summary else None,
                "budget": budget,
                "limits": {"blockedReason": budget["reason"]} if budget["blocked"] else {},
            }
            if session.error:
                result["error"] = session.error
            return result

    def events(self, team: str, after_seq: int = 0) -> dict[str, Any]:
        team = _validate_team(team)
        if not isinstance(after_seq, int) or isinstance(after_seq, bool) or after_seq < 0:
            raise BridgeError("after_seq must be a non-negative integer")
        with self._sessions_lock:
            session = self._sessions.get(team)
        if not session:
            restored = self._event_store.load(team)
            oldest = restored[0]["seq"] if restored else after_seq + 1
            saved_next = (restored[-1]["seq"] + 1) if restored else 1
            next_seq = max(after_seq, self._event_store.next_sequence(team, saved_next) - 1)
            return {
                "team": team,
                "afterSeq": after_seq,
                "nextSeq": next_seq,
                "truncated": after_seq + 1 < oldest,
                "events": [dict(event) for event in restored if event["seq"] > after_seq],
            }
        with session.lock:
            visible = self._visible_events(session, after_seq)
            oldest = session.events[0]["seq"] if session.events else session.next_event_seq
            return {
                "team": team,
                "afterSeq": after_seq,
                "nextSeq": session.next_event_seq - 1,
                "truncated": after_seq + 1 < oldest,
                "events": visible,
            }

    def _visible_events(self, session: _TeamSession, after_seq: int) -> list[dict[str, Any]]:
        """Keep completed conversation history when streaming traffic fills the ring."""
        durable = [event for event in session.replay_events if event["seq"] > after_seq]
        durable_ids = {event["seq"] for event in durable}
        tail = [
            event for event in session.events
            if event["seq"] > after_seq and event["seq"] not in durable_ids
        ]
        remaining = max(0, self.max_events - len(durable))
        selected_tail = tail[-remaining:] if remaining else []
        return [dict(event) for event in sorted([*durable, *selected_tail], key=lambda event: event["seq"])]

    def _event(
        self,
        session: _TeamSession,
        event_type: str,
        data: dict[str, Any],
        thread_id: str | None = None,
        turn_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        with session.lock:
            event = {
                "seq": session.next_event_seq,
                "time": _now_ms(),
                "type": event_type,
                "threadId": thread_id or session.thread_id,
                "turnId": turn_id or session.turn_id,
                "itemId": item_id,
                "data": data,
            }
            session.events.append(event)
            if event_type != "message.delta":
                session.replay_events.append(event)
            session.next_event_seq += 1
            self._event_store.record_next_sequence(session.team, session.next_event_seq)
            snapshot = list(session.replay_events)
            if event_type != "message.delta":
                self._event_store.save(session.team, snapshot)

    def _on_message(self, session: _TeamSession, message: dict[str, Any]) -> None:
        if "id" in message and ("result" in message or "error" in message):
            with session.lock:
                pending = session.pending_calls.pop(message["id"], None)
            if pending:
                if "error" in message:
                    error = message.get("error")
                    raw = error.get("message") if isinstance(error, dict) else "request failed"
                    pending.error = _safe_text(raw, 1000)
                else:
                    pending.result = message.get("result")
                pending.ready.set()
            return
        method, params = message.get("method"), message.get("params")
        if not isinstance(method, str) or not isinstance(params, dict):
            return
        if "id" in message:
            self._handle_server_request(session, message["id"], method, params)
        else:
            self._handle_notification(session, method, params)

    def _handle_server_request(
        self,
        session: _TeamSession,
        wire_id: object,
        method: str,
        params: dict[str, Any],
    ) -> None:
        with session.lock:
            if session.pending_turn_notifications is not None:
                session.pending_turn_notifications.append(("request", wire_id, method, params))
                return
        self._process_server_request(session, wire_id, method, params)

    def _process_server_request(
        self,
        session: _TeamSession,
        wire_id: object,
        method: str,
        params: dict[str, Any],
    ) -> None:
        approval_methods = {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "execCommandApproval",
            "applyPatchApproval",
        }
        if method in approval_methods:
            with session.lock:
                planning = session.mode == "plan"
            if planning:
                session.connection.send({
                    "id": wire_id,
                    "result": self._approval_response(method, "reject"),
                })
                self._event(session, "request.denied", {
                    "text": "Write or command approval denied during read-only planning",
                    "kind": method,
                    "mode": "plan",
                })
                return
            thread_id = params.get("threadId") or params.get("conversationId")
            turn_id = params.get("turnId") or session.turn_id
            if thread_id != session.thread_id or turn_id != session.turn_id:
                session.connection.send({
                    "id": wire_id,
                    "result": self._approval_response(method, "reject"),
                })
                return
            public_id = uuid.uuid4().hex
            kind = "command" if "Command" in method or method == "execCommandApproval" else "fileChange"
            data = {
                "requestId": public_id,
                "kind": kind,
                "reason": _safe_text(params.get("reason", "Approval required"), 2000),
                "command": _safe_text(params.get("command", ""), 4000),
                "cwd": _safe_text(params.get("cwd", str(session.project)), 2000),
                "availableDecisions": ["approve", "reject"],
            }
            approval = _Approval(public_id, wire_id, method, thread_id, turn_id, data)
            with session.lock:
                session.approvals[public_id] = approval
                session.state = "awaiting_approval"
            self._event(
                session,
                "approval.requested",
                {"text": data["reason"], **data},
                thread_id,
                turn_id,
                params.get("itemId") or params.get("callId"),
            )
            return
        safe_results = {
            "item/permissions/requestApproval": {
                "permissions": {}, "scope": "turn", "strictAutoReview": True,
            },
            "mcpServer/elicitation/request": {"action": "decline", "content": None},
            "item/tool/requestUserInput": {"answers": {}},
            "item/tool/call": {
                "success": False,
                "contentItems": [{"type": "inputText", "text": "Unsupported client tool"}],
            },
        }
        if method in safe_results:
            session.connection.send({"id": wire_id, "result": safe_results[method]})
        else:
            session.connection.send({
                "id": wire_id,
                "error": {"code": -32601, "message": "Unsupported client request"},
            })
        self._event(session, "request.denied", {
            "text": "Unsupported native request was denied", "kind": method,
        })

    @staticmethod
    def _begin_turn_notification_buffer(session: _TeamSession) -> None:
        with session.lock:
            if session.pending_turn_notifications is not None:
                raise BridgeError("native turn registration is already in progress")
            session.pending_turn_notifications = []

    def _flush_turn_notification_buffer(self, session: _TeamSession) -> None:
        # Retain the session lock while draining so notifications arriving at
        # the same instant cannot overtake the accepted user entry.
        with session.lock:
            pending = session.pending_turn_notifications or []
            session.pending_turn_notifications = None
            for item in pending:
                if item[0] == "notification":
                    _, method, params = item
                    self._process_notification(session, method, params)
                else:
                    _, wire_id, method, params = item
                    self._process_server_request(session, wire_id, method, params)

    def _handle_notification(
        self,
        session: _TeamSession,
        method: str,
        params: dict[str, Any],
    ) -> None:
        with session.lock:
            if session.pending_turn_notifications is not None:
                session.pending_turn_notifications.append(("notification", method, params))
                return
        self._process_notification(session, method, params)

    def _process_notification(
        self,
        session: _TeamSession,
        method: str,
        params: dict[str, Any],
    ) -> None:
        thread_id, turn_id = params.get("threadId"), params.get("turnId")
        if isinstance(thread_id, str) and session.thread_id and thread_id != session.thread_id:
            return
        if method == "turn/started":
            turn = params.get("turn")
            native_id = turn.get("id") if isinstance(turn, dict) else turn_id
            if isinstance(native_id, str):
                with session.lock:
                    session.turn_id = native_id
                    session.state = "running"
                self._event(session, "turn.started", {"text": "Supervisor turn started"})
            return
        if method == "turn/completed":
            turn = params.get("turn")
            status = turn.get("status", "completed") if isinstance(turn, dict) else "completed"
            native_id = turn.get("id") if isinstance(turn, dict) else turn_id
            with session.lock:
                session.approvals.clear()
                session.last_turn_status = str(status)
                session.plan_ready = (
                    session.mode == "plan" and status == "completed"
                )
                if isinstance(native_id, str):
                    session.turn_id = native_id
                    if status == "completed":
                        session.completed_turns.add(native_id)
                session.state = "error" if status == "failed" else "idle"
                persist_plan_ready = session.plan_ready
                persist_mode = session.mode
                persist_project = session.project
                persist_thread = session.thread_id
                persist_model = session.model
            if persist_mode == "plan":
                with self._binding_lock:
                    self._write_binding(
                        session.team,
                        persist_project,
                        persist_thread,
                        persist_model,
                        persist_mode,
                        plan_ready=persist_plan_ready,
                    )
            self._event(session, "turn.completed", {
                "text": f"Supervisor turn {status}", "status": status,
            })
            return
        if method == "item/agentMessage/delta":
            self._event(
                session,
                "message.delta",
                {"text": _safe_text(params.get("delta", ""))},
                thread_id,
                turn_id,
                params.get("itemId"),
            )
            return
        if method in {"item/started", "item/completed"}:
            self._handle_item(session, method, params)
            return
        if method == "thread/tokenUsage/updated":
            raw_counts = _numeric_tree(params.get("tokenUsage")) or {}
            counts = raw_counts if isinstance(raw_counts, dict) else {"value": raw_counts}
            summary = _usage_summary(counts)
            budget_status, budget_notify = self._budget.record_usage(session.team, thread_id or session.thread_id, _native_total_tokens(counts))
            with session.lock:
                session.usage_event_count += 1
                summary["eventCount"] = session.usage_event_count
                session.usage_summary = summary
            if budget_notify:
                self._event(session, "budget.exhausted", {"text": budget_status["reason"], **budget_status}, thread_id, turn_id)
            self._event(
                session,
                "usage",
                {"text": "Token usage updated", "counts": counts, "summary": summary},
                thread_id,
                turn_id,
            )
            return
        if method == "thread/status/changed":
            self._event(session, "status", {
                "text": "Native thread status changed", "status": params.get("status"),
            }, thread_id)
            return
        if method == "error":
            error = params.get("error")
            raw = error.get("message", error) if isinstance(error, dict) else error
            self._event(session, "error", {"text": _safe_text(raw, 2000)})

    def _handle_item(
        self,
        session: _TeamSession,
        method: str,
        params: dict[str, Any],
    ) -> None:
        item = params.get("item")
        if not isinstance(item, dict):
            return
        item_type, item_id = item.get("type"), item.get("id")
        phase = "started" if method.endswith("started") else "completed"
        if item_type == "agentMessage" and phase == "completed":
            self._event(
                session, "message.completed",
                {"text": _safe_text(item.get("text", ""))},
                item_id=item_id,
            )
            return
        tool_name = None
        if item_type == "commandExecution":
            tool_name = "shell"
        elif item_type == "fileChange":
            tool_name = "fileChange"
        elif item_type == "mcpToolCall":
            tool_name = f"{item.get('server', 'mcp')}/{item.get('tool', 'tool')}"
        elif item_type == "dynamicToolCall":
            tool_name = f"{item.get('namespace', 'tool')}/{item.get('tool', 'call')}"
        elif item_type == "webSearch":
            tool_name = "webSearch"
        if tool_name:
            self._event(session, f"tool.{phase}", {
                "text": _safe_text(tool_name, 500),
                "tool": _safe_text(tool_name, 500),
                "status": item.get("status") or phase,
            }, item_id=item_id)
            return
        if item_type == "collabAgentToolCall":
            receivers, states = item.get("receiverThreadIds"), item.get("agentsStates")
            if isinstance(receivers, list):
                for child_id in receivers:
                    if not isinstance(child_id, str):
                        continue
                    raw_state = states.get(child_id) if isinstance(states, dict) else None
                    child_state = (
                        raw_state.get("status")
                        if isinstance(raw_state, dict)
                        else raw_state or phase
                    )
                    child = {
                        "threadId": child_id,
                        "state": child_state,
                        "source": "collabAgentToolCall",
                    }
                    with session.lock:
                        session.children[child_id] = child
                    self._event(session, "child.updated", {
                        "text": "Native child agent updated", **child,
                    }, item_id=item_id)
            return
        if item_type == "subAgentActivity":
            child_id = item.get("agentThreadId")
            if isinstance(child_id, str):
                child = {
                    "threadId": child_id,
                    "state": item.get("kind") or phase,
                    "path": _safe_text(item.get("agentPath", ""), 500),
                    "source": "subAgentActivity",
                }
                with session.lock:
                    session.children[child_id] = child
                self._event(session, "child.updated", {
                    "text": "Native child agent updated", **child,
                }, item_id=item_id)

    def _on_exit(self, session: _TeamSession, reason: str) -> None:
        with session.lock:
            if session.closing:
                session.state = "offline"
                return
            session.state = "error"
            session.error = _safe_text(reason, 1000)
            pending = list(session.pending_calls.values())
            session.pending_calls.clear()
            session.approvals.clear()
        for call in pending:
            call.error = session.error
            call.ready.set()
        self._event(session, "error", {"text": session.error})

    def _require_session(self, team: str) -> _TeamSession:
        with self._sessions_lock:
            session = self._sessions.get(team)
        if not session or not session.connection.running():
            raise BridgeError("team has no connected native supervisor")
        return session

    def shutdown_all(self) -> None:
        with self._sessions_lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            with session.lock:
                session.closing = True
                session.state = "offline"
                pending = list(session.pending_calls.values())
                session.pending_calls.clear()
                session.approvals.clear()
            for call in pending:
                call.error = "native Codex app-server is shutting down"
                call.ready.set()
            session.connection.close()


_SINGLETONS: dict[Path, CodexBridge] = {}
_SINGLETON_LOCK = threading.Lock()


def get_codex_bridge(state_dir: Path = DEFAULT_STATE_DIR) -> CodexBridge:
    """Return the process-local singleton for a resolved runtime state directory."""
    key = Path(state_dir).resolve()
    with _SINGLETON_LOCK:
        bridge = _SINGLETONS.get(key)
        if bridge is None:
            bridge = CodexBridge(state_dir=key)
            _SINGLETONS[key] = bridge
        return bridge


def get_bridge(data_dir: Path) -> CodexBridge:
    """HTTP-adapter convenience factory using DATA_DIR/runtime."""
    return get_codex_bridge(Path(data_dir).resolve() / "runtime")
