"""DeepSeek's documented Claude Code compatibility transport."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import threading
from typing import Any

from claude_runtime import ClaudeCodeRuntime
from provider_runtime import ProviderRuntimeError
from runtime_config import state_root
from deepseek_connection import connection, DeepSeekConnection


class DeepSeekRuntime(ClaudeCodeRuntime):
    provider = "deepseek"
    def __init__(self, *args: Any, connection_: DeepSeekConnection | None = None, **kwargs: Any) -> None:
        self.connection = connection_ or connection()
        self._bound_key: str | None = None
        self._bound_catalog: list[dict[str, str]] = []
        self._bound_model: str | None = None
        super().__init__(*args, **kwargs)

    def _catalog(self) -> list[dict[str, str]]:
        catalog = self.connection.catalog_for_runtime()
        if not self.connection.key_for_runtime() or not catalog:
            raise ProviderRuntimeError("Connect and verify a DeepSeek API key before starting")
        return catalog

    def _select(self, model: str | None) -> str:
        chosen = model or self.model
        values = {item["value"] for item in self._catalog()}
        if not isinstance(chosen, str) or chosen not in values:
            raise ProviderRuntimeError("Select a model reported by DeepSeek")
        return chosen

    def _args(self, *, resume: bool) -> list[str]:
        # Bind this transport to its explicit API route and reviewed MCP set.
        # User/project Claude settings can otherwise override the process env.
        return [*super()._args(resume=resume), "--setting-sources", "", "--strict-mcp-config"]

    def _launch(self, *, resume: bool) -> None:
        assert self.project
        key, selected = self._bound_key, self._bound_model
        if not key: raise ProviderRuntimeError("Connect and verify a DeepSeek API key before starting")
        if not selected: raise ProviderRuntimeError("Select a model reported by DeepSeek")
        config = state_root() / "providers" / "deepseek" / "claude-config"
        config.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = config.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ProviderRuntimeError("DeepSeek Claude profile must be a private directory")
        # Keep native homes and OS execution settings, not unrelated API secrets.
        inherited = {"HOME", "CODEX_HOME", "PATH", "USER", "LOGNAME", "SHELL", "TMPDIR", "TMP", "TEMP", "LANG", "TERM", "COLORTERM", "SSH_AUTH_SOCK", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "COMPANY_HQ_STATE_ROOT", "CLAWTEAM_DATA_DIR", "CLAWTEAM_TRANSPORT"}
        env = {k: v for k, v in os.environ.items() if k in inherited or k.startswith("LC_")}
        env.update({"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": key, "CLAUDE_CONFIG_DIR": str(config), "ANTHROPIC_MODEL": selected, "ANTHROPIC_DEFAULT_OPUS_MODEL": selected, "ANTHROPIC_DEFAULT_SONNET_MODEL": selected, "ANTHROPIC_DEFAULT_HAIKU_MODEL": selected, "CLAUDE_CODE_SUBAGENT_MODEL": selected})
        try:
            process = self._factory(self._args(resume=resume), cwd=self.project, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        except OSError as exc:
            self._state = "error"; self._event("runtime.error", message="DeepSeek Claude Code could not start")
            raise ProviderRuntimeError("DeepSeek Claude Code could not start") from exc
        if not getattr(process, "stdin", None) or not getattr(process, "stdout", None):
            self._state = "error"
            try: process.terminate()
            except (AttributeError, OSError): pass
            raise ProviderRuntimeError("DeepSeek Claude Code did not expose JSONL streams")
        with self._lock:
            self.process = process; self._generation += 1; generation = self._generation; self._stopped = False
        self._reader = threading.Thread(target=self._read_stdout, args=(process, generation), daemon=True, name="company-hq-deepseek-stdout"); self._reader.start()
        if getattr(process, "stderr", None): self._stderr_reader = threading.Thread(target=self._read_stderr, args=(process,), daemon=True, name="company-hq-deepseek-stderr"); self._stderr_reader.start()

    def initialize(self, *, project: str | Path, model: str | None = None) -> dict[str, Any]:
        if self.session_id and not self._running() and self._bound_key is None:
            raise ProviderRuntimeError("Start a new DeepSeek chat after reconnecting credentials; the original session key is no longer available")
        if self._running():
            if model is not None and model != self._bound_model:
                raise ProviderRuntimeError("Start a new DeepSeek chat to change models")
            result = super().initialize(project=project, model=self._bound_model)
            self.models = [dict(item) for item in self._bound_catalog]
            return {**result, "models": self.list_models()}
        chosen = self._select(model)
        if not self._running():
            if self._bound_key is not None and self.connection.key_for_runtime() != self._bound_key:
                raise ProviderRuntimeError("Start a new DeepSeek chat to change credentials")
            self._bound_key = self.connection.key_for_runtime()
            self._bound_catalog = self.connection.catalog_for_runtime()
            self._bound_model = chosen
        try:
            result = super().initialize(project=project, model=chosen)
        except Exception:
            if not self._running(): self._bound_key = self._bound_model = None; self._bound_catalog = []
            raise
        self.models = [dict(item) for item in self._bound_catalog]
        return {**result, "models": self.list_models()}

    def send(self, prompt: str, *, images: list[Any] | None = None, model: str | None = None, **kwargs: Any) -> dict[str, Any]:
        if model is not None:
            if not self.project: raise ProviderRuntimeError("DeepSeek runtime is not started")
            self.initialize(project=self.project, model=model)
        return super().send(prompt, images=images, **kwargs)

    def _event(self, type_: str, **data: Any):
        key = getattr(self, "_bound_key", None)
        if key:
            def redact(value: Any) -> Any:
                if isinstance(value, str): return value.replace(key, "[redacted]")
                if isinstance(value, list): return [redact(item) for item in value]
                if isinstance(value, dict): return {name: redact(item) for name, item in value.items()}
                return value
            data = redact(data)
        return super()._event(type_, **data)

    def status(self) -> dict[str, Any]:
        value = super().status(); value["provider"] = "deepseek"; value["transport"] = "deepseek-claude-code-stream-json-control-v1"; return value


def runtime(**kwargs: Any) -> DeepSeekRuntime:
    return DeepSeekRuntime(**kwargs)
