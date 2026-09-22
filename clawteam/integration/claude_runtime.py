"""Persistent official Claude Code stream-json transport.

The adapter speaks the same control protocol used by Anthropic's Agent SDK. It
inherits the caller's environment so Claude Code remains the owner of account
sign-in, settings, transcripts, and billing.
"""
from __future__ import annotations

import base64
import binascii
from collections import deque
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid
from typing import Any, Callable

from provider_runtime import ProviderRuntime, ProviderRuntimeError, executable_available


MAX_LINE = 2_000_000
MAX_IMAGE_BYTES = 6 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ACCESS_MODES = {"plan", "workspace", "full"}


@dataclass
class _PendingControl:
    done: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None
    error: str | None = None


def claude_binary() -> str | None:
    root = Path(__file__).resolve().parents[2]
    names = ("claude.cmd", "claude") if os.name == "nt" else ("claude",)
    paths = tuple(root / "build" / "providers" / "claude-code" / "node_modules" / ".bin" / name for name in names)
    return executable_available("claude", paths)


def runtime(**kwargs: Any) -> "ClaudeCodeRuntime":
    """Discover the official CLI, including HQ's pinned ignored install."""
    return ClaudeCodeRuntime(binary=claude_binary(), **kwargs)


def auth_status(binary: str | None = None, *, timeout: float = 5.0) -> dict[str, Any]:
    """Return a sanitized, model-free official CLI authentication probe."""
    executable = binary or claude_binary()
    if not executable:
        return {"installed": False, "authenticated": False}
    try:
        completed = subprocess.run(
            [executable, "auth", "status", "--json"], capture_output=True,
            text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"installed": True, "authenticated": False, "status": "unavailable"}
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        value = {}
    authenticated = bool(value.get("loggedIn") or value.get("authenticated")) if isinstance(value, dict) else False
    result: dict[str, Any] = {"installed": True, "authenticated": authenticated, "status": "connected" if authenticated else "signed_out"}
    if isinstance(value, dict):
        for source, target in (("authMethod", "authMethod"), ("subscriptionType", "subscriptionType")):
            if isinstance(value.get(source), str):
                result[target] = value[source][:100]
    return result


def probe(binary: str | None = None, *, timeout: float = 5.0) -> dict[str, Any]:
    """Probe the official binary and auth state without a model invocation."""
    executable = binary or claude_binary()
    if not executable:
        return {"installed": False, "authenticated": False, "models": []}
    try:
        completed = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        version = completed.stdout.strip()[:200] if completed.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        version = None
    return {**auth_status(executable, timeout=timeout), "binary": executable, "version": version, "models": []}


def login_command(binary: str | None = None) -> list[str]:
    """Return the official interactive login command without starting it."""
    executable = binary or claude_binary()
    if not executable:
        raise ProviderRuntimeError("Claude Code CLI is unavailable")
    return [executable, "auth", "login"]


class ClaudeCodeRuntime(ProviderRuntime):
    provider = "claude"

    def __init__(
        self,
        binary: str | None = None,
        *,
        model: str | None = None,
        permission_mode: str = "default",
        access: str | None = None,
        session_id: str | None = None,
        process_factory: Callable[..., Any] = subprocess.Popen,
        request_timeout: float = 10.0,
    ) -> None:
        super().__init__(model=model)
        if permission_mode not in {"default", "plan", "acceptEdits", "dontAsk", "auto"}:
            raise ProviderRuntimeError("Unsupported Claude permission mode")
        if access is not None and access not in ACCESS_MODES:
            raise ProviderRuntimeError("Claude access must be plan, workspace, or full")
        self.binary = claude_binary() if binary is None else binary
        self.access = access or ("plan" if permission_mode == "plan" else "workspace")
        self.permission_mode = "plan" if self.access == "plan" else "bypassPermissions" if self.access == "full" else permission_mode
        self._factory = process_factory
        self.request_timeout = request_timeout
        self.project: str | None = None
        if session_id is not None and (not isinstance(session_id, str) or not session_id or len(session_id) > 512):
            raise ProviderRuntimeError("Claude session ID is invalid")
        self.session_id: str | None = session_id
        self.process: Any | None = None
        self.models: list[dict[str, Any]] = []
        self._generation = 0
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._pending_controls: dict[str, _PendingControl] = {}
        self._pending_permissions: dict[str, dict[str, Any]] = {}
        self._cancelled_permissions: set[str] = set()
        self._permission_turns: dict[str, tuple[str | None, bool]] = {}
        self._turn_ids: deque[str] = deque()
        self._turn_items: dict[str, str] = {}
        self._stopped = False

    def _args(self, *, resume: bool) -> list[str]:
        if not self.binary:
            raise ProviderRuntimeError(
                "Claude Code CLI is unavailable. Install the pinned official CLI or sign in with the official Claude Code client; Claude Desktop alone is not an HQ execution adapter."
            )
        args = [
            self.binary,
            "-p",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--verbose",
            "--replay-user-messages",
            # This is the official Agent SDK's stdio permission transport. It
            # causes permission asks to arrive as control_request records.
            "--permission-prompt-tool", "stdio",
        ]
        if self.model:
            args.extend(["--model", self.model])
        if self.access == "full":
            args.append("--allow-dangerously-skip-permissions")
        if self.permission_mode != "default":
            args.extend(["--permission-mode", self.permission_mode])
        if resume and self.session_id:
            args.extend(["--resume", self.session_id])
        return args

    @staticmethod
    def _bounded_text(value: object, maximum: int = 24_000) -> str | None:
        return value[:maximum] if isinstance(value, str) else None

    @staticmethod
    def _image_block(image: object) -> dict[str, Any]:
        if not isinstance(image, dict):
            raise ProviderRuntimeError("Claude image attachments must be resolved image records")
        media_type = image.get("mimeType") or image.get("media_type")
        if media_type not in IMAGE_TYPES:
            raise ProviderRuntimeError("Claude image attachment has an unsupported media type")
        encoded = image.get("dataBase64") or image.get("data")
        if encoded is None and isinstance(image.get("path"), str):
            try:
                raw = Path(image["path"]).read_bytes()
            except OSError as exc:
                raise ProviderRuntimeError("Claude image attachment is unavailable") from exc
            if len(raw) > MAX_IMAGE_BYTES:
                raise ProviderRuntimeError("Claude image attachment exceeds 6 MiB")
            encoded = base64.b64encode(raw).decode("ascii")
        if not isinstance(encoded, str):
            raise ProviderRuntimeError("Claude image attachment has no deliverable content")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ProviderRuntimeError("Claude image attachment is not valid base64") from exc
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ProviderRuntimeError("Claude image attachment must contain at most 6 MiB")
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}}

    @classmethod
    def _message(cls, prompt: str, images: list[Any] | None = None) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(cls._image_block(image) for image in (images or []))
        return json.dumps({
            "type": "user",
            "session_id": "",
            "message": {"role": "user", "content": content},
            "parent_tool_use_id": None,
        }, separators=(",", ":")) + "\n"

    def _running(self, process: Any | None = None) -> bool:
        candidate = self.process if process is None else process
        return candidate is not None and candidate.poll() is None

    def _write(self, payload: dict[str, Any] | str, *, process: Any | None = None) -> None:
        candidate = self.process if process is None else process
        if not self._running(candidate) or not getattr(candidate, "stdin", None):
            raise ProviderRuntimeError("Claude Code runtime is not connected")
        line = payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":")) + "\n"
        with self._write_lock:
            try:
                candidate.stdin.write(line)
                candidate.stdin.flush()
            except (OSError, ValueError) as exc:
                raise ProviderRuntimeError("Claude Code input stream closed") from exc

    def _control(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        pending = _PendingControl()
        with self._lock:
            self._pending_controls[request_id] = pending
        try:
            self._write({"type": "control_request", "request_id": request_id, "request": request})
            if not pending.done.wait(self.request_timeout if timeout is None else timeout):
                raise ProviderRuntimeError(f"Claude Code timed out during {request.get('subtype', 'control request')}")
            if pending.error:
                raise ProviderRuntimeError(pending.error)
            return pending.response or {}
        finally:
            with self._lock:
                self._pending_controls.pop(request_id, None)

    @staticmethod
    def _safe_models(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        models: list[dict[str, Any]] = []
        for row in value[:100]:
            if not isinstance(row, dict) or not isinstance(row.get("value"), str):
                continue
            item = {"value": row["value"][:200]}
            for key in ("resolvedModel", "displayName", "description"):
                if isinstance(row.get(key), str):
                    item[key] = row[key][:1000]
            for key in ("supportsEffort", "supportsAdaptiveThinking", "supportsFastMode", "supportsAutoMode"):
                if isinstance(row.get(key), bool):
                    item[key] = row[key]
            levels = row.get("supportedEffortLevels")
            if isinstance(levels, list):
                item["supportedEffortLevels"] = [level for level in levels[:10] if isinstance(level, str)]
            models.append(item)
        return models

    def _launch(self, *, resume: bool) -> None:
        assert self.project
        try:
            process = self._factory(
                self._args(resume=resume), cwd=self.project, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            )
        except OSError as exc:
            self._state = "error"
            self._event("runtime.error", message="Claude Code could not start")
            raise ProviderRuntimeError("Claude Code could not start") from exc
        if not getattr(process, "stdin", None) or not getattr(process, "stdout", None):
            self._state = "error"
            try:
                process.terminate()
            except (AttributeError, OSError):
                pass
            raise ProviderRuntimeError("Claude Code did not expose JSONL streams")
        with self._lock:
            self.process = process
            self._generation += 1
            generation = self._generation
            self._stopped = False
        self._reader = threading.Thread(target=self._read_stdout, args=(process, generation), name="company-hq-claude-stdout", daemon=True)
        self._reader.start()
        if getattr(process, "stderr", None):
            self._stderr_reader = threading.Thread(target=self._read_stderr, args=(process,), name="company-hq-claude-stderr", daemon=True)
            self._stderr_reader.start()

    def initialize(self, *, project: str | Path, model: str | None = None) -> dict[str, Any]:
        """Launch and handshake without submitting a model prompt."""
        project_path = self._project(project)
        with self._lock:
            if self._running():
                if project_path != self.project:
                    raise ProviderRuntimeError("Claude Code session is already bound to another project")
                running = True
            else:
                running = False
        if running:
            if model and model != self.model:
                self._control({"subtype": "set_model", "model": model})
                self.model = model
                self._event("runtime.model", model=model)
            return {"accepted": True, "provider": self.provider, "sessionId": self.session_id, "models": self.list_models()}
        if model:
            self.model = model
        with self._lock:
            self.project = project_path
            self._state = "starting"
            resume = bool(self.session_id)
        try:
            self._launch(resume=resume)
            initialized = self._control({"subtype": "initialize", "sdkMcpServers": []})
            self.models = self._safe_models(initialized.get("models"))
            pending = initialized.get("pending_permission_requests")
            if isinstance(pending, list):
                for request in pending:
                    if isinstance(request, dict):
                        self._handle_control_request(request, recovered=True)
            self._state = "idle"
            self._event("runtime.started", project=self.project, resumed=resume, sessionId=self.session_id)
            self._event("runtime.models", models=self.models)
            return {"accepted": True, "provider": self.provider, "sessionId": self.session_id, "models": self.list_models()}
        except Exception:
            if self.process is not None:
                self.stop()
            else:
                self._state = "error"
            raise

    def list_models(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(model) for model in self.models]

    def start(self, prompt: str, *, project: str | Path, model: str | None = None, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        prompt = self._prompt(prompt)
        wire_message = self._message(prompt, images)  # Validate before launch.
        self.initialize(project=project, model=model)
        return self._send_wire(prompt, wire_message, images)

    def _send_wire(self, prompt: str, wire_message: str, images: list[Any] | None) -> dict[str, Any]:
        turn_id, item_id = str(uuid.uuid4()), str(uuid.uuid4())
        with self._lock:
            self._turn_ids.append(turn_id)
            self._turn_items[turn_id] = item_id
        try:
            self._write(wire_message)
        except ProviderRuntimeError:
            with self._lock:
                try:
                    self._turn_ids.remove(turn_id)
                except ValueError:
                    pass
                self._turn_items.pop(turn_id, None)
            self._state = "error"
            self._event("runtime.error", message="Claude Code input stream closed")
            raise
        self._state = "running"
        data: dict[str, Any] = {"text": prompt, "turnId": turn_id, "itemId": item_id, "sessionId": self.session_id}
        if images:
            data["attachments"] = [
                {key: image[key] for key in ("id", "name", "mimeType", "url") if key in image}
                for image in images if isinstance(image, dict)
            ]
        self._event("message.user", **data)
        return {"accepted": True, "provider": self.provider, "sessionId": self.session_id, "turnId": turn_id, "itemId": item_id}

    def send(self, prompt: str, *, images: list[Any] | None = None, **_: Any) -> dict[str, Any]:
        prompt = self._prompt(prompt)
        wire_message = self._message(prompt, images)
        if not self._running() or self._state not in {"idle", "running"}:
            raise ProviderRuntimeError("Claude Code runtime is not started")
        return self._send_wire(prompt, wire_message, images)

    def set_access(self, access: str) -> dict[str, Any]:
        """Apply an explicit per-chat access choice.

        Full access must be selected before launch because Claude requires a
        launch-time opt-in flag. Plan/workspace can also change in process.
        """
        if access not in ACCESS_MODES:
            raise ProviderRuntimeError("Claude access must be plan, workspace, or full")
        if self._running() and access != self.access and "full" in {access, self.access}:
            raise ProviderRuntimeError("Restart Claude Code when changing full access")
        target = "plan" if access == "plan" else "bypassPermissions" if access == "full" else "default"
        if self._running() and target != self.permission_mode:
            self._control({"subtype": "set_permission_mode", "mode": target})
        self.access, self.permission_mode = access, target
        self._event("runtime.access", access=access)
        return {"accepted": True, "access": access}

    def _read_stdout(self, process: Any, generation: int) -> None:
        malformed = 0
        try:
            for raw in process.stdout:
                if len(raw) > MAX_LINE:
                    malformed += 1
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if isinstance(row, dict):
                    self._handle(row)
        except (OSError, ValueError):
            pass
        finally:
            with self._lock:
                current = generation == self._generation
                stopped = self._stopped
            if malformed and current:
                self._event("runtime.warning", message="Claude Code emitted malformed or oversized protocol records", count=malformed)
            if current:
                self._fail_pending("Claude Code stream closed")
                if not stopped and self._state not in {"offline", "error"}:
                    self._state = "error"
                    self._event("runtime.error", message="Claude Code stream closed", exitCode=process.poll())

    @staticmethod
    def _read_stderr(process: Any) -> None:
        try:
            for _ in process.stderr:
                pass
        except (OSError, ValueError):
            pass

    def _fail_pending(self, message: str) -> None:
        with self._lock:
            for pending in self._pending_controls.values():
                pending.error = message
                pending.done.set()

    def _handle_control_response(self, row: dict[str, Any]) -> None:
        response = row.get("response")
        if not isinstance(response, dict):
            return
        request_id = response.get("request_id")
        with self._lock:
            pending = self._pending_controls.get(request_id) if isinstance(request_id, str) else None
        if pending is None:
            return
        if response.get("subtype") == "success":
            value = response.get("response")
            pending.response = dict(value) if isinstance(value, dict) else {}
            for key in ("pending_permission_requests", "pending_user_dialog_requests"):
                if isinstance(response.get(key), list):
                    pending.response[key] = response[key]
        else:
            pending.error = self._bounded_text(response.get("error"), 1000) or "Claude Code rejected a control request"
        pending.done.set()

    def _handle_control_request(self, row: dict[str, Any], *, recovered: bool = False) -> None:
        request_id, request = row.get("request_id"), row.get("request")
        if not isinstance(request_id, str) or not isinstance(request, dict):
            return
        subtype = request.get("subtype")
        if subtype != "can_use_tool":
            self._event("request.denied", requestId=request_id, providerMethod=subtype if isinstance(subtype, str) else "unknown")
            try:
                self._write({"type": "control_response", "response": {"subtype": "error", "request_id": request_id, "error": "Company HQ does not implement this control request"}})
            except ProviderRuntimeError:
                pass
            return
        with self._lock:
            if request_id in self._pending_permissions:
                return
            self._cancelled_permissions.discard(request_id)
            self._pending_permissions[request_id] = request
            turn_id = self._turn_ids[0] if self._turn_ids else None
            if recovered and turn_id is None and self.session_id:
                turn_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"company-hq:claude:{self.session_id}:{request_id}"))
            self._permission_turns[request_id] = (turn_id, recovered)
            item_id = self._turn_items.get(turn_id) if turn_id else None
        tool = request.get("tool_name") if isinstance(request.get("tool_name"), str) else "unknown"
        details = {
            "requestId": request_id,
            "tool": tool[:200],
            "toolInput": request.get("input") if isinstance(request.get("input"), dict) else {},
            "reason": self._bounded_text(request.get("decision_reason"), 2000),
            "requiresUserInteraction": bool(request.get("requires_user_interaction")),
            "sessionId": self.session_id,
            "turnId": turn_id,
            "itemId": item_id,
            "recovered": recovered,
        }
        self._event("question.requested" if tool == "AskUserQuestion" else "approval.requested", **details)

    def _handle(self, row: dict[str, Any]) -> None:
        session = row.get("session_id")
        if isinstance(session, str) and 1 <= len(session) <= 512:
            self.session_id = session
        type_ = row.get("type")
        if type_ == "control_response":
            self._handle_control_response(row)
            return
        if type_ == "control_request":
            self._handle_control_request(row)
            return
        if type_ == "control_cancel_request":
            request_id = row.get("request_id")
            if isinstance(request_id, str):
                with self._lock:
                    removed = self._pending_permissions.pop(request_id, None)
                    permission_turn = self._permission_turns.pop(request_id, (None, False))
                    self._cancelled_permissions.add(request_id)
                if removed is not None:
                    self._event("request.cancelled", requestId=request_id, turnId=permission_turn[0], recovered=permission_turn[1], sessionId=self.session_id)
            return
        if type_ == "system" and row.get("subtype") == "init":
            capabilities = row.get("capabilities")
            self._event(
                "session.ready", sessionId=self.session_id,
                tools=[tool[:200] for tool in row.get("tools", [])[:100] if isinstance(tool, str)] if isinstance(row.get("tools"), list) else [],
                capabilities=[cap[:200] for cap in capabilities[:100] if isinstance(cap, str)] if isinstance(capabilities, list) else [],
            )
            return
        if type_ == "assistant":
            message = row.get("message")
            with self._lock:
                turn_id = self._turn_ids[0] if self._turn_ids else None
                item_id = self._turn_items.get(turn_id) if turn_id else None
            native_item_id = message.get("id") if isinstance(message, dict) else None
            if not isinstance(native_item_id, str):
                native_item_id = row.get("uuid") if isinstance(row.get("uuid"), str) else None
            if turn_id and native_item_id:
                item_id = native_item_id
                with self._lock:
                    self._turn_items[turn_id] = item_id
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        self._event("message.delta", text=item["text"][:24_000], sessionId=self.session_id, turnId=turn_id, itemId=item_id)
                    elif item.get("type") == "tool_use":
                        name = item.get("name")
                        self._event("tool.requested", tool=name[:200] if isinstance(name, str) else "unknown", toolUseId=item.get("id") if isinstance(item.get("id"), str) else None, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
            return
        if type_ == "result":
            with self._lock:
                turn_id = self._turn_ids.popleft() if self._turn_ids else None
                item_id = self._turn_items.pop(turn_id, None) if turn_id else None
            result = row.get("result")
            failed = bool(row.get("is_error")) or row.get("subtype") not in {None, "success"}
            data: dict[str, Any] = {"sessionId": self.session_id, "turnId": turn_id, "itemId": item_id, "isError": failed}
            if isinstance(result, str):
                data["text"] = result[:24_000]
            usage = row.get("usage")
            if isinstance(usage, dict):
                data["usage"] = {key: value for key, value in usage.items() if isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool)}
            for key in ("duration_ms", "duration_api_ms", "num_turns", "total_cost_usd"):
                value = row.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    data[key] = value
            self._event("message.completed" if not failed else "runtime.error", **data)
            self._state = "error" if failed else "idle"
            return
        if type_ not in {"user", "stream_event"}:
            self._event("provider.event", kind=type_[:200] if isinstance(type_, str) else "unknown")

    def respond(self, request_id: str, response: object) -> dict[str, Any]:
        if not isinstance(request_id, str) or not request_id:
            raise ProviderRuntimeError("Claude response requires a request ID")
        with self._lock:
            request = self._pending_permissions.pop(request_id, None)
            permission_turn = self._permission_turns.pop(request_id, (None, False))
            generation = self._generation
        if request is None:
            raise ProviderRuntimeError("Claude permission request is stale or unknown")
        if not isinstance(response, dict):
            with self._lock:
                if generation == self._generation and request_id not in self._cancelled_permissions:
                    self._pending_permissions[request_id] = request
                    self._permission_turns[request_id] = permission_turn
            raise ProviderRuntimeError("Claude permission response must be an object")
        allow = response.get("allow") is True or response.get("approved") is True or response.get("decision") in {"allow", "approved", "accept"}
        tool = request.get("tool_name")
        if allow:
            updated = dict(request.get("input")) if isinstance(request.get("input"), dict) else {}
            if tool == "AskUserQuestion":
                answers = response.get("answers")
                if isinstance(answers, dict):
                    updated["answers"] = {str(key)[:500]: str(value)[:4000] for key, value in list(answers.items())[:50]}
                elif isinstance(response.get("message"), str):
                    questions = updated.get("questions")
                    key = "answer"
                    if isinstance(questions, list) and questions and isinstance(questions[0], dict) and isinstance(questions[0].get("question"), str):
                        key = questions[0]["question"]
                    updated["answers"] = {key[:500]: response["message"][:4000]}
            decision: dict[str, Any] = {"behavior": "allow", "updatedInput": updated, "decisionClassification": "user_temporary"}
        else:
            message = response.get("message") if isinstance(response.get("message"), str) else "User denied"
            decision = {"behavior": "deny", "message": message[:2000], "decisionClassification": "user_reject"}
        try:
            self._write({"type": "control_response", "response": {"subtype": "success", "request_id": request_id, "response": decision}})
        except ProviderRuntimeError:
            with self._lock:
                if generation == self._generation and request_id not in self._cancelled_permissions and request_id not in self._pending_permissions:
                    self._pending_permissions[request_id] = request
                    self._permission_turns[request_id] = permission_turn
            raise
        with self._lock:
            self._cancelled_permissions.discard(request_id)
        self._event(
            "request.resolved", requestId=request_id, allowed=allow, tool=tool,
            sessionId=self.session_id, turnId=permission_turn[0], recovered=permission_turn[1],
        )
        return {"accepted": True, "requestId": request_id, "allowed": allow}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self.process
            already_offline = self._state == "offline" and not self._running(process)
            self._stopped = True
        if already_offline:
            return {"accepted": True, "sessionId": self.session_id}
        if self._running(process):
            try:
                self._control({"subtype": "interrupt", "cancel_queued": True}, timeout=min(2.0, self.request_timeout))
            except ProviderRuntimeError:
                pass
            try:
                if getattr(process, "stdin", None):
                    process.stdin.close()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
        with self._lock:
            self._generation += 1
        for stream_name in ("stdout", "stderr"):
            stream = getattr(process, stream_name, None) if process is not None else None
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        self._fail_pending("Claude Code runtime stopped")
        with self._lock:
            self.process = None
            self._pending_permissions.clear()
            self._permission_turns.clear()
            self._cancelled_permissions.clear()
            self._state = "offline"
        self._event("runtime.stopped", sessionId=self.session_id)
        return {"accepted": True, "sessionId": self.session_id}

    def status(self) -> dict[str, Any]:
        value = super().status()
        with self._lock:
            pending = len(self._pending_permissions)
        value.update({
            "sessionId": self.session_id,
            "project": self.project,
            "transport": "claude-code-stream-json-control-v1",
            "input": "text_and_images",
            "permissions": "company_hq_control_response",
            "access": self.access,
            "workspaceScope": "cwd_with_native_permission_prompts" if self.access == "workspace" else self.access,
            "filesystemSandboxed": False,
            "models": self.models,
            "pendingRequests": pending,
            "resumable": bool(self.session_id),
        })
        return value
