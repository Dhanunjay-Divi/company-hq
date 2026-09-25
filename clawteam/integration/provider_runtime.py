"""Provider-neutral runtime contract.

Adapters preserve each provider's account home and authentication. They emit only
observations from their local transport; a binary being found is never claimed as
a live provider session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
from typing import Any, Callable
from urllib import request


class ProviderRuntimeError(RuntimeError):
    """A safe, user-facing provider transport failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: Any, depth: int = 0) -> Any:
    """Keep in-memory transport observations finite and JSON-compatible."""
    if depth >= 6:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:24_000]
    if isinstance(value, (list, tuple)):
        return [_bounded(item, depth + 1) for item in value[:100]]
    if isinstance(value, dict):
        return {
            str(key)[:200]: _bounded(item, depth + 1)
            for key, item in list(value.items())[:100]
        }
    return str(value)[:1000]


@dataclass(frozen=True)
class RuntimeEvent:
    seq: int
    type: str
    data: dict[str, Any]
    time: str = field(default_factory=_now)


class ProviderRuntime:
    """Normalized asynchronous session contract.

    Start/send return after a turn has been accepted by the local transport.
    Completion, tool activity, questions, and errors arrive through ``events``.
    Company HQ's run ledger, rather than this adapter, owns durable replay.
    """
    provider = "unknown"
    max_events = 300

    def __init__(self, *, model: str | None = None):
        self.model = model
        self._state = "offline"
        self._events: list[RuntimeEvent] = []
        self._next_seq = 1
        self._lock = threading.RLock()

    @staticmethod
    def _prompt(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 40_000:
            raise ProviderRuntimeError("Prompt must be non-empty text of at most 40000 characters")
        return value.strip()

    @staticmethod
    def _project(value: str | Path) -> str:
        try:
            path = Path(value).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ProviderRuntimeError("Approved project folder is unavailable") from exc
        if not path.is_dir() or path == Path("/") or path == Path.home():
            raise ProviderRuntimeError("Approved project folder must be a non-home directory")
        return str(path)

    def _event(self, type_: str, **data: Any) -> RuntimeEvent:
        with self._lock:
            event = RuntimeEvent(self._next_seq, type_, _bounded(data))
            self._next_seq += 1
            self._events.append(event)
            if len(self._events) > self.max_events:
                del self._events[: len(self._events) - self.max_events]
            return event

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "provider": self.provider,
                "state": self._state,
                "model": self.model,
                "connected": self._state not in ("offline", "error"),
                "lastEventSeq": self._next_seq - 1,
            }

    def events(self, after: int = 0) -> dict[str, Any]:
        if not isinstance(after, int) or isinstance(after, bool) or after < 0:
            raise ProviderRuntimeError("Event cursor must be a non-negative integer")
        with self._lock:
            oldest = self._events[0].seq if self._events else self._next_seq
            events = [event for event in self._events if event.seq > after]
            return {
                "afterSeq": after,
                "nextSeq": self._next_seq - 1,
                "truncated": after + 1 < oldest,
                "events": [
                    {"seq": event.seq, "type": event.type, "data": event.data, "time": event.time}
                    for event in events
                ],
            }

    def start(self, prompt: str, *, project: str | Path, model: str | None = None, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def send(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def stop(self) -> dict[str, Any]:
        raise NotImplementedError

    def respond(self, request_id: str, response: object) -> dict[str, Any]:
        raise ProviderRuntimeError(f"{self.provider} has no pending interactive request")

    def set_access(self, access: str) -> dict[str, Any]:
        raise ProviderRuntimeError(f"{self.provider} does not support changing access mode")


class UnavailableRuntime(ProviderRuntime):
    def __init__(self, provider: str, reason: str):
        super().__init__()
        self.provider, self.reason = provider, reason

    def _unavailable(self) -> None:
        raise ProviderRuntimeError(self.reason)

    start = lambda self, *args, **kwargs: self._unavailable()
    send = lambda self, *args, **kwargs: self._unavailable()
    stop = lambda self, *args, **kwargs: self._unavailable()


class OllamaRuntime(ProviderRuntime):
    """Asynchronous local Ollama chat adapter with turn history and cancellation."""
    provider = "ollama"

    def __init__(self, *, model: str | None = None, endpoint: str = "http://127.0.0.1:11434", post: Callable[..., dict[str, Any]] | None = None):
        super().__init__(model=model)
        self.endpoint = endpoint.rstrip("/")
        self._post = post or self._http_post
        self.project: str | None = None
        self.session_id = str(uuid.uuid4())
        self._cancel = threading.Event()
        self._worker: threading.Thread | None = None
        self._active_response: Any | None = None
        self._messages: list[dict[str, str]] = []
        self._generation = 0

    def _http_post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, body, {"Content-Type": "application/json"}, method="POST")
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        with request.urlopen(req, timeout=120) as response:
            with self._lock:
                self._active_response = response
            for raw in response:
                if self._cancel.is_set():
                    break
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ProviderRuntimeError("Ollama returned invalid JSON") from exc
                if not isinstance(value, dict):
                    continue
                message = value.get("message")
                text = message.get("content") if isinstance(message, dict) else None
                if isinstance(text, str) and text:
                    chunks.append(text)
                    self._event("message.delta", text=text)
                if value.get("done") is True:
                    usage = {key: value[key] for key in ("prompt_eval_count", "eval_count", "total_duration") if isinstance(value.get(key), (int, float))}
        with self._lock:
            self._active_response = None
        return {"response": "".join(chunks), "usage": usage}

    def start(self, prompt: str, *, project: str | Path, model: str | None = None, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        if images:
            raise ProviderRuntimeError("Ollama image input is not enabled by this adapter")
        if model:
            self.model = model
        if not self.model:
            raise ProviderRuntimeError("Choose a local Ollama model before starting")
        self.project = self._project(project)
        self._state = "idle"
        self._cancel.clear()
        self._event("runtime.started", project=self.project, sessionId=self.session_id)
        return self.send(prompt)

    def send(self, prompt: str, *, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        if images:
            raise ProviderRuntimeError("Ollama image input is not enabled by this adapter")
        if self._state != "idle":
            raise ProviderRuntimeError("Ollama runtime is not started")
        prompt = self._prompt(prompt)
        turn_id, item_id = str(uuid.uuid4()), str(uuid.uuid4())
        self._state = "running"
        self._cancel.clear()
        with self._lock:
            self._generation += 1
            generation = self._generation
            history = [*self._messages, {"role": "user", "content": prompt}]
        self._event("message.user", text=prompt, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
        self._worker = threading.Thread(
            target=self._run_turn, args=(history, prompt, turn_id, item_id, generation),
            name="company-hq-ollama", daemon=True,
        )
        self._worker.start()
        return {"accepted": True, "provider": self.provider, "sessionId": self.session_id, "turnId": turn_id, "itemId": item_id}

    def _run_turn(self, history: list[dict[str, str]], prompt: str, turn_id: str, item_id: str, generation: int) -> None:
        try:
            response = self._post(self.endpoint + "/api/chat", {"model": self.model, "messages": history, "stream": True})
            with self._lock:
                current = generation == self._generation and not self._cancel.is_set()
            if not current:
                return
            text = response.get("response")
            if text is None and isinstance(response.get("message"), dict):
                text = response["message"].get("content")
            if not isinstance(text, str):
                raise ProviderRuntimeError("Ollama did not return text")
            with self._lock:
                self._messages.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": text}])
            data: dict[str, Any] = {"text": text, "sessionId": self.session_id, "turnId": turn_id, "itemId": item_id}
            if isinstance(response.get("usage"), dict):
                data["usage"] = response["usage"]
            self._event("message.completed", **data)
            self._state = "idle"
        except Exception as exc:
            if self._cancel.is_set() or generation != self._generation:
                return
            self._state = "error"
            self._event("runtime.error", message="Local Ollama request failed", turnId=turn_id, itemId=item_id)

    def stop(self) -> dict[str, Any]:
        self._cancel.set()
        with self._lock:
            self._generation += 1
            response = self._active_response
            self._active_response = None
        try:
            if response is not None:
                response.close()
        except OSError:
            pass
        self._state = "offline"
        self._event("runtime.stopped", sessionId=self.session_id)
        return {"accepted": True, "sessionId": self.session_id}

    def status(self) -> dict[str, Any]:
        value = super().status()
        value.update({"sessionId": self.session_id, "project": self.project, "transport": "ollama-chat-http", "turns": len(self._messages) // 2})
        return value


def executable_available(name: str, paths: tuple[Path, ...] = ()) -> str | None:
    """Bounded executable check only; never reads provider configuration."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for path in paths:
        if path.is_file() and path.stat().st_mode & 0o111:
            return str(path)
    return None


def create_runtime(provider: str, **kwargs: Any) -> ProviderRuntime:
    """Construct a real adapter only for a reviewed provider transport."""
    if provider == "ollama":
        return OllamaRuntime(**kwargs)
    if provider == "deepseek":
        from deepseek_runtime import runtime
        return runtime(**kwargs)
    if provider == "claude":
        from claude_runtime import runtime
        return runtime(**kwargs)
    if provider == "kimi":
        from kimi_runtime import runtime
        return runtime(**kwargs)
    if provider == "zai":
        from zcode_runtime import runtime
        return runtime(**kwargs)
    if provider == "cursor":
        from acp_runtime import runtime_for_provider
        return runtime_for_provider(provider, **kwargs)
    return UnavailableRuntime(provider, f"{provider} does not have a verified Company HQ native runtime adapter.")
