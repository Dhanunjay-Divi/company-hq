"""Text-only chat adapter for a user-configured OpenAI-compatible endpoint.

The adapter obeys the ProviderRuntime start/send/stop/events contract with a
fresh project binding per chat. It is strictly text-only: images and tools are
rejected and never advertised. The optional bearer key stays in process memory
and is redacted from every event. Message history is bounded by a
character-based estimate of the configured context hint; that estimate is not
an exact token measurement. Each turn is one non-streaming chat completion
with bounded output, a request timeout and cancellable in-flight work.
"""
from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable
from urllib import request
import uuid

from openai_compatible_connection import (
    OpenAICompatibleConnection,
    TransportError,
    _NoRedirect,
    assistant_text,
    chat_usage,
    fetch_json,
    finish_reason,
    origin_display,
    returned_tool_calls,
    valid_bearer_key,
    validated_base_url,
    validated_context_hint,
    validated_model,
    validated_temperature,
)
from provider_runtime import ProviderRuntime, ProviderRuntimeError, RuntimeEvent

TRANSPORT = "openai-chat-completions-v1"
DEFAULT_TIMEOUT = 120.0
MIN_TIMEOUT = 1.0
MAX_TIMEOUT = 600.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS_LIMIT = 16384
MAX_HISTORY_MESSAGES = 100
MAX_ASSISTANT_CHARS = 24_000
CHARS_PER_TOKEN = 4  # rough heuristic only; not an exact token measurement


class OpenAICompatibleRuntime(ProviderRuntime):
    """One text chat at a time over the OpenAI chat-completions wire format."""

    provider = "openai-compatible"

    def __init__(
        self,
        *,
        model: str | None = None,
        model_catalog: list[str] | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        context_hint: int | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
        post: Callable[..., Any] | None = None,
        opener: Any | None = None,
        session_id: str | None = None,
        **_: Any,
    ):
        super().__init__()
        if session_id:
            # Chat state is client-side history only; there is nothing to resume.
            raise ProviderRuntimeError("This runtime does not resume previous chats")
        try:
            self.model = validated_model(model) if model is not None else None
            self._base_url = validated_base_url(base_url) if base_url is not None else None
            self._key = valid_bearer_key(api_key)
            self._temperature = validated_temperature(temperature)
            self._context_hint = validated_context_hint(context_hint)
            self._max_output_tokens = self._bounded_tokens(max_output_tokens)
            self._timeout = self._bounded_timeout(timeout)
        except ValueError as exc:
            raise ProviderRuntimeError(str(exc)) from exc
        self._opener = opener or request.build_opener(_NoRedirect())
        self._catalog = [validated_model(item) for item in model_catalog] if model_catalog else []
        self._post = post or self._http_post
        self.project: str | None = None
        self.session_id: str | None = None
        self._messages: list[dict[str, str]] = []
        self._cancel = threading.Event()
        self._worker: threading.Thread | None = None
        self._active_response: Any = None
        self._generation = 0

    @staticmethod
    def _bounded_tokens(value: object) -> int:
        if value is None:
            return DEFAULT_MAX_OUTPUT_TOKENS
        if isinstance(value, bool) or not isinstance(value, int) or not 16 <= value <= MAX_OUTPUT_TOKENS_LIMIT:
            raise ValueError("Max output tokens must be an integer between 16 and 16384")
        return value

    @staticmethod
    def _bounded_timeout(value: object) -> float:
        if value is None:
            return DEFAULT_TIMEOUT
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not MIN_TIMEOUT <= value <= MAX_TIMEOUT:
            raise ValueError("Request timeout must be a number between 1 and 600 seconds")
        return float(value)

    @staticmethod
    def _estimated_tokens(messages: list[dict[str, str]]) -> int:
        return sum(len(message["content"]) // CHARS_PER_TOKEN + 8 for message in messages)

    def _bounded(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Trim a history copy to the context-hint estimate; never the last message."""
        pending = list(messages)
        while len(pending) > 1 and (len(pending) > MAX_HISTORY_MESSAGES or self._estimated_tokens(pending) > self._context_hint):
            pending.pop(0)
            if pending and pending[0]["role"] == "assistant":
                pending.pop(0)
        return pending

    def _http_post(self, url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
        tracked: list[Any] = []

        def track(response: Any) -> None:
            tracked.append(response)
            with self._lock:
                self._active_response = response

        try:
            return fetch_json(self._opener, url, method="POST", headers=headers, payload=payload, timeout=timeout, on_response=track)
        finally:
            if tracked:
                with self._lock:
                    if self._active_response is tracked[0]:
                        self._active_response = None

    def initialize(self, *, project: str | Path, model: str | None = None) -> dict[str, Any]:
        """Bind the requested model to the verified catalog before any paid turn."""
        root = self._project(project)
        if self.project is not None and self.project != root:
            raise ProviderRuntimeError("This chat belongs to another project")
        try:
            chosen = validated_model(model or self.model)
        except ValueError as exc:
            raise ProviderRuntimeError(str(exc)) from exc
        if self._catalog and chosen not in self._catalog:
            raise ProviderRuntimeError("Choose a model verified by this endpoint")
        self.model = chosen
        return {"models": [{"value": item} for item in (self._catalog or [chosen])], "sessionId": self.session_id}

    def start(self, prompt: str, *, project: str | Path, model: str | None = None, images: list[Any] | None = None, tools: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        if images:
            raise ProviderRuntimeError("This runtime is text-only; image input is not available")
        if tools:
            raise ProviderRuntimeError("This runtime is text-only; tool access is not available")
        if self._state == "running":
            raise ProviderRuntimeError("Wait for the current turn or stop the runtime")
        if model is not None:
            try:
                chosen = validated_model(model)
            except ValueError as exc:
                raise ProviderRuntimeError(str(exc)) from exc
            if self._catalog and chosen not in self._catalog:
                raise ProviderRuntimeError("Choose a model verified by this endpoint")
            self.model = chosen
        if not self._base_url:
            raise ProviderRuntimeError("Configure the endpoint base URL before starting")
        if not self.model:
            raise ProviderRuntimeError("Choose a model ID before starting")
        root = self._project(project)
        if self.project is not None and self.project != root:
            raise ProviderRuntimeError("This chat belongs to another project")
        if self.project is None:
            # Fresh binding: new session identity and empty history.
            self.project = root
            self.session_id = str(uuid.uuid4())
            with self._lock:
                self._messages = []
        self._state = "idle"
        self._cancel.clear()
        self._event("runtime.started", project=self.project, sessionId=self.session_id, model=self.model)
        return self.send(prompt)

    def send(self, prompt: str, *, images: list[Any] | None = None, tools: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        if images:
            raise ProviderRuntimeError("This runtime is text-only; image input is not available")
        if tools:
            raise ProviderRuntimeError("This runtime is text-only; tool access is not available")
        prompt = self._prompt(prompt)
        turn_id, item_id = str(uuid.uuid4()), str(uuid.uuid4())
        with self._lock:
            if self._state == "running":
                raise ProviderRuntimeError("Wait for the current turn or stop the runtime")
            if self._state != "idle" or self.project is None or self.session_id is None:
                raise ProviderRuntimeError("OpenAI-compatible runtime is not started")
            self._state = "running"
            self._cancel.clear()
            self._generation += 1
            generation = self._generation
            history = self._bounded([*self._messages, {"role": "user", "content": prompt}])
        self._event("message.user", text=prompt, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
        self._worker = threading.Thread(target=self._run_turn, args=(history, prompt, turn_id, item_id, self.session_id, generation), name="company-hq-openai-compatible", daemon=True)
        self._worker.start()
        return {"accepted": True, "provider": self.provider, "sessionId": self.session_id, "turnId": turn_id, "itemId": item_id}

    def _run_turn(self, history: list[dict[str, str]], prompt: str, turn_id: str, item_id: str, session_id: str, generation: int) -> None:
        try:
            payload: dict[str, Any] = {"model": self.model, "messages": history, "max_tokens": self._max_output_tokens}
            if self._temperature is not None:
                payload["temperature"] = self._temperature
            headers = {"Content-Type": "application/json"}
            if self._key:
                headers["Authorization"] = "Bearer " + self._key
            result = self._post(self._base_url + "/chat/completions", payload, headers, self._timeout)
            text = assistant_text(result)
            if text is None:
                if returned_tool_calls(result):
                    raise ProviderRuntimeError("The endpoint returned tool calls; this runtime is text-only")
                raise ProviderRuntimeError("The endpoint did not return assistant text")
            bounded = text[:MAX_ASSISTANT_CHARS]
            data: dict[str, Any] = {"text": bounded, "sessionId": session_id, "turnId": turn_id, "itemId": item_id}
            reason = finish_reason(result)
            if reason:
                data["finishReason"] = reason
            usage = chat_usage(result)
            if usage:
                data["usage"] = usage
            with self._lock:
                if generation != self._generation or self._cancel.is_set():
                    return
                self._messages.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": bounded}])
                self._messages = self._bounded(self._messages)
                self._event("message.completed", **data)
                self._state = "idle"
        except (ProviderRuntimeError, TransportError) as exc:
            self._fail_turn(turn_id, item_id, str(exc), generation)
        except Exception:
            self._fail_turn(turn_id, item_id, "The OpenAI-compatible endpoint request failed", generation)

    def _fail_turn(self, turn_id: str, item_id: str, message: str, generation: int) -> None:
        with self._lock:
            if generation != self._generation or self._cancel.is_set():
                return
            self._state = "error"
            self._event("runtime.error", message=message, turnId=turn_id, itemId=item_id)

    def stop(self) -> dict[str, Any]:
        """Cancel any in-flight turn and release the project binding."""
        self._cancel.set()
        with self._lock:
            self._generation += 1
            response = self._active_response
            self._active_response = None
            self._messages = []
        try:
            if response is not None:
                response.close()
        except Exception:
            pass
        session = self.session_id
        self.project = None
        self.session_id = None
        self._state = "offline"
        self._event("runtime.stopped", sessionId=session)
        return {"accepted": True, "sessionId": session}

    def _event(self, type_: str, **data: Any) -> RuntimeEvent:
        key = self._key
        if key:
            def redact(value: Any) -> Any:
                if isinstance(value, str):
                    return value.replace(key, "[redacted]")
                if isinstance(value, list):
                    return [redact(item) for item in value]
                if isinstance(value, dict):
                    return {name: redact(item) for name, item in value.items()}
                return value
            data = redact(data)
        return super()._event(type_, **data)

    def status(self) -> dict[str, Any]:
        value = super().status()
        value.update({
            "sessionId": self.session_id,
            "project": self.project,
            "transport": TRANSPORT,
            "turns": len(self._messages) // 2,
            "endpoint": origin_display(self._base_url) if self._base_url else None,
            "models": [{"value": item} for item in self._catalog],
        })
        return value

    @classmethod
    def from_connection(cls, connection: OpenAICompatibleConnection, **kwargs: Any) -> OpenAICompatibleRuntime:
        """Bind a runtime from a configured connection; the key is copied once."""
        config = connection.config_for_runtime()
        if not config:
            raise ProviderRuntimeError("Configure the OpenAI-compatible endpoint before starting")
        return cls(
            model=config.get("model"),
            model_catalog=connection.snapshot().get('models') or [],
            base_url=config.get("base_url"),
            api_key=config.get("key"),
            temperature=config.get("temperature"),
            context_hint=config.get("context_hint"),
            **kwargs,
        )


def runtime(**kwargs: Any) -> OpenAICompatibleRuntime:
    return OpenAICompatibleRuntime(**kwargs)
