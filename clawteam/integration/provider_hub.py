"""Provider-neutral facade preserving the existing CodexBridge API."""
from __future__ import annotations

import atexit
from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable

from codex_bridge import (
    BridgeError,
    CodexBridge,
    _EventStore,
    _now_ms,
    _safe_event_value,
    _unresolved_replay_requests,
    _validate_prompt,
    _validate_team,
)
from provider_runtime import ProviderRuntime, ProviderRuntimeError, create_runtime
from transcript_archive import TranscriptArchive


SUPPORTED_PROVIDERS = {"codex", "claude", "kimi", "zai", "deepseek", "openai-compatible"}
DEFAULT_EXECUTION_PROMPT = (
    "The user approved the current plan. Begin bounded execution now. "
    "Do not repeat planning or ask for plan approval again. Verify the work and "
    "honor native permission requests."
)


@dataclass
class _ProviderSession:
    team: str
    provider: str
    runtime: ProviderRuntime
    project: Path
    model: str
    mode: str
    access: str
    session_id: str | None = None
    plan_ready: bool = False
    reported_tokens: int = 0
    usage_reported: bool = False
    usage_details: dict[str, Any] = field(default_factory=dict)
    runtime_cursor: int = 0
    next_event_seq: int = 1
    turn_id: str | None = None
    error: str | None = None
    events: deque[dict[str, Any]] = field(default_factory=deque)
    replay_events: deque[dict[str, Any]] = field(default_factory=deque)
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_turns: set[str] = field(default_factory=set)
    lock: threading.RLock = field(default_factory=threading.RLock)
    drain_lock: threading.Lock = field(default_factory=threading.Lock)
    operation_lock: threading.RLock = field(default_factory=threading.RLock)
    stop_event: threading.Event = field(default_factory=threading.Event)
    watcher: threading.Thread | None = None
    archive_pending: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))
    history_warning: str | None = None
    persistence_warning: str | None = None
    usage_pending: bool = False
    quota_failure: dict[str, Any] | None = None


class ProviderHub:
    """Route one permanently provider-bound chat through Codex or Claude."""

    def __init__(
        self,
        state_dir: Path,
        *,
        codex: CodexBridge | None = None,
        runtime_factory: Callable[..., ProviderRuntime] = create_runtime,
        max_events: int = 500,
        poll_interval: float = 0.03,
    ) -> None:
        if not 20 <= max_events <= 5000:
            raise ValueError("max_events must be between 20 and 5000")
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        self.binding_dir = self.state_dir / "provider-bindings"
        self.binding_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.binding_dir, 0o700)
        self.codex = codex or CodexBridge(state_dir=self.state_dir, max_events=max_events)
        self.runtime_factory = runtime_factory
        self.max_events = max_events
        self.poll_interval = poll_interval
        self._event_store = _EventStore(self.state_dir, max_events)
        self._transcripts = TranscriptArchive(self.state_dir)
        self._sessions: dict[str, _ProviderSession] = {}
        self._sessions_lock = threading.RLock()
        self._binding_lock = threading.RLock()
        atexit.register(self.shutdown_all)

    def _binding_path(self, team: str) -> Path:
        return self.binding_dir / f"{hashlib.sha256(team.encode('utf-8')).hexdigest()}.json"

    def _read_binding(self, team: str) -> dict[str, Any] | None:
        path = self._binding_path(team)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
            raise BridgeError("provider binding is not a regular small file")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeError("provider binding is unreadable") from exc
        if not isinstance(value, dict) or value.get("team") != team:
            raise BridgeError("provider binding does not match the requested chat")
        if value.get("provider") not in SUPPORTED_PROVIDERS:
            raise BridgeError("provider binding names an unsupported provider")
        if not isinstance(value.get("projectRoot"), str):
            raise BridgeError("provider binding has no project root")
        if value.get("mode") not in {"plan", "execute", "full"}:
            raise BridgeError("provider binding has an invalid mode")
        if value.get("accessMode") not in {"workspace", "full"}:
            raise BridgeError("provider binding has an invalid access mode")
        return value

    def _write_binding(self, team: str, **changes: Any) -> dict[str, Any]:
        with self._binding_lock:
            previous = self._read_binding(team) or {}
            value = {**previous, **changes, "team": team, "updatedAtMs": _now_ms()}
            path = self._binding_path(team)
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            return value

    @staticmethod
    def _project(project: str | Path) -> Path:
        try:
            value = Path(project).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise BridgeError("approved project root does not exist") from exc
        if not value.is_dir() or value == Path.home() or value == Path("/"):
            raise BridgeError("approved project root must be a non-home directory")
        return value

    def _provider(self, team: str) -> str:
        binding = self._read_binding(team)
        return binding["provider"] if binding else "codex"

    def _ensure_choice(self, team: str, provider: str, project: Path) -> dict[str, Any] | None:
        if provider not in SUPPORTED_PROVIDERS:
            raise BridgeError(f"{provider} does not have a verified Company HQ runtime")
        binding = self._read_binding(team)
        if binding:
            if binding["provider"] != provider:
                raise BridgeError(f"This chat is already bound to {binding['provider']}; start a new chat to change providers")
            if Path(binding["projectRoot"]).resolve() != project:
                raise BridgeError("chat is already bound to a different project root")
            return binding
        if provider != "codex" and not binding:
            codex_status = self.codex.status(team)
            if codex_status.get("threadId") or codex_status.get("project"):
                raise BridgeError("This chat is already bound to codex; start a new chat to change providers")
        return None

    def _new_provider_session(
        self, team: str, provider: str, project: Path, model: str, mode: str, access: str,
        binding: dict[str, Any] | None,
    ) -> _ProviderSession:
        runtime = self.runtime_factory(
            provider, model=None, access="plan" if mode == "plan" else access,
            session_id=binding.get("sessionId") if binding else None,
            **({"shared_tools":True} if provider in {"kimi","zai"} else {}),
        )
        runtime.context_team = team
        runtime.shared_tools = provider != 'openai-compatible'
        restored = self._event_store.load(team)
        next_seq = self._event_store.next_sequence(team, restored[-1]["seq"] + 1 if restored else 1)
        session = _ProviderSession(
            team=team, provider=provider,
            runtime=runtime,
            project=project,
            model=model,
            mode=mode,
            access=access,
            session_id=binding.get("sessionId") if binding else None,
            plan_ready=bool(binding.get("planReady", False)) if binding else False,
            reported_tokens=int(binding.get("reportedTokens", 0)) if binding and isinstance(binding.get("reportedTokens", 0), int) else 0,
            usage_reported=bool(binding and (binding.get("usageReported") or binding.get("reportedTokens",0))),
            usage_details=dict(binding.get('usageDetails') or {}) if binding else {},
            next_event_seq=next_seq,
            events=deque(restored, maxlen=self.max_events),
            replay_events=deque(restored, maxlen=self.max_events),
            archive_pending=deque(
                (dict(event) for event in restored if event.get("type") in {"message.user", "message.completed"}),
                maxlen=500,
            ),
        )
        with self._sessions_lock:
            current = self._sessions.get(team)
            if current and current.runtime.status().get("connected"):
                raise BridgeError("chat already has a connected provider runtime")
            if current:
                self._shutdown_session(current)
            self._sessions[team] = session
        return session

    def _start_watcher(self, session: _ProviderSession) -> None:
        if session.watcher and session.watcher.is_alive():
            return
        session.watcher = threading.Thread(
            target=self._watch, args=(session,), name=f"company-hq-{session.team}-provider-events", daemon=True,
        )
        session.watcher.start()

    def _persist_session(self, session: _ProviderSession) -> None:
        try:
            self._write_binding(
                session.team, provider=session.provider, projectRoot=str(session.project),
                sessionId=session.session_id, model=session.model, mode=session.mode,
                accessMode=session.access, planReady=session.plan_ready,
                reportedTokens=session.reported_tokens,
                usageReported=session.usage_reported,
                usageDetails=session.usage_details,
            )
            session.persistence_warning = None
        except (OSError, ValueError, BridgeError):
            session.persistence_warning = "The provider session is active, but its latest binding metadata could not be saved."

    def _validate_live_binding(self, session: _ProviderSession) -> None:
        binding = self._read_binding(session.team)
        if not binding or binding.get("provider") != session.provider:
            raise BridgeError("provider binding is missing or changed")
        if Path(binding["projectRoot"]).resolve() != session.project:
            raise BridgeError("provider project binding changed")
        bound_session = binding.get("sessionId")
        if bound_session and session.session_id and bound_session != session.session_id:
            raise BridgeError("provider session binding changed")

    @staticmethod
    def _catalog_values(models: list[dict[str, Any]]) -> set[str]:
        values: set[str] = set()
        for row in models:
            for key in ("value", "resolvedModel"):
                if isinstance(row.get(key), str):
                    values.add(row[key])
        return values

    def start(
        self,
        team: str,
        project: str | Path,
        prompt: str,
        model: str,
        *,
        work_mode: str = "plan",
        attachments: list[dict] | None = None,
        provider: str = "codex",
    ) -> dict[str, Any]:
        team = _validate_team(team)
        prompt = _validate_prompt(prompt)
        provider = provider.strip().lower() if isinstance(provider, str) else ""
        if work_mode not in {"plan", "auto", "full"}:
            raise BridgeError("choose plan, auto or full work mode")
        if provider == "openai-compatible" and work_mode == "full":
            raise BridgeError("Custom API is text-only; full filesystem and tool access is unavailable")
        if provider == "openai-compatible" and attachments:
            raise BridgeError("Custom API is text-only; choose an image-capable model for attachments")
        project_path = self._project(project)
        binding = self._ensure_choice(team, provider, project_path)
        self.codex._budget.authorize(team)
        if provider == "codex":
            pre_mode = binding.get("mode", "plan") if binding else ("full" if work_mode == "full" else "execute" if work_mode == "auto" else "plan")
            pre_access = binding.get("accessMode", "workspace") if binding else ("full" if work_mode == "full" else "workspace")
            self._write_binding(
                team, provider="codex", projectRoot=str(project_path),
                sessionId=binding.get("sessionId") if binding else None,
                model=model, mode=pre_mode, accessMode=pre_access,
                planReady=bool(binding.get("planReady", False)) if binding else False,
                reportedTokens=int(binding.get("reportedTokens", 0)) if binding else 0,
            )
            result = self.codex.start(team, project_path, prompt, model, work_mode=work_mode, attachments=attachments)
            try:
                self._write_binding(
                    team, provider="codex", projectRoot=str(project_path), sessionId=result.get("threadId"),
                    model=model, mode=result.get("mode", "plan"), accessMode=result.get("accessMode", "workspace"),
                    planReady=bool(result.get("planReady", False)), reportedTokens=0,
                )
                warning = None
            except OSError:
                warning = "Codex accepted the turn; the provider binding update will be retried from its native binding."
            return {**result, "provider": "codex", **({"persistenceWarning": warning} if warning else {})}

        mode = binding.get("mode", "plan") if binding else ("full" if work_mode == "full" else "execute" if work_mode == "auto" else "plan")
        access = binding.get("accessMode", "workspace") if binding else ("full" if work_mode == "full" else "workspace")
        session = self._new_provider_session(team, provider, project_path, model, mode, access, binding)
        try:
            # Native providers must select the requested model while creating
            # the session; validating a later catalog must not permit a
            # transport default to accept the first paid turn.
            initialized = session.runtime.initialize(project=project_path, model=model)  # type: ignore[attr-defined]
            models = initialized.get("models") if isinstance(initialized, dict) else None
            if not isinstance(models, list) or model not in self._catalog_values(models):
                raise BridgeError("model is not in the initialized provider model catalog")
            session.session_id = session.runtime.status().get("sessionId") or session.session_id
            # Commit provider/project/session authority before the user turn is
            # accepted so a metadata write failure cannot orphan paid work.
            self._write_binding(
                team, provider=provider, projectRoot=str(project_path), sessionId=session.session_id,
                model=model, mode=mode, accessMode=access, planReady=False,
                reportedTokens=session.reported_tokens,
            )
            accepted = session.runtime.start(prompt, project=project_path, model=model, images=attachments)
            session.session_id = accepted.get("sessionId") or session.runtime.status().get("sessionId")
            session.turn_id = accepted.get("turnId")
            session.model = model
            session.plan_ready = False if mode == "plan" else session.plan_ready
            self._persist_session(session)
            self._start_watcher(session)
            self._drain(session)
            return self.status(team)
        except Exception as exc:
            public_error = str(exc) if isinstance(exc, (BridgeError, ProviderRuntimeError)) else f"{provider} provider could not start"
            session.error = public_error[:1000]
            try:
                session.runtime.stop()
            except Exception:
                pass
            if isinstance(exc, BridgeError):
                raise
            if isinstance(exc, ProviderRuntimeError):
                raise BridgeError(str(exc)) from exc
            raise BridgeError(public_error) from exc

    def _watch(self, session: _ProviderSession) -> None:
        while not session.stop_event.wait(self.poll_interval):
            try:
                self._drain(session)
            except Exception:
                with session.lock:
                    session.persistence_warning = "Provider event processing is retrying after an internal persistence error."

    def _question_data(self, data: dict[str, Any]) -> dict[str, Any]:
        raw = data.get("toolInput")
        raw_questions = raw.get("questions") if isinstance(raw, dict) else None
        questions = []
        if isinstance(raw_questions, list):
            for index, row in enumerate(raw_questions[:3]):
                if not isinstance(row, dict) or not isinstance(row.get("question"), str):
                    continue
                options = []
                if isinstance(row.get("options"), list):
                    for option in row["options"][:10]:
                        if isinstance(option, dict) and isinstance(option.get("label"), str):
                            options.append({
                                "label": option["label"][:500],
                                "description": option.get("description", "")[:1000] if isinstance(option.get("description"), str) else "",
                            })
                questions.append({
                    "id": f"question-{index}",
                    "header": row.get("header", "Question")[:100] if isinstance(row.get("header"), str) else "Question",
                    "question": row["question"][:4000],
                    "options": options,
                    "isOther": True,
                    "multiSelect": bool(row.get("multiSelect")),
                })
        return {
            "requestId": data.get("requestId"), "kind": "questions",
            "text": "The provider needs your input", "reason": data.get("reason"),
            "questions": questions, "availableDecisions": ["respond", "reject"],
            "sessionId": data.get("sessionId"), "turnId": data.get("turnId"), "itemId": data.get("itemId"),
            "recovered": bool(data.get("recovered")),
        }

    @staticmethod
    def _approval_data(data: dict[str, Any]) -> dict[str, Any]:
        tool = data.get("tool") if isinstance(data.get("tool"), str) else "Tool"
        tool_input = data.get("toolInput") if isinstance(data.get("toolInput"), dict) else {}
        command = tool_input.get("command") if isinstance(tool_input.get("command"), str) else ""
        path = next((tool_input.get(key) for key in ("file_path", "path", "notebook_path") if isinstance(tool_input.get(key), str)), None)
        return {
            "requestId": data.get("requestId"),
            "kind": "command" if tool in {"Bash", "PowerShell", "REPL"} else "fileChange" if tool in {"Edit", "Write", "NotebookEdit"} else "tool",
            "title": tool,
            "reason": data.get("reason") or f"The provider requested {tool}",
            "command": command[:4000],
            "path": path[:2000] if isinstance(path, str) else None,
            "tool": tool,
            "availableDecisions": ["approve", "reject"],
            "sessionId": data.get("sessionId"), "turnId": data.get("turnId"), "itemId": data.get("itemId"),
            "recovered": bool(data.get("recovered")),
        }

    def _drain(self, session: _ProviderSession) -> None:
        with session.drain_lock:
            with session.lock:
                cursor = session.runtime_cursor
            try:
                page = session.runtime.events(cursor)
            except Exception:
                return
            rows = page.get("events") if isinstance(page, dict) else None
            if not isinstance(rows, list):
                return
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("seq"), int):
                    continue
                try:
                    self._record_runtime_event(session, row)
                except Exception:
                    with session.lock:
                        session.persistence_warning = "A provider event was accepted and event persistence is retrying."
                finally:
                    with session.lock:
                        session.runtime_cursor = max(session.runtime_cursor, row["seq"])
            self._save_event_snapshot(session)
            self._flush_archive(session)
            self._flush_usage(session)

    def _save_event_snapshot(self, session: _ProviderSession) -> None:
        with session.lock:
            next_seq = session.next_event_seq
            snapshot = list(session.replay_events)
        try:
            self._event_store.record_next_sequence(session.team, next_seq)
            self._event_store.save(session.team, snapshot)
            if session.persistence_warning and "event replay" in session.persistence_warning:
                session.persistence_warning = None
        except (OSError, ValueError, TypeError):
            session.persistence_warning = "Provider event replay is temporarily memory-only; saving will be retried."

    def _flush_archive(self, session: _ProviderSession) -> None:
        with session.lock:
            pending = list(session.archive_pending)
            session.archive_pending.clear()
        for index, candidate in enumerate(pending):
            try:
                self._transcripts.record(session.team, candidate)
            except (OSError, ValueError, sqlite3.Error):
                with session.lock:
                    for remaining in pending[index:]:
                        session.archive_pending.append(remaining)
                    session.history_warning = "Some accepted messages are waiting for durable history storage; runtime replay remains available."
                return
        with session.lock:
            session.history_warning = None

    def _archive(self, session: _ProviderSession, event: dict[str, Any]) -> None:
        if event.get("type") not in {"message.user", "message.completed"}:
            return
        with session.lock:
            session.archive_pending.append(event)
        self._flush_archive(session)

    def _flush_usage(self, session: _ProviderSession) -> None:
        with session.lock:
            if not session.usage_pending or not session.session_id:
                return
            session_id = session.session_id
            reported_tokens = session.reported_tokens
        try:
            self.codex._budget.record_usage(session.team, session_id, reported_tokens)
        except Exception:
            with session.lock:
                session.persistence_warning = "Provider usage accounting is temporarily unavailable; persisted token totals will be retried."
            return
        with session.lock:
            session.usage_pending = False
            if session.persistence_warning and "usage accounting" in session.persistence_warning:
                session.persistence_warning = None

    def _record_runtime_event(self, session: _ProviderSession, row: dict[str, Any]) -> None:
        event_type = row.get("type") if isinstance(row.get("type"), str) else "provider.event"
        raw_data = row.get("data") if isinstance(row.get("data"), dict) else {}
        data = dict(raw_data)
        request_id = data.get("requestId")
        with session.lock:
            if event_type == "question.requested" and isinstance(request_id, str):
                session.pending[request_id] = self._question_data(data)
                data = dict(session.pending[request_id])
            elif event_type == "approval.requested" and isinstance(request_id, str):
                session.pending[request_id] = self._approval_data(data)
                data = dict(session.pending[request_id])
            elif event_type in {"request.resolved", "request.cancelled"} and isinstance(request_id, str):
                session.pending.pop(request_id, None)
                if data.get("recovered") and isinstance(data.get("turnId"), str):
                    session.active_turns.discard(data["turnId"])
            if event_type == "message.user" and isinstance(data.get("turnId"), str):
                session.active_turns.add(data["turnId"])
                session.quota_failure = None
            if event_type in {"question.requested", "approval.requested"} and data.get("recovered") and isinstance(data.get("turnId"), str):
                session.active_turns.add(data["turnId"])
            if isinstance(data.get("turnId"), str):
                session.turn_id = data["turnId"]
            if event_type == "message.completed":
                if isinstance(data.get("turnId"), str):
                    session.active_turns.discard(data["turnId"])
                session.plan_ready = session.mode == "plan" and not bool(data.get("isError"))
            if event_type in {'message.completed','usage'}:
                usage = data.get("usage")
                if isinstance(usage, dict):
                    session.usage_reported = True
                    openai_total = usage.get('total_tokens')
                    if isinstance(openai_total,int) and not isinstance(openai_total,bool) and openai_total >= 0:
                        turn_tokens = openai_total
                    elif any(key in usage for key in ('prompt_tokens','completion_tokens')):
                        turn_tokens = sum(usage.get(key,0) for key in ('prompt_tokens','completion_tokens')
                            if isinstance(usage.get(key),int) and not isinstance(usage.get(key),bool) and usage[key]>=0)
                    else:
                        turn_tokens = sum(
                            int(usage.get(key, 0)) for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
                            if isinstance(usage.get(key, 0), (int, float)) and not isinstance(usage.get(key, 0), bool)
                        )
                    session.reported_tokens += max(0, turn_tokens)
                native_usage = data.get("nativeUsage")
                if isinstance(native_usage, dict):
                    total = native_usage.get("totalTokens")
                    if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
                        # ZCode reports a cumulative session total. Cached tokens
                        # are already included; replay/resume must not add it twice.
                        session.reported_tokens = max(session.reported_tokens, total)
                        session.usage_reported = True
                        session.usage_details = {key:native_usage[key] for key in ('totalTokens','inputTokens','outputTokens','reasoningTokens') if isinstance(native_usage.get(key),int) and not isinstance(native_usage.get(key),bool) and native_usage[key]>=0}
                        cached=native_usage.get('cacheReadTokens')
                        if isinstance(cached,int) and not isinstance(cached,bool) and cached>=0:session.usage_details['cachedInputTokens']=cached
                session.usage_pending = session.usage_reported
            if event_type == "runtime.error":
                from quota_errors import quota_failure
                session.quota_failure = quota_failure(data.get('message') or data.get('text'))
                session.error = str(data.get("message") or data.get("text") or "Provider runtime error")[:1000]
                failed_turn = data.get("turnId")
                if isinstance(failed_turn, str):
                    session.active_turns.discard(failed_turn)
                try:
                    runtime_state = session.runtime.status().get("state")
                except Exception:
                    runtime_state = "error"
                if not failed_turn or runtime_state in {"error", "offline"}:
                    session.active_turns.clear()
                    session.pending.clear()
            event = {
                "seq": session.next_event_seq,
                "time": _now_ms(),
                "type": event_type,
                "threadId": data.get("sessionId") or session.session_id,
                "turnId": data.get("turnId") or session.turn_id,
                "itemId": data.get("itemId"),
                "data": _safe_event_value(data),
            }
            session.next_event_seq += 1
            session.events.append(event)
            if event_type != "message.delta":
                session.replay_events.append(event)
            self._archive(session, event)
            binding_update = event_type in {"runtime.started", "message.completed", "runtime.access", "usage"}
            plan_ready = session.plan_ready
            reported_tokens = session.reported_tokens
            session_id = session.session_id or data.get("sessionId")
        if event_type in {"message.completed", "usage"} and session_id:
            self._flush_usage(session)
        if binding_update:
            self._persist_session(session)

    def _session(self, team: str, *, resume: bool = False) -> _ProviderSession:
        with self._sessions_lock:
            session = self._sessions.get(team)
        if not session and resume:
            binding = self._read_binding(team)
            if not binding or binding.get("provider") not in SUPPORTED_PROVIDERS - {"codex"}:
                raise BridgeError("Connect this Claude chat before continuing")
            project = self._project(binding["projectRoot"])
            session = self._new_provider_session(
                team, binding["provider"], project, binding.get("model"), binding["mode"], binding["accessMode"], binding,
            )
            try:
                initialized = session.runtime.initialize(project=project, model=session.model)  # type: ignore[attr-defined]
                models = initialized.get("models") if isinstance(initialized, dict) else None
                if not isinstance(models, list) or session.model not in self._catalog_values(models):
                    raise BridgeError("persisted model is not in the initialized provider model catalog")
                session.session_id = session.runtime.status().get("sessionId") or session.session_id
                self._persist_session(session)
                self._start_watcher(session)
                self._drain(session)
            except Exception as exc:
                try:
                    session.runtime.stop()
                except Exception:
                    pass
                if isinstance(exc, BridgeError):
                    raise
                if isinstance(exc, ProviderRuntimeError):
                    raise BridgeError(str(exc)) from exc
                raise BridgeError(f"{binding['provider']} provider could not resume") from exc
        if not session:
            raise BridgeError("Connect this Claude chat before continuing")
        return session

    def send(self, team: str, prompt: str, *, attachments: list[dict] | None = None) -> dict[str, Any]:
        team = _validate_team(team)
        prompt = _validate_prompt(prompt)
        if self._provider(team) == "codex":
            return self.codex.send(team, prompt, attachments=attachments)
        if self._provider(team) == "openai-compatible" and attachments:
            raise BridgeError("Custom API is text-only; choose an image-capable model for attachments")
        self.codex._budget.authorize(team)
        session = self._session(team, resume=True)
        with session.operation_lock:
            self._validate_live_binding(session)
            try:
                if not session.runtime.status().get("connected"):
                    session.runtime.initialize(project=session.project, model=session.model)  # type: ignore[attr-defined]
                    session.session_id = session.runtime.status().get("sessionId") or session.session_id
                if session.pending:
                    raise BridgeError("Respond to the pending native request before sending another message")
                if session.runtime.status().get("state") not in {"idle", "running"}:
                    raise BridgeError("provider runtime cannot accept input in its current state")
                if session.mode == "plan":
                    session.plan_ready = False
                # Persist the resumed identity and plan state before acceptance.
                self._write_binding(
                    team, provider=session.provider, projectRoot=str(session.project), sessionId=session.session_id,
                    model=session.model, mode=session.mode, accessMode=session.access,
                    planReady=session.plan_ready, reportedTokens=session.reported_tokens,
                )
                result = session.runtime.send(prompt, images=attachments)
                session.turn_id = result.get("turnId")
                self._drain(session)
                return result
            except ProviderRuntimeError as exc:
                raise BridgeError(str(exc)) from exc

    def begin_execution(self, team: str, prompt: str = DEFAULT_EXECUTION_PROMPT) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.begin_execution(team, prompt)
        self.codex._budget.authorize(team)
        session = self._session(team, resume=True)
        with session.operation_lock:
            self._validate_live_binding(session)
            state = session.runtime.status().get("state")
            if state != "idle" or session.mode != "plan" or not session.plan_ready:
                raise BridgeError("the planning turn must complete successfully before execution")
            try:
                session.mode, session.access, session.plan_ready = "execute", "workspace", False
                self._write_binding(team, mode="execute", accessMode="workspace", planReady=False)
                session.runtime.set_access("workspace")
                result = session.runtime.send(_validate_prompt(prompt))
                session.turn_id = result.get("turnId")
                self._drain(session)
                return {**result, "mode": "execute", "threadId": session.session_id}
            except ProviderRuntimeError as exc:
                raise BridgeError(str(exc)) from exc

    def set_access(self, team: str, access: str) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.set_access(team, access)
        if access not in {"workspace", "full"}:
            raise BridgeError("Choose workspace or full access")
        session = self._session(team, resume=True)
        with session.operation_lock:
            self._validate_live_binding(session)
            if session.mode == "plan":
                raise BridgeError("Approve the plan before changing execution access")
            # ZCode exposes a native mode change while its tool permission is
            # pending. This explicit chat-level choice does not approve the
            # pending tool itself; the caller still answers that request.
            if session.provider == 'zai' and access == 'full' and session.pending:
                try:
                    session.runtime.set_access(access)
                    session.access=access
                    session.mode='full'
                    self._write_binding(team,mode='full',accessMode=access)
                    self._drain(session)
                    return self.status(team)
                except ProviderRuntimeError as exc:
                    raise BridgeError(str(exc)) from exc
            if session.runtime.status().get("state") != "idle" or session.pending:
                raise BridgeError("Finish or stop the current turn before changing access")
            try:
                next_mode = "full" if access == "full" else "execute"
                self._write_binding(
                    team, provider=session.provider, projectRoot=str(session.project), sessionId=session.session_id,
                    model=session.model, mode=next_mode, accessMode=access,
                    planReady=False, reportedTokens=session.reported_tokens,
                )
                previous_access = session.access
                session.access = access
                session.mode = next_mode
                if session.runtime.status().get("connected") and "full" in {previous_access, access} and previous_access != access:
                    session.runtime.stop()
                session.runtime.set_access(access)
                if not session.runtime.status().get("connected"):
                    session.runtime.initialize(project=session.project, model=session.model)  # type: ignore[attr-defined]
                session.session_id = session.runtime.status().get("sessionId") or session.session_id
                self._write_binding(team, mode=session.mode, accessMode=access, sessionId=session.session_id)
                self._drain(session)
                return self.status(team)
            except ProviderRuntimeError as exc:
                raise BridgeError(str(exc)) from exc

    def stop(self, team: str) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.stop(team)
        session = self._session(team)
        with session.operation_lock:
            result = session.runtime.stop()
            self._drain(session)
            with session.lock:
                session.pending.clear()
                session.active_turns.clear()
            return result

    def _claude_answers(self, pending: dict[str, Any], response: object) -> dict[str, str]:
        if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
            return {}
        answers = response["answers"]
        result: dict[str, str] = {}
        for question in pending.get("questions", []):
            if not isinstance(question, dict):
                continue
            value = answers.get(question.get("id"))
            if isinstance(value, dict) and isinstance(value.get("answers"), list):
                choices = [item for item in value["answers"] if isinstance(item, str)]
                if choices:
                    result[question.get("question", question.get("id", "answer"))] = ", ".join(choices)[:4000]
            elif isinstance(value, str):
                result[question.get("question", question.get("id", "answer"))] = value[:4000]
        return result

    def respond(self, team: str, request_id: str, response: object) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.respond(team, request_id, response)
        session = self._session(team)
        with session.operation_lock:
            self._validate_live_binding(session)
            pending = session.pending.get(request_id)
            if not pending or pending.get("kind") != "questions":
                raise BridgeError("native question is unknown, stale, or already resolved")
            if pending.get("sessionId") not in {None, session.session_id} or pending.get("turnId") not in session.active_turns:
                raise BridgeError("native question no longer belongs to an active provider turn")
            answers = self._claude_answers(pending, response)
            allow = bool(answers)
            self.codex._budget.authorize(team) if allow else None
            try:
                result = session.runtime.respond(request_id, {"allow": allow, "answers": answers})
                self._drain(session)
                return result
            except ProviderRuntimeError as exc:
                raise BridgeError(str(exc)) from exc

    def approve(self, team: str, request_id: str, decision: str) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.approve(team, request_id, decision)
        if decision not in {"approve", "reject"}:
            raise BridgeError("decision must be approve or reject")
        if decision == "approve":
            self.codex._budget.authorize(team)
        session = self._session(team)
        with session.operation_lock:
            self._validate_live_binding(session)
            pending = session.pending.get(request_id)
            if not pending or pending.get("kind") == "questions":
                raise BridgeError("native approval is unknown, stale, or already resolved")
            if pending.get("sessionId") not in {None, session.session_id} or pending.get("turnId") not in session.active_turns:
                raise BridgeError("native approval no longer belongs to an active provider turn")
            if decision == "approve" and session.mode == "plan":
                raise BridgeError("tool approvals cannot be granted during read-only planning")
            try:
                result = session.runtime.respond(request_id, {"allow": decision == "approve", "message": "User denied"})
                self._drain(session)
                return {**result, "decision": decision}
            except ProviderRuntimeError as exc:
                raise BridgeError(str(exc)) from exc

    def status(self, team: str) -> dict[str, Any]:
        team = _validate_team(team)
        binding = self._read_binding(team)
        if not binding or binding["provider"] == "codex":
            value = self.codex.status(team)
            # Retain reported usage in HQ's binding so app restarts do not erase
            # model attribution. Native provider histories remain untouched.
            usage = value.get("usageSummary") or {}
            total = usage.get("totalTokens", usage.get("reportedTokens"))
            if binding and isinstance(total, int) and not isinstance(total, bool) and total >= 0:
                if total > binding.get("reportedTokens", 0) or not binding.get("usageReported"):
                    self._write_binding(team, reportedTokens=total, usageReported=True, usageDetails=usage)
            elif binding and binding.get("usageReported"):
                value["usageSummary"] = {**(binding.get("usageDetails") or {}), "reportedTokens": binding.get("reportedTokens")}
            return {**value, "provider": "codex", "providerBound": bool(binding)}
        with self._sessions_lock:
            session = self._sessions.get(team)
        budget = self.codex._budget.status(team)
        restored = self._event_store.load(team)
        if not session:
            return {
                "team": team, "provider": binding["provider"], "providerBound": True, "state": "offline", "connected": False,
                "project": binding["projectRoot"], "model": binding.get("model"),
                "mode": "execute" if binding["mode"] == "full" else binding["mode"],
                "accessMode": binding["accessMode"], "planReady": bool(binding.get("planReady")),
                "threadId": binding.get("sessionId"), "sessionId": binding.get("sessionId"), "turnId": None,
                "lastEventSeq": self._event_store.next_sequence(team, restored[-1]["seq"] + 1 if restored else 1) - 1,
                "pendingApprovals": [], "unrecoverableRequests": _unresolved_replay_requests(restored),
                "children": [], "usageSummary": {**(binding.get('usageDetails') or {}), "reportedTokens": binding.get("reportedTokens") if binding.get("usageReported") or binding.get("reportedTokens",0) else None},
                "budget": budget, "limits": {"blockedReason": budget["reason"]} if budget["blocked"] else {},
                "capabilities": {"images": binding['provider'] != 'openai-compatible', "workers": False, "toolsInventory": False, "nativePermissions": binding['provider'] != 'openai-compatible'},
            }
        self._drain(session)
        runtime_status = session.runtime.status()
        with session.lock:
            state = "awaiting_approval" if session.pending else runtime_status.get("state", "offline")
            return {
                "team": team, "provider": session.provider, "providerBound": True, "state": state,
                "connected": bool(runtime_status.get("connected")), "project": str(session.project),
                "model": session.model, "models": runtime_status.get("models", []),
                "mode": "execute" if session.mode == "full" else session.mode,
                "accessMode": session.access, "planReady": session.plan_ready,
                "threadId": session.session_id, "sessionId": session.session_id, "turnId": session.turn_id,
                "lastEventSeq": session.next_event_seq - 1,
                "pendingApprovals": [dict(item) for item in session.pending.values()],
                "unrecoverableRequests": [], "children": [
                    {**child, "verified":(runtime_status.get("nativeStatus") or {}).get("childrenVerified") is True and not child.get("stale")}
                    for child in runtime_status.get("children", []) or []] if isinstance(runtime_status.get("children"), list) else None,
                "usageSummary": {**session.usage_details, "reportedTokens": session.reported_tokens if session.usage_reported else None},
                "nativeStatus": {**(runtime_status.get("nativeStatus") or {}),
                    "childInventory": (runtime_status.get("nativeStatus") or {}).get("childInventory") or
                        {"complete": (runtime_status.get("nativeStatus") or {}).get("childrenVerified") is True}},
                "quotaFailure": session.quota_failure or runtime_status.get('quotaFailure'),
                "budget": budget, "limits": {"blockedReason": budget["reason"]} if budget["blocked"] else {},
                "capabilities": {"images": session.provider != 'openai-compatible', "workers": session.provider == "zai", "workerControl": False, "toolsInventory": session.provider == "zai", "nativePermissions": session.provider != 'openai-compatible'},
                "historyWarning": session.history_warning,
                "persistenceWarning": session.persistence_warning,
                **({"error": session.error} if session.error else {}),
            }

    def events(self, team: str, after_seq: int = 0) -> dict[str, Any]:
        team = _validate_team(team)
        if not isinstance(after_seq, int) or isinstance(after_seq, bool) or after_seq < 0:
            raise BridgeError("after_seq must be a non-negative integer")
        if self._provider(team) == "codex":
            return self.codex.events(team, after_seq)
        with self._sessions_lock:
            session = self._sessions.get(team)
        if not session:
            restored = self._event_store.load(team)
            oldest = restored[0]["seq"] if restored else after_seq + 1
            saved_next = restored[-1]["seq"] + 1 if restored else 1
            return {
                "team": team, "afterSeq": after_seq,
                "nextSeq": max(after_seq, self._event_store.next_sequence(team, saved_next) - 1),
                "truncated": after_seq + 1 < oldest,
                "events": [dict(event) for event in restored if event["seq"] > after_seq],
            }
        self._drain(session)
        with session.lock:
            durable = [event for event in session.replay_events if event["seq"] > after_seq]
            durable_ids = {event["seq"] for event in durable}
            tail = [event for event in session.events if event["seq"] > after_seq and event["seq"] not in durable_ids]
            remaining = max(0, self.max_events - len(durable))
            visible = sorted([*durable, *(tail[-remaining:] if remaining else [])], key=lambda event: event["seq"])
            oldest = session.events[0]["seq"] if session.events else session.next_event_seq
            return {
                "team": team, "afterSeq": after_seq, "nextSeq": session.next_event_seq - 1,
                "truncated": after_seq + 1 < oldest, "events": [dict(event) for event in visible],
            }

    def set_budget(self, team: str, limit_tokens: object, enforced: object = True) -> dict[str, Any]:
        return self.codex.set_budget(team, limit_tokens, enforced)

    def rotate_idle_binding(self, team, target_provider, target_model, handoff_id):
        """Rotate one verified terminal session; retain its private provenance.

        The caller holds HQ's workspace operation lock across rotation/start.
        No native history is deleted and the canonical team ID stays unchanged.
        """
        from provider_handoff import ProviderHandoff
        team = _validate_team(team)
        if target_provider not in SUPPORTED_PROVIDERS or not isinstance(target_model, str) or not target_model:
            raise BridgeError('Choose a supported provider and model')
        if target_provider == 'openai-compatible':
            raise BridgeError('Text-only custom endpoints cannot inherit an automatic coding handoff')
        if not isinstance(handoff_id, str) or len(handoff_id) != 32 or any(c not in '0123456789abcdef' for c in handoff_id):
            raise BridgeError('Invalid handoff identity')
        status = self.status(team)
        reason = ProviderHandoff._checkpoint_reason(status)
        if reason or not status.get('quotaFailure'):
            raise BridgeError(reason or 'Native quota evidence is required for automatic rotation')
        binding = self._read_binding(team)
        if not binding:
            raise BridgeError('Provider binding is unavailable')
        folder = self.state_dir / 'handoff-epochs'
        if folder.is_symlink():
            raise BridgeError('Invalid handoff storage')
        folder.mkdir(mode=0o700, exist_ok=True)
        epoch_path = folder / (handoff_id + '.json')
        if epoch_path.exists():
            raise BridgeError('This handoff already rotated; inspect its checkpoint before retrying')
        # Quiesce readers before a successor starts writing the shared event log.
        if binding['provider'] == 'codex':
            with self.codex._sessions_lock:
                old = self.codex._sessions.get(team)
            if not old:
                raise BridgeError('Native Codex checkpoint is no longer connected')
            with old.operation_lock, old.lock:
                if old.state not in {'idle', 'error'} or old.approvals:
                    raise BridgeError('Native work resumed before handoff')
                old.closing = True
                old.state = 'offline'
            old.connection.close()
            if old.connection.running():
                raise BridgeError('Native Codex connection did not stop')
            with self.codex._sessions_lock:
                self.codex._sessions.pop(team, None)
        else:
            old = self._session(team)
            with old.operation_lock:
                old.stop_event.set()
                old.runtime.stop()
                if old.watcher and old.watcher is not threading.current_thread():
                    old.watcher.join(timeout=3)
                    if old.watcher.is_alive():
                        raise BridgeError('Previous provider is still saving events; handoff was not started')
                self._drain(old)
                if old.runtime.status().get('connected'):
                    raise BridgeError('Previous provider did not stop')
            with self._sessions_lock:
                self._sessions.pop(team, None)
        native_path = self.codex._binding_path(team)
        worker_path = self.codex._worker_store._path(team)
        native_binding = self.codex._read_binding(team)
        usage = status.get('usageSummary') or {}
        epoch = {**binding, 'nativeBinding': native_binding,
                 'reportedTokens': usage.get('totalTokens', usage.get('reportedTokens')),
                 'handoffId': handoff_id, 'lastEventSeq': status.get('lastEventSeq')}
        descriptor = os.open(epoch_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(epoch, handle)
        # These are HQ pointers only, not provider history files.
        if native_path.exists():
            native_path.unlink()
        if worker_path.exists():
            os.replace(worker_path, folder / (handoff_id + '.workers'))
        self._write_binding(team, provider=target_provider, model=target_model,
            sessionId=None, projectRoot=binding['projectRoot'], mode=binding['mode'],
            accessMode=binding['accessMode'], planReady=False, reportedTokens=0,
            usageReported=False, usageDetails={}, previousHandoff=handoff_id)
        return {'rotated': True, 'project': binding['projectRoot'],
                'workMode': 'plan' if binding['mode'] == 'plan' else 'full' if binding['accessMode'] == 'full' else 'auto',
                'oldSessionId': binding.get('sessionId'), 'bindingSeq': status.get('lastEventSeq')}

    def tools(self, team: str) -> dict[str, Any]:
        provider = self._provider(_validate_team(team))
        if provider == 'codex':
            result={**self.codex.tools(team), 'provider':'codex', 'readOnly':False}
        elif provider == 'zai':
            session = self._session(team)
            try: result=session.runtime.tools()
            except ProviderRuntimeError as exc: raise BridgeError(str(exc)) from exc
        else:
            result={"provider": provider, "available": False, "readOnly":True, "tools": [], "reason": f"{provider} exposes tool activity but no verified HQ tool-inventory control adapter"}
        binding=self._read_binding(team)
        if binding:
            try:
                from project_context import ProjectContext
                result['sharedSkills']=ProjectContext(binding['projectRoot'],team).skills()
            except (ValueError,OSError):
                result['sharedSkillsUnavailable']=True
        return result

    def workers(self, team: str) -> dict[str, Any]:
        if self._provider(_validate_team(team)) == "codex":
            return {**self.codex.workers(team), "provider":"codex", "workerControl":True}
        if self._provider(team) == "zai":
            session = self._session(team)
            value = session.runtime.workers()
            return {**value, "team":team, "provider":"zai", "workerControl":False,
                    "connected":session.runtime.status().get("connected", False)}
        status = self.status(team)
        return {"team": team, "provider":status.get("provider"), "workerControl":False, "rootThreadId": status.get("threadId"), "connected": status["connected"], "authoritative": False, "complete": False, "workers": [], "error": "Worker hierarchy synchronization is not yet verified for this provider"}

    def send_worker(self, team: str, thread_id: str, prompt: str) -> dict[str, Any]:
        if self._provider(_validate_team(team)) == "codex":
            return self.codex.send_worker(team, thread_id, prompt)
        raise BridgeError("Worker messaging is not supported by this provider adapter")

    def worker_conversation(self, team: str, thread_id: str) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return {**self.codex.worker_conversation(team, thread_id), "provider": "codex"}
        status = self.status(team)
        return {"team": team, "threadId": thread_id, "worker": None, "messages": [],
                "provider": status.get("provider"), "truncated": False, "readOnly": True, "conversationAvailable": False,
                "error": "Worker conversation reading is not supported by this provider adapter"}

    def report_worker(self, team: str, thread_id: str, summary: str) -> dict[str, Any]:
        team = _validate_team(team)
        if self._provider(team) == "codex":
            return self.codex.report_worker(team, thread_id, summary)
        raise BridgeError("Worker reporting is not supported by this provider adapter")

    def stop_workers(self, team: str) -> dict[str, Any]:
        if self._provider(_validate_team(team)) == "codex":
            return self.codex.stop_workers(team)
        raise BridgeError("Worker stopping is not supported by this provider adapter")

    def _shutdown_session(self, session: _ProviderSession) -> None:
        try:
            session.runtime.stop()
            self._drain(session)
        except Exception:
            pass
        session.stop_event.set()
        if session.watcher and session.watcher is not threading.current_thread():
            session.watcher.join(timeout=1)

    def shutdown_all(self) -> None:
        with self._sessions_lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            self._shutdown_session(session)
        shutdown = getattr(self.codex, "shutdown_all", None)
        if callable(shutdown):
            shutdown()
