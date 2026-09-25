"""Small, provider-fact-only routing policy for Company HQ.

The caller owns connection refreshes, safe chat checkpoints, and execution.  This
module only validates saved routing choices and explains a single next choice.
It intentionally does not infer model quality, pricing, access, or quotas.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time
import uuid
from typing import Any, Callable


class RoutingPolicyError(ValueError):
    """The supplied routing configuration or provider facts are invalid."""


class RoutingPolicy:
    """Persist allowlisted choices and account-scoped quota cooldowns.

    ``catalog`` entries passed to :meth:`decide` must be current provider facts:
    ``provider``, ``model``, ``accountId``, plus ``verified``, ``authenticated``
    and ``available`` booleans.  ``usageWindows`` is displayed unchanged except
    for a minimal safe shape check; it is never synthesized from local tokens.
    """

    VERSION = 1

    def __init__(self, state_path: str | Path, *, now: Callable[[], float] = time.time) -> None:
        supplied = Path(state_path).expanduser()
        if supplied.exists() and supplied.is_symlink():
            raise RoutingPolicyError("routing policy state must not be a symlink")
        self.path = supplied.resolve()
        self._now = now
        self._state = self._read()

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": RoutingPolicy.VERSION,
            "config": {"autoFallback": True, "models": []},
            "reportedUsage": {},
            "accountBlocks": {},
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_size > 131_072:
            raise RoutingPolicyError("routing policy state must be a small regular file")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RoutingPolicyError("routing policy state is unreadable") from exc
        if not isinstance(raw, dict) or raw.get("version") != self.VERSION:
            raise RoutingPolicyError("routing policy state has an unsupported schema")
        # Re-validate persisted config to fail closed if the file was edited.
        config = self._validate_config(raw.get("config"))
        usage = raw.get("reportedUsage", {})
        blocks = raw.get("accountBlocks", {})
        if not isinstance(usage, dict) or not isinstance(blocks, dict):
            raise RoutingPolicyError("routing policy state has invalid runtime data")
        return {"version": self.VERSION, "config": config, "reportedUsage": usage, "accountBlocks": blocks}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(self._state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)

    @staticmethod
    def _identity(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise RoutingPolicyError(f"{label} must be a non-empty short string")
        return value.strip()

    @classmethod
    def _model(cls, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise RoutingPolicyError("each enrolled model must be an object")
        provider = cls._identity(raw.get("provider"), "provider")
        model = cls._identity(raw.get("model"), "model")
        enabled = raw.get("enabled", True)
        share = raw.get("sharePercent", 100)
        if not isinstance(enabled, bool) or isinstance(share, bool) or not isinstance(share, (int, float)) or not math.isfinite(share) or not 0 <= share <= 100:
            raise RoutingPolicyError("model enabled must be boolean and sharePercent must be 0 through 100")
        return {"provider": provider, "model": model, "enabled": enabled, "sharePercent": share}

    @classmethod
    def _validate_config(cls, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise RoutingPolicyError("routing config must be an object")
        auto = raw.get("autoFallback", True)
        if not isinstance(auto, bool):
            raise RoutingPolicyError("autoFallback must be boolean")
        models = raw.get("models", [])
        if not isinstance(models, list) or len(models) > 100:
            raise RoutingPolicyError("models must be a list of at most 100 enrolled models")
        normalized = [cls._model(item) for item in models]
        identities = [(item["provider"], item["model"]) for item in normalized]
        if len(set(identities)) != len(identities):
            raise RoutingPolicyError("models must not contain duplicate provider/model entries")
        result: dict[str, Any] = {"autoFallback": auto, "models": normalized}
        preferred = raw.get("preferredSupervisor")
        if preferred is not None:
            if not isinstance(preferred, dict):
                raise RoutingPolicyError("preferredSupervisor must identify an enrolled model")
            identity = (cls._identity(preferred.get("provider"), "provider"), cls._identity(preferred.get("model"), "model"))
            if identity not in identities:
                raise RoutingPolicyError("preferredSupervisor must be enrolled")
            result["preferredSupervisor"] = {"provider": identity[0], "model": identity[1]}
        pool = raw.get("tokenPool")
        if pool is not None:
            if not isinstance(pool, dict):
                raise RoutingPolicyError("tokenPool must be an object")
            limit = pool.get("limitTokens")
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
                raise RoutingPolicyError("tokenPool.limitTokens must be a positive integer")
            result["tokenPool"] = {"limitTokens": limit}
        return result

    def get_settings(self) -> dict[str, Any]:
        """Return configured policy plus local reported-token enforcement facts."""
        return {**self._state["config"], "reportedUsage": dict(self._state["reportedUsage"])}

    def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        self._state["config"] = self._validate_config(settings)
        self._save()
        return self.get_settings()

    @staticmethod
    def _key(provider: str, account: str) -> str:
        return f"{provider}\x1f{account}"

    @staticmethod
    def _model_key(provider: str, model: str) -> str:
        return f"{provider}\x1f{model}"

    def record_reported_usage(self, provider: str, model: str, total_tokens: int) -> None:
        """Store a cumulative native-provider token report for configured pool limits."""
        provider = self._identity(provider, "provider")
        model = self._identity(model, "model")
        if isinstance(total_tokens, bool) or not isinstance(total_tokens, int) or total_tokens < 0:
            raise RoutingPolicyError("total_tokens must be a non-negative integer")
        key = self._model_key(provider, model)
        self._state["reportedUsage"][key] = max(total_tokens, int(self._state["reportedUsage"].get(key, 0)))
        self._save()

    def record_quota_exhausted(self, provider: str, account_id: str, reset_at: float | int | None) -> None:
        """Block every model on an account; an unknown reset stays blocked until refresh."""
        provider = self._identity(provider, "provider")
        account_id = self._identity(account_id, "accountId")
        if reset_at is not None and (isinstance(reset_at, bool) or not isinstance(reset_at, (int, float)) or not math.isfinite(reset_at) or reset_at <= self._now()):
            reset_at = None
        self._state["accountBlocks"][self._key(provider, account_id)] = {"blockedUntil": reset_at}
        self._save()

    def refresh_account(self, provider: str, account_id: str) -> None:
        """Clear an unknown-reset block only after the caller has refreshed provider facts."""
        self._state["accountBlocks"].pop(self._key(self._identity(provider, "provider"), self._identity(account_id, "accountId")), None)
        self._save()

    def _pool_reason(self, model: dict[str, Any]) -> str | None:
        pool = self._state["config"].get("tokenPool")
        if not pool:
            return None
        used = sum(value for value in self._state["reportedUsage"].values() if isinstance(value, int) and not isinstance(value, bool) and value >= 0)
        limit = pool["limitTokens"]
        if used >= limit:
            return "reported token pool is exhausted"
        share = model["sharePercent"]
        allotted = limit * share / 100
        own = self._state["reportedUsage"].get(self._model_key(model["provider"], model["model"]), 0)
        if own >= allotted:
            return "model reported-token share is exhausted"
        return None

    def global_pool_reason(self) -> str | None:
        """Return only the global reported-token gate for an explicit model."""
        pool = self._state["config"].get("tokenPool")
        if not pool:
            return None
        used = sum(value for value in self._state["reportedUsage"].values() if isinstance(value, int) and not isinstance(value, bool) and value >= 0)
        return "reported token pool is exhausted" if used >= pool["limitTokens"] else None

    @staticmethod
    def _quota_exhausted(entry: dict[str, Any]) -> bool:
        windows = entry.get("usageWindows", [])
        if not isinstance(windows, list):
            return False
        return any(
            isinstance(item, dict)
            and isinstance(item.get("usedPercent"), (int, float))
            and not isinstance(item.get("usedPercent"), bool)
            and math.isfinite(item["usedPercent"])
            and item["usedPercent"] >= 100
            for item in windows
        )

    def decide(self, catalog: list[dict[str, Any]], *, role: str = "worker") -> dict[str, Any]:
        """Choose one enrolled candidate from supplied facts, or explain why none is safe.

        A returned fallback has ``requiresSafeHandoff`` because this policy never
        retries execution or transfers conversation/tool state itself.
        """
        if role not in {"worker", "supervisor"}:
            raise RoutingPolicyError("role must be worker or supervisor")
        if not isinstance(catalog, list):
            raise RoutingPolicyError("catalog must be a list")
        facts = {}
        for item in catalog:
            if not isinstance(item, dict):
                continue
            provider, model = item.get("provider"), item.get("model")
            if isinstance(provider, str) and isinstance(model, str):
                facts[(provider, model)] = item
        config = self._state["config"]
        ordered = list(config["models"])
        preferred = config.get("preferredSupervisor") if role == "supervisor" else None
        if preferred:
            preferred_id = (preferred["provider"], preferred["model"])
            ordered.sort(key=lambda item: (item["provider"], item["model"]) != preferred_id)
        rejected: list[dict[str, str]] = []
        selected: dict[str, Any] | None = None
        for enrolled in ordered:
            identity = (enrolled["provider"], enrolled["model"])
            fact = facts.get(identity)
            if not enrolled["enabled"] or enrolled["sharePercent"] == 0:
                rejected.append({"provider": identity[0], "model": identity[1], "reason": "not enabled for routing"}); continue
            if not fact or not all(fact.get(key) is True for key in ("verified", "authenticated", "available")):
                rejected.append({"provider": identity[0], "model": identity[1], "reason": "not currently verified, authenticated, and available"}); continue
            account = fact.get("accountId")
            if not isinstance(account, str) or not account:
                rejected.append({"provider": identity[0], "model": identity[1], "reason": "missing provider account identity"}); continue
            block = self._state["accountBlocks"].get(self._key(identity[0], account))
            if isinstance(block, dict):
                until = block.get("blockedUntil")
                if isinstance(until, (int, float)) and not isinstance(until, bool) and until > self._now():
                    rejected.append({"provider": identity[0], "model": identity[1], "reason": "account quota cooldown is active"}); continue
                # An elapsed provider reset is not proof that this account has
                # refreshed.  Keep the durable block until RoutingService's
                # fresh signed-in allowance check calls refresh_account().
                rejected.append({"provider": identity[0], "model": identity[1], "reason": "account quota requires provider refresh"}); continue
            if self._quota_exhausted(fact):
                resets = [
                    item.get("resetsAt") for item in fact.get("usageWindows", [])
                    if isinstance(item, dict)
                    and isinstance(item.get("usedPercent"), (int, float))
                    and not isinstance(item.get("usedPercent"), bool)
                    and math.isfinite(item["usedPercent"])
                    and item["usedPercent"] >= 100
                ]
                future = [value for value in resets if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > self._now()]
                if future:
                    self.record_quota_exhausted(identity[0], account, max(future))
                    reason = "provider reports account quota exhausted"
                else:
                    # A reported exhausted window whose reset has passed may be
                    # stale.  Do not create another indefinite cooldown, but
                    # remain fail-closed until current provider facts arrive.
                    reason = "provider quota status needs refresh after its reported reset"
                rejected.append({"provider": identity[0], "model": identity[1], "reason": reason}); continue
            reason = self._pool_reason(enrolled)
            if reason:
                rejected.append({"provider": identity[0], "model": identity[1], "reason": reason}); continue
            selected = {"provider": identity[0], "model": identity[1], "accountId": account, "usageWindows": fact.get("usageWindows", [])}
            break
        if selected is None:
            return {"candidate": None, "reason": "no enrolled model is currently eligible", "rejected": rejected, "requiresSafeHandoff": False}
        fallback = bool(rejected)
        if fallback and not config["autoFallback"]:
            return {"candidate": None, "reason": "preferred route is unavailable and automatic fallback is disabled", "rejected": rejected, "requiresSafeHandoff": False}
        return {"candidate": selected, "reason": "eligible enrolled model selected" if not fallback else "eligible approved fallback selected", "rejected": rejected, "fallback": fallback, "requiresSafeHandoff": fallback}
