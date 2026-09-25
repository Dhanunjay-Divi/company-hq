"""Session-only DeepSeek API-key verification and catalog discovery."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import threading
from typing import Any, Callable
from urllib import error, request

from claude_runtime import claude_binary

API = "https://api.deepseek.com"
MAX_RESPONSE = 1024 * 1024


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _valid_key(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    # HTTP header values must be printable ASCII without whitespace.
    if any(not 33 <= ord(char) <= 126 for char in value):
        return None
    return value


class DeepSeekConnection:
    """Never writes or exposes a DeepSeek key; state lasts only this process."""
    def __init__(self, *, opener: Any | None = None, timeout: float = 10.0, binary: Callable[[], str | None] = claude_binary):
        self._opener = opener or request.build_opener(_NoRedirect())
        self._timeout, self._binary = timeout, binary
        self._key: str | None = None
        self._lock = threading.RLock()
        self._generation = 0
        self._value: dict[str, Any] = {"provider": "deepseek", "authentication": "not_checked", "signed_in": False, "models": [], "modelDetails": [], "balances": [], "runtimeReady": bool(binary()), "message": "Enter a DeepSeek API key to connect."}

    def _get(self, path: str, key: str) -> Any:
        req = request.Request(API + path, headers={"Authorization": "Bearer " + key, "Accept": "application/json"}, method="GET")
        try:
            with self._opener.open(req, timeout=self._timeout) as response:
                if getattr(response, "geturl", lambda: API + path)() != API + path:
                    raise ValueError("redirect")
                body = response.read(MAX_RESPONSE + 1)
        except (error.HTTPError, error.URLError, OSError, ValueError) as exc:
            raise RuntimeError("DeepSeek request failed") from exc
        if len(body) > MAX_RESPONSE:
            raise RuntimeError("DeepSeek response was too large")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("DeepSeek returned invalid JSON") from exc

    @staticmethod
    def _models(value: Any) -> list[dict[str, str]]:
        rows = value.get("data") if isinstance(value, dict) else None
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        if isinstance(rows, list):
            for row in rows[:100]:
                identifier = row.get("id") if isinstance(row, dict) else None
                if isinstance(identifier, str) and 0 < len(identifier) <= 200 and not any(not 33 <= ord(char) <= 126 for char in identifier) and identifier not in seen:
                    seen.add(identifier)
                    item = {"value": identifier}
                    for source, target in (("object", "object"), ("owned_by", "ownedBy")):
                        if isinstance(row.get(source), str): item[target] = row[source][:200]
                    result.append(item)
        return result

    @staticmethod
    def _balances(value: Any) -> list[dict[str, Any]]:
        rows = value.get("balance_infos") if isinstance(value, dict) else None
        result: list[dict[str, Any]] = []
        if isinstance(rows, list):
            for row in rows[:100]:
                if isinstance(row, dict) and row.get("currency") in {"USD", "CNY"}:
                    item = {"currency": row["currency"]}
                    for key in ("total_balance", "granted_balance", "topped_up_balance"):
                        amount = row.get(key)
                        if isinstance(amount, str):
                            try:
                                decimal = Decimal(amount)
                            except InvalidOperation:
                                continue
                            if decimal.is_finite() and decimal >= 0:
                                item[key] = amount
                    result.append(item)
        return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._value)

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    def connect(self, api_key: str | None = None) -> dict[str, Any]:
        key = _valid_key(api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY"))
        with self._lock:
            self._generation += 1
            generation = self._generation
        return self._verify(key, generation)

    def _verify(self, key: str | None, generation: int) -> dict[str, Any]:
        if not key:
            with self._lock:
                if generation != self._generation: return self.snapshot()
                self._key = None; self._value.update(authentication="sign_in_required", signed_in=False, models=[], modelDetails=[], balances=[], checkedAt=self._checked_at(), message="A valid DeepSeek API key is required.")
            return self.snapshot()
        try:
            models = self._models(self._get("/models", key))
            if not models: raise RuntimeError("DeepSeek returned no usable models")
        except RuntimeError:
            with self._lock:
                if generation != self._generation: return self.snapshot()
                self._key = None; self._value.update(authentication="sign_in_required", signed_in=False, models=[], modelDetails=[], balances=[], checkedAt=self._checked_at(), message="DeepSeek could not verify that API key.")
            return self.snapshot()
        balances: list[dict[str, Any]] = []
        try: balances = self._balances(self._get("/user/balance", key))
        except RuntimeError: pass  # Catalog authentication is sufficient; balance is optional.
        with self._lock:
            if generation != self._generation: return self.snapshot()
            self._key = key
            self._value.update(authentication="signed_in", signed_in=True, models=[item["value"] for item in models], modelDetails=models, balances=balances, runtimeReady=bool(self._binary()), checkedAt=self._checked_at(), message="DeepSeek API key is verified.")
        return self.snapshot()

    def check(self) -> dict[str, Any]:
        with self._lock:
            key = self._key
            if key is None: return self.snapshot()
            self._generation += 1
            generation = self._generation
        return self._verify(key, generation)

    def cancel(self) -> dict[str, Any]:
        return self.close()

    def close(self) -> dict[str, Any]:
        with self._lock:
            self._generation += 1
            self._key = None; self._value.update(authentication="not_checked", signed_in=False, models=[], modelDetails=[], balances=[], message="DeepSeek connection closed.")
        return self.snapshot()

    def key_for_runtime(self) -> str | None:
        with self._lock: return self._key if self._value.get("signed_in") else None

    def catalog_for_runtime(self) -> list[dict[str, str]]:
        with self._lock: return [dict(item) for item in self._value.get("modelDetails", [])]


_connection = DeepSeekConnection()
def connection() -> DeepSeekConnection: return _connection
