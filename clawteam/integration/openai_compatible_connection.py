"""Session-only verification for a user-configured OpenAI-compatible endpoint.

The user supplies an HTTPS base URL (plain HTTP is allowed on loopback hosts
only), a model ID, an optional bearer key, a temperature and a context hint.
Nothing is persisted: the key lives in process memory and never appears in
snapshots, messages, exceptions or events. Verification prefers the ``/models``
listing and keeps that proof distinct from an explicit, quota-consuming
generation test over ``/chat/completions``.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import ipaddress
from json import JSONDecodeError
import json
from math import isfinite
import threading
from typing import Any, Callable
from urllib import error, request
from urllib.parse import urlparse

PROVIDER = "openai-compatible"
MAX_RESPONSE = 1024 * 1024
DEFAULT_CONTEXT_HINT = 32768
DEFAULT_TIMEOUT = 10.0
PROBE_MAX_TOKENS = 64


class TransportError(RuntimeError):
    """A safe, user-facing transport failure; never carries key material."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _origin(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port


def same_origin(first: str, second: str) -> bool:
    try:
        return _origin(first) == _origin(second)
    except ValueError:
        return False


def origin_display(base_url: str) -> str:
    """Scheme and host of a validated base URL; safe for status output."""
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc or parsed.hostname or ''}"


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validated_base_url(value: object) -> str:
    """Accept HTTPS anywhere, or plain HTTP on loopback hosts only."""
    if not isinstance(value, str):
        raise ValueError("Base URL must be text")
    text = value.strip()
    if not text or len(text) > 2048:
        raise ValueError("Base URL must be 1 to 2048 characters")
    if any(not 33 <= ord(char) <= 126 for char in text):
        raise ValueError("Base URL must be printable characters without spaces")
    try:
        parsed = urlparse(text)
        parsed.port
    except ValueError as exc:
        raise ValueError("Base URL has an invalid port") from exc
    if not parsed.hostname:
        raise ValueError("Base URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Base URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL must not include a query or fragment")
    if parsed.scheme == "https":
        pass
    elif parsed.scheme == "http":
        if not _loopback(parsed.hostname):
            raise ValueError("Plain HTTP base URLs are allowed only on loopback hosts")
    else:
        raise ValueError("Base URL must use https, or http on a loopback host")
    return text.rstrip("/")


def valid_bearer_key(value: object) -> str | None:
    """Return a header-safe bearer key, or None when none was supplied."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("API key must be text")
    text = value.strip()
    if not text:
        return None
    if len(text) > 4096 or any(not 33 <= ord(char) <= 126 for char in text):
        raise ValueError("API key must be 1 to 4096 printable characters without spaces")
    return text


def validated_model(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Model ID must be text")
    model = value.strip()
    if not model or len(model) > 200:
        raise ValueError("Model ID must be 1 to 200 characters")
    if any(not 33 <= ord(char) <= 126 for char in model):
        raise ValueError("Model ID must be printable characters without spaces")
    return model


def validated_temperature(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Temperature must be a finite number")
    temperature = float(value)
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("Temperature must be between 0 and 2")
    return temperature


def validated_context_hint(value: object) -> int:
    if value is None:
        return DEFAULT_CONTEXT_HINT
    if isinstance(value, bool) or not isinstance(value, int) or not 1024 <= value <= 262144:
        raise ValueError("Context hint must be an integer between 1024 and 262144")
    return value


def fetch_json(
    opener: Any,
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    on_response: Callable[[Any], None] | None = None,
    max_bytes: int = MAX_RESPONSE,
) -> Any:
    """One guarded JSON request: redirects refused, body bounded, errors safe."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    req = request.Request(url, body, request_headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as response:
            if on_response is not None:
                on_response(response)
            final = response.geturl() if hasattr(response, "geturl") else url
            if not isinstance(final, str) or not same_origin(final, url):
                raise TransportError("The endpoint redirected to another host")
            raw = response.read(max_bytes + 1)
    except error.HTTPError as exc:
        try:
            exc.close()
        except Exception:
            pass
        if 300 <= exc.code < 400:
            raise TransportError("The endpoint attempted a redirect; refusing to follow it") from exc
        raise TransportError(f"The endpoint returned HTTP {exc.code}", exc.code) from exc
    except (error.URLError, OSError) as exc:
        raise TransportError("The endpoint request failed") from exc
    if len(raw) > max_bytes:
        raise TransportError("The endpoint response was too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise TransportError("The endpoint returned invalid JSON") from exc


def _first_choice(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    choices = value.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    return first if isinstance(first, dict) else None


def assistant_text(value: Any) -> str | None:
    """First assistant text of a chat completion, or None when absent."""
    choice = _first_choice(value)
    if choice is None:
        return None
    message = choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) and content.strip() else None


def returned_tool_calls(value: Any) -> bool:
    choice = _first_choice(value)
    message = choice.get("message") if choice else None
    return isinstance(message, dict) and isinstance(message.get("tool_calls"), list) and bool(message["tool_calls"])


def finish_reason(value: Any) -> str | None:
    choice = _first_choice(value)
    reason = choice.get("finish_reason") if choice else None
    return reason if isinstance(reason, str) and reason and len(reason) <= 100 else None


def chat_usage(value: Any) -> dict[str, int] | None:
    """Native usage counts when the endpoint reported them."""
    usage = value.get("usage") if isinstance(value, dict) else None
    if not isinstance(usage, dict):
        return None
    result = {
        key: usage[key]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool) and usage[key] >= 0
    }
    return result or None


def _parse_models(value: Any) -> list[dict[str, str]]:
    rows = value.get("data") if isinstance(value, dict) else value
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    if not isinstance(rows, list):
        return result
    for row in rows[:100]:
        identifier = row.get("id") if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 200:
            continue
        if any(not 33 <= ord(char) <= 126 for char in identifier) or identifier in seen:
            continue
        seen.add(identifier)
        item = {"value": identifier}
        for source, target in (("object", "object"), ("owned_by", "ownedBy")):
            if isinstance(row.get(source), str):
                item[target] = row[source][:200]
        result.append(item)
    return result


class OpenAICompatibleConnection:
    """Never writes or exposes the bearer key; state lasts only this process.

    There is no environment fallback for the key: an ambient OPENAI_API_KEY
    must never be attached automatically to an arbitrary user-configured host.
    """

    def __init__(self, *, opener: Any | None = None, timeout: float = DEFAULT_TIMEOUT):
        self._opener = opener or request.build_opener(_NoRedirect())
        self._timeout = timeout
        self._lock = threading.RLock()
        self._generation = 0
        self._config: dict[str, Any] | None = None
        self._value: dict[str, Any] = {
            "provider": PROVIDER,
            "authentication": "not_checked",
            "signed_in": False,
            "models": [],
            "modelDetails": [],
            "verification": None,
            "runtimeReady": False,
            "message": "Enter an OpenAI-compatible base URL and model ID to connect.",
        }

    @staticmethod
    def _headers(key: str | None) -> dict[str, str]:
        return {"Authorization": "Bearer " + key} if key else {}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._value)

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _update(self, *, config: dict[str, Any] | None, generation: int, **fields: Any) -> dict[str, Any]:
        with self._lock:
            if generation != self._generation:
                return self.snapshot()
            self._config = copy.deepcopy(config) if config else None
            self._value.update(fields, checkedAt=self._checked_at())
            return self.snapshot()

    def connect(self, *, base_url: str, model: str, api_key: str | None = None, temperature: float | None = None, context_hint: int | None = None) -> dict[str, Any]:
        """Validate the configuration locally, then verify via ``/models``."""
        config = {
            "base_url": validated_base_url(base_url),
            "model": validated_model(model),
            "key": valid_bearer_key(api_key),
            "temperature": validated_temperature(temperature),
            "context_hint": validated_context_hint(context_hint),
        }
        with self._lock:
            self._generation += 1
            generation = self._generation
        return self._verify_listing(config, generation, None)

    def check(self) -> dict[str, Any]:
        """Re-run the listing verification for the stored configuration."""
        with self._lock:
            config = copy.deepcopy(self._config) if self._config else None
            previous = self._value.get("verification")
            if config is None:
                return self.snapshot()
            self._generation += 1
            generation = self._generation
        return self._verify_listing(config, generation, previous)

    def _verify_listing(self, config: dict[str, Any], generation: int, previous: Any) -> dict[str, Any]:
        try:
            listing = fetch_json(self._opener, config["base_url"] + "/models", headers=self._headers(config["key"]), timeout=self._timeout)
        except TransportError as exc:
            status = getattr(exc, "status", None)
            if status in (401, 403):
                message = "The endpoint rejected the API key." if config["key"] else "The endpoint requires an API key."
                return self._update(config=None, generation=generation, authentication="sign_in_required", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message=message)
            if status in (404, 405):
                # Listing is optional across OpenAI-compatible deployments; the
                # endpoint stays configured but unverified until a generation test.
                return self._update(config=config, generation=generation, authentication="not_checked", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message="The endpoint does not support model listing; run an explicit generation test to verify it.")
            return self._update(config=None, generation=generation, authentication="connection_failed", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message=str(exc))
        models = _parse_models(listing)
        if config['model'] not in {item['value'] for item in models}:
            return self._update(config=config, generation=generation, authentication="model_unavailable", signed_in=False,
                models=[item['value'] for item in models], modelDetails=models, verification=None, runtimeReady=False,
                message="The endpoint did not list the chosen model. Choose a listed model or run an explicit generation test.")
        verification = "generation" if previous == "generation" else "model_listing"
        return self._update(
            config=config,
            generation=generation,
            authentication="signed_in",
            signed_in=True,
            models=[item["value"] for item in models],
            modelDetails=models,
            verification=verification,
            runtimeReady=True,
            message=self._listing_message(config["key"], models),
        )

    @staticmethod
    def _listing_message(key: str | None, models: list[dict[str, str]]) -> str:
        count = len(models)
        noun = "model" if count == 1 else "models"
        with_key = "with the API key" if key else "without a key"
        return f"The endpoint is reachable and listed {count} {noun} {with_key}. A listing is not generation proof; run an explicit generation test for actual proof."

    def test_generation(self) -> dict[str, Any]:
        """Run one minimal chat completion against the configured model.

        This consumes endpoint quota, so it stays a separate, explicitly
        requested action; a model listing is never claimed as generation proof.
        """
        with self._lock:
            config = copy.deepcopy(self._config) if self._config else None
            if config is None:
                return self.snapshot()
            previous_details = copy.deepcopy(self._value.get('modelDetails') or [])
            self._generation += 1
            generation = self._generation
        payload = {"model": config["model"], "messages": [{"role": "user", "content": "Reply with the single word: ok"}], "max_tokens": PROBE_MAX_TOKENS}
        try:
            result = fetch_json(self._opener, config["base_url"] + "/chat/completions", method="POST", headers=self._headers(config["key"]), payload=payload, timeout=self._timeout)
            text = assistant_text(result)
        except TransportError as exc:
            status = getattr(exc, "status", None)
            if status in (401, 403):
                message = "The endpoint rejected the API key." if config["key"] else "The endpoint requires an API key."
                return self._update(config=None, generation=generation, authentication="sign_in_required", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message=message)
            return self._update(config=None, generation=generation, authentication="connection_failed", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message=str(exc))
        if text is None:
            return self._update(config=config, generation=generation, authentication="connection_failed", signed_in=False, verification=None, runtimeReady=True, message="The endpoint responded but returned no assistant text; generation is not verified.")
        details = previous_details
        if config['model'] not in {item.get('value') for item in details if isinstance(item, dict)}:
            details = [*details, {'value': config['model']}]
        return self._update(config=config, generation=generation, authentication="signed_in", signed_in=True,
            models=[item['value'] for item in details], modelDetails=details, verification="generation",
            runtimeReady=True, message="The endpoint generated text with the configured model.")

    def cancel(self) -> dict[str, Any]:
        return self.close()

    def close(self) -> dict[str, Any]:
        with self._lock:
            self._generation += 1
            self._config = None
            self._value.update(authentication="not_checked", signed_in=False, models=[], modelDetails=[], verification=None, runtimeReady=False, message="Connection closed.")
        return self.snapshot()

    def key_for_runtime(self) -> str | None:
        with self._lock:
            return self._config.get("key") if self._config and self._value.get('signed_in') else None

    def config_for_runtime(self) -> dict[str, Any] | None:
        """Full endpoint configuration for a runtime; None when unconfigured."""
        with self._lock:
            return copy.deepcopy(self._config) if self._config and self._value.get('signed_in') else None


_connection = OpenAICompatibleConnection()


def connection() -> OpenAICompatibleConnection:
    return _connection
