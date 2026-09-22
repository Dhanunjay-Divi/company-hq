"""Strict stdio JSON-RPC adapter for an explicitly configured ACP executable.

ACP is an open protocol, not proof that a detected app supports it.  Cursor,
Kimi, and Z.ai remain unavailable unless their exact command is supplied by the
caller and completes the protocol handshake.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import threading
from typing import Any, Callable

from provider_runtime import ProviderRuntime, ProviderRuntimeError, UnavailableRuntime


@dataclass
class _Pending:
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: str | None = None


class AcpRuntime(ProviderRuntime):
    """ACP lifecycle: initialize -> session/new -> session/prompt -> cancel."""

    def __init__(self, provider: str, command: list[str], *, model: str | None = None, process_factory: Callable[..., Any] = subprocess.Popen, request_timeout: float = 15.0):
        super().__init__(model=model)
        if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
            raise ProviderRuntimeError("ACP command must be a non-empty argument list")
        self.provider, self.command, self.factory = provider, list(command), process_factory
        self.request_timeout = request_timeout
        self.process: Any | None = None
        self.project: str | None = None
        self.session_id: str | None = None
        self._next = 1
        self._pending: dict[int, _Pending] = {}
        self._reader: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._stopped = False

    def _running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _send(self, method: str, params: dict[str, Any], *, respond_to: object | None = None) -> int:
        if not self._running() or not getattr(self.process, "stdin", None):
            raise ProviderRuntimeError("ACP runtime is not connected")
        ident = self._next
        self._next += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": ident if respond_to is None else respond_to, "method": method, "params": params}
        with self._write_lock:
            self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
        return ident

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        ident = self._next
        pending = _Pending()
        self._pending[ident] = pending
        try:
            self._send(method, params)
            if not pending.done.wait(self.request_timeout):
                raise ProviderRuntimeError(f"ACP provider timed out during {method}")
            if pending.error:
                raise ProviderRuntimeError(pending.error)
            return pending.result or {}
        finally:
            self._pending.pop(ident, None)

    def start(self, prompt: str, *, project: str | Path, model: str | None = None, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        prompt = self._prompt(prompt)
        if images:
            raise ProviderRuntimeError("This ACP adapter has no verified image-content mapping")
        if model:
            self.model = model
        project_path = self._project(project)
        if self._running():
            if project_path != self.project:
                raise ProviderRuntimeError("ACP session is already bound to another project")
            return self.send(prompt)
        try:
            self.process = self.factory(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, cwd=project_path)
        except OSError as exc:
            self._state = "error"
            self._event("runtime.error", message="ACP provider could not start")
            raise ProviderRuntimeError("ACP provider could not start") from exc
        if not getattr(self.process, "stdin", None) or not getattr(self.process, "stdout", None):
            self._state = "error"
            raise ProviderRuntimeError("ACP provider did not expose stdio JSON-RPC")
        self.project, self._state, self._stopped = project_path, "starting", False
        self._reader = threading.Thread(target=self._read, name=f"company-hq-{self.provider}-acp", daemon=True)
        self._reader.start()
        try:
            self._rpc("initialize", {
                "protocolVersion": 1,
                "clientInfo": {"name": "company-hq", "version": "1"},
                "clientCapabilities": {},
            })
            session = self._rpc("session/new", {"cwd": self.project, "mcpServers": []})
            candidate = session.get("sessionId")
            if not isinstance(candidate, str) or not candidate:
                raise ProviderRuntimeError("ACP provider did not return a session ID")
            self.session_id, self._state = candidate, "idle"
            self._event("runtime.started", project=self.project, sessionId=self.session_id)
            return self.send(prompt)
        except Exception:
            self.stop()
            raise

    def send(self, prompt: str, *, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        prompt = self._prompt(prompt)
        if images:
            raise ProviderRuntimeError("This ACP adapter has no verified image-content mapping")
        if self._state not in {"idle", "running"} or not self.session_id:
            raise ProviderRuntimeError("ACP runtime is not started")
        self._state = "running"
        self._event("message.user", text=prompt)
        self._rpc("session/prompt", {"sessionId": self.session_id, "prompt": [{"type": "text", "text": prompt}]})
        self._state = "idle"
        return {"accepted": True, "provider": self.provider, "sessionId": self.session_id}

    def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    self._event("runtime.warning", message="ACP provider emitted malformed JSON-RPC")
                    continue
                if isinstance(message, dict):
                    self._handle(message)
        finally:
            if not self._stopped and self._state not in {"idle", "offline", "error"}:
                self._state = "error"
                self._event("runtime.error", message="ACP provider stream closed")
            for pending in list(self._pending.values()):
                pending.error = "ACP provider stream closed"
                pending.done.set()

    def _reply(self, ident: object, result: dict[str, Any]) -> None:
        if not self._running() or not getattr(self.process, "stdin", None):
            return
        with self._write_lock:
            self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident, "result": result}, separators=(",", ":")) + "\n")
            self.process.stdin.flush()

    def _handle(self, message: dict[str, Any]) -> None:
        ident = message.get("id")
        if ident in self._pending and ("result" in message or "error" in message):
            pending = self._pending[ident]
            if "error" in message:
                pending.error = "ACP provider rejected a request"
            else:
                pending.result = message.get("result") if isinstance(message.get("result"), dict) else {}
            pending.done.set()
            return
        method, params = message.get("method"), message.get("params")
        if not isinstance(method, str) or not isinstance(params, dict):
            return
        if ident is not None:
            # HQ does not silently grant filesystem/terminal/tool permissions.
            if method in {"session/request_permission", "session/requestPermission"}:
                self._event("approval.requested", providerMethod=method, sessionId=self.session_id)
                self._reply(ident, {"outcome": "cancelled"})
            elif method in {"session/request_user_input", "session/requestUserInput"}:
                self._event("question.requested", providerMethod=method, sessionId=self.session_id)
                self._reply(ident, {"responses": {}})
            else:
                self._event("request.denied", providerMethod=method)
                self._reply(ident, {})
            return
        if method in {"session/update", "sessionUpdate"}:
            update = params.get("update")
            if isinstance(update, dict):
                kind = update.get("sessionUpdate") or update.get("type")
                if kind in {"agent_message_chunk", "agentMessageChunk"}:
                    content = update.get("content")
                    text = content.get("text") if isinstance(content, dict) else None
                    if isinstance(text, str):
                        self._event("message.delta", text=text[:24_000])
                elif kind in {"tool_call", "toolCall"}:
                    self._event("tool.requested", tool=update.get("title") if isinstance(update.get("title"), str) else "unknown")
                else:
                    self._event("provider.event", kind=kind if isinstance(kind, str) else "session.update")
            return
        self._event("provider.event", kind=method)

    def stop(self) -> dict[str, Any]:
        self._stopped = True
        process = self.process
        if self.session_id and self._running():
            try:
                self._rpc("session/cancel", {"sessionId": self.session_id})
            except ProviderRuntimeError:
                pass
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(process, stream_name, None) if process is not None else None
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        self._state = "offline"
        self._event("runtime.stopped", sessionId=self.session_id)
        return {"accepted": True, "sessionId": self.session_id}

    def status(self) -> dict[str, Any]:
        value = super().status()
        value.update({
            "sessionId": self.session_id,
            "project": self.project,
            "transport": "acp-json-rpc",
            "input": "text_only",
            "support": "experimental_fixture_only",
            "verifiedProvider": False,
        })
        return value


def runtime_for_provider(provider: str, **kwargs: Any) -> ProviderRuntime:
    command = kwargs.pop("command", None)
    experimental = kwargs.pop("experimental_acp", False)
    if command is None or experimental is not True:
        return UnavailableRuntime(
            provider,
            f"{provider} has no provider-specific verified ACP adapter; executable discovery or a generic command alone is not readiness proof.",
        )
    return AcpRuntime(provider, command, **kwargs)
