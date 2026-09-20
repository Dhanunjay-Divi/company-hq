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
    if mode not in {"plan", "execute"}:
        raise BridgeError("mode must be plan or execute")
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


def _supervisor_instructions(team: str, project: Path) -> str:
    return f"""You are the native Codex supervisor for Company HQ team {team!r}.
The approved project root is {str(project)!r}. Keep project writes inside that root.
Read the repository operating resources under {str(REPO_ROOT)!r} when useful.
Use registered Ruflo and codebase-memory tools when available; do not replace the
user's Codex configuration or account environment. Treat ClawTeam team IDs, task IDs, member IDs,
inboxes, and events as canonical coordination state. Delegate useful independent work
through native Codex collaboration tools, preferring gpt-5.6-luna for small bounded
tasks and escalating only when complexity requires it. Report actual child thread IDs
and observed states. Never invent workers, liveness, completion, or tool results.
Never bypass approvals or sandbox protections."""


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
    mode: str = "execute"
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
    lock: threading.RLock = field(default_factory=threading.RLock)
    operation_lock: threading.Lock = field(default_factory=threading.Lock)
    closing: bool = False


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
        return value

    def _write_binding(
        self,
        team: str,
        project: Path,
        thread_id: str | None = None,
        model: str | None = None,
        mode: str | None = None,
    ) -> None:
        path = self._binding_path(team)
        previous = self._read_binding(team) or {}
        value = {
            "team": team,
            "projectRoot": str(project),
            "threadId": thread_id if thread_id is not None else previous.get("threadId"),
            "model": model if model is not None else previous.get("model"),
            "mode": mode if mode is not None else previous.get("mode"),
            "updatedAtMs": _now_ms(),
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)

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
                self._write_binding(team, resolved)
        return resolved, binding

    def _new_session(self, team: str, project: Path, model: str, mode: str) -> _TeamSession:
        session = _TeamSession(
            team=team,
            project=project,
            model=model,
            mode=mode,
            connection=self.connection_factory(self.codex_path),
            events=deque(maxlen=self.max_events),
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
        mode: str = "execute",
    ) -> dict[str, Any]:
        team = _validate_team(team)
        prompt = _validate_prompt(prompt)
        model = _validate_model(model)
        mode = _validate_mode(mode)
        project_path, binding = self._bind_project(team, Path(project))
        session = self._new_session(team, project_path, model, mode)
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
                "approvalPolicy": "on-request",
                "approvalsReviewer": "user",
                "sandbox": "read-only" if mode == "plan" else "workspace-write",
                "developerInstructions": _supervisor_instructions(team, project_path)
                + (
                    "\nThis session starts in read-only planning mode. Inspect, clarify and propose a concise plan; do not modify project files until the user explicitly approves execution."
                    if mode == "plan"
                    else ""
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
                self._write_binding(team, project_path, thread_id, model, mode)
            self._event(session, "thread.started", {
                "text": "Native supervisor connected",
                "mode": mode,
            })
            self._start_turn(session, prompt)
            return self.status(team)
        except Exception as exc:
            with session.lock:
                session.state = "error"
                session.error = _safe_text(exc, 1000)
            self._event(session, "error", {"text": session.error})
            session.connection.close()
            raise

    def _start_turn(self, session: _TeamSession, prompt: str) -> str:
        if not session.thread_id:
            raise BridgeError("team has no native Codex thread")
        result = self._rpc(session, "turn/start", {
            "threadId": session.thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(session.project),
            "model": session.model,
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "sandboxPolicy": (
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
            session.state = "idle" if turn_id in session.completed_turns else "running"
            session.error = None
        self._event(session, "turn.started", {
            "text": "Supervisor turn started",
            "mode": session.mode,
        })
        return turn_id

    def begin_execution(
        self,
        team: str,
        prompt: str = "The user approved the current plan. Begin bounded execution now. Reuse relevant project context, prefer economical capable workers, and report progress and blockers.",
    ) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        prompt = _validate_prompt(prompt)
        with session.operation_lock:
            with session.lock:
                if session.state != "idle" or not session.thread_id:
                    raise BridgeError("wait for the planning turn to finish before approving execution")
                session.mode = "execute"
                thread_id = session.thread_id
            with self._binding_lock:
                self._write_binding(team, session.project, session.thread_id, session.model, "execute")
            self._event(session, "mode.changed", {
                "text": "User approved execution",
                "mode": "execute",
            })
            turn_id = self._start_turn(session, prompt)
        return {
            "accepted": True,
            "mode": "execute",
            "threadId": thread_id,
            "turnId": turn_id,
        }

    def send(self, team: str, prompt: str) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        prompt = _validate_prompt(prompt)
        with session.operation_lock:
            with session.lock:
                state, thread_id, turn_id = session.state, session.thread_id, session.turn_id
            if not thread_id or state in {"starting", "stopping", "error", "offline"}:
                raise BridgeError(f"team supervisor cannot accept input while {state}")
            if state in {"running", "awaiting_approval"} and turn_id:
                result = self._rpc(session, "turn/steer", {
                    "threadId": thread_id,
                    "expectedTurnId": turn_id,
                    "input": [{"type": "text", "text": prompt}],
                })
                if result.get("turnId") != turn_id:
                    raise BridgeProtocolError("native Codex steered a different turn")
                delivery = "turn/steer"
            else:
                turn_id = self._start_turn(session, prompt)
                delivery = "turn/start"
        return {
            "accepted": True,
            "delivery": delivery,
            "mode": session.mode,
            "threadId": thread_id,
            "turnId": turn_id,
        }

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

    def approve(self, team: str, request_id: str, decision: str) -> dict[str, Any]:
        session = self._require_session(_validate_team(team))
        if decision not in {"approve", "reject"}:
            raise BridgeError("decision must be approve or reject")
        with session.operation_lock:
            with session.lock:
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
            return {
                "team": team,
                "state": "offline",
                "connected": False,
                "project": binding.get("projectRoot") if binding else None,
                "model": binding.get("model") if binding else None,
                "mode": binding.get("mode") if binding else None,
                "threadId": binding.get("threadId") if binding else None,
                "turnId": None,
                "lastEventSeq": 0,
                "pendingApprovals": [],
                "children": [],
            }
        with session.lock:
            result = {
                "team": team,
                "state": session.state,
                "connected": bool(session.connection.running()),
                "project": str(session.project),
                "model": session.model,
                "mode": session.mode,
                "threadId": session.thread_id,
                "turnId": session.turn_id,
                "lastEventSeq": session.next_event_seq - 1,
                "pendingApprovals": [dict(item.data) for item in session.approvals.values()],
                "children": [dict(value) for value in session.children.values()],
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
            return {"team": team, "afterSeq": after_seq, "nextSeq": after_seq, "events": []}
        with session.lock:
            oldest = session.events[0]["seq"] if session.events else session.next_event_seq
            return {
                "team": team,
                "afterSeq": after_seq,
                "nextSeq": session.next_event_seq - 1,
                "truncated": after_seq + 1 < oldest,
                "events": [dict(event) for event in session.events if event["seq"] > after_seq],
            }

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
            session.events.append({
                "seq": session.next_event_seq,
                "time": _now_ms(),
                "type": event_type,
                "threadId": thread_id or session.thread_id,
                "turnId": turn_id or session.turn_id,
                "itemId": item_id,
                "data": data,
            })
            session.next_event_seq += 1

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
        approval_methods = {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "execCommandApproval",
            "applyPatchApproval",
        }
        if method in approval_methods:
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

    def _handle_notification(
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
                if isinstance(native_id, str):
                    session.turn_id = native_id
                    session.completed_turns.add(native_id)
                session.state = "error" if status == "failed" else "idle"
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
            self._event(
                session,
                "usage",
                {"text": "Token usage updated", "counts": _numeric_tree(params.get("tokenUsage")) or {}},
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
