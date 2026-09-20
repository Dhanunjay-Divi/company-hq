"""Deterministic, token-free model routing for Company HQ.

The router never asks a model which model to use. It intersects the reviewed
policy with the native provider catalog and chooses the smallest reviewed tier
whose capability band fits the request. Flagship use is explicit/escalation
only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from runtime_config import REPO_ROOT, routing_path

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from discover import discover  # noqa: E402


SIMPLE_HINTS = (
    "typo", "rename", "format", "comment", "documentation", "docs", "readme",
    "small css", "copy change", "one line", "simple test", "find where",
)
COMPLEX_HINTS = (
    "architecture", "distributed", "concurrency", "race condition", "security",
    "authentication", "authorization", "migration", "schema change", "data loss",
    "large refactor", "cross service", "production incident", "unknown failure",
    "payments", "billing", "cryptography", "permission", "multi-agent",
)
VERY_COMPLEX_HINTS = (
    "security critical", "data migration", "distributed transaction",
    "large-scale refactor", "cross-repository", "cross repository",
)


class RoutingError(RuntimeError):
    """No safe reviewed route can be selected."""


def _policy() -> dict[str, Any]:
    return json.loads(routing_path().read_text(encoding="utf-8"))


def reviewed_catalog() -> dict[str, Any]:
    """Return current reviewed Codex models without spending model tokens."""
    policy = _policy()
    try:
        capabilities = discover(refresh=False)
    except Exception as exc:
        return {
            "verified": False,
            "models": [],
            "reason": f"native model catalog unavailable: {str(exc)[:240]}",
        }
    provider = capabilities.get("providers", {}).get("codex", {})
    if provider.get("status") != "catalog_verified":
        return {
            "verified": False,
            "models": [],
            "reason": provider.get("error") or "native Codex model catalog is not verified",
        }
    reviewed = set(policy.get("reviewed_codex_models", []))
    rows = provider.get("models", [])
    available = []
    for row in rows:
        model = row.get("model") or row.get("id")
        if model in reviewed:
            available.append({
                "model": model,
                "displayName": row.get("displayName"),
                "defaultReasoningEffort": row.get("defaultReasoningEffort"),
                "supportedReasoningEfforts": row.get("supportedReasoningEfforts") or [],
            })
    return {"verified": True, "models": available, "reason": None}


def complexity_score(prompt: str, mode: str = "execute") -> tuple[int, list[str]]:
    """Cheap lexical estimate; deliberately conservative and explainable."""
    text = prompt.lower()
    score = 1 if mode == "execute" else 0
    reasons: list[str] = []

    length = len(prompt)
    if length > 6_000:
        score += 2
        reasons.append("large request")
    elif length > 2_000:
        score += 1
        reasons.append("multi-part request")

    complex_hits = [hint for hint in COMPLEX_HINTS if hint in text]
    if complex_hits:
        score += min(3, len(complex_hits))
        reasons.append("complex domain: " + ", ".join(complex_hits[:3]))

    very_hits = [hint for hint in VERY_COMPLEX_HINTS if hint in text]
    if very_hits:
        score += 2
        reasons.append("high-risk scope: " + ", ".join(very_hits[:2]))

    if re.search(r"\b(failed|retry|second attempt|still failing|regression)\b", text):
        score += 1
        reasons.append("prior failure/regression")

    simple_hits = [hint for hint in SIMPLE_HINTS if hint in text]
    if simple_hits and not complex_hits and length < 1_500:
        score = max(0, score - 1)
        reasons.append("bounded/simple change")

    return min(score, 8), reasons or ["normal bounded engineering request"]


def _tier_for(score: int) -> str:
    if score <= 1:
        return "small"
    if score <= 4:
        return "standard"
    return "complex"


def _candidate_order(policy: dict[str, Any], tier: str) -> list[str]:
    economy = policy.get("economy", {})
    tiers = economy.get("tiers", {})
    configured = tiers.get(tier, [])
    reviewed = policy.get("reviewed_codex_models", [])
    # Escalate upward; never silently downgrade a complex task below its tier.
    if tier == "small":
        fallback_tiers = ("small", "standard", "complex")
    elif tier == "standard":
        fallback_tiers = ("standard", "complex")
    else:
        fallback_tiers = ("complex",)
    ordered: list[str] = []
    for name in fallback_tiers:
        for model in tiers.get(name, []):
            if model in reviewed and model not in ordered:
                ordered.append(model)
    for model in configured:
        if model in reviewed and model not in ordered:
            ordered.append(model)
    return ordered


def _choose_effort(row: dict[str, Any], tier: str) -> str | None:
    supported_raw = row.get("supportedReasoningEfforts") or []
    supported = [
        item.get("reasoningEffort") if isinstance(item, dict) else item
        for item in supported_raw
    ]
    supported = [item for item in supported if isinstance(item, str) and item]
    default = row.get("defaultReasoningEffort")
    desired = {"small": "low", "standard": "medium", "complex": "high"}.get(tier)
    if desired in supported:
        return desired
    if isinstance(default, str) and (not supported or default in supported):
        return default
    order = ["low", "medium", "high", "xhigh"]
    ranked = [item for item in order if item in supported]
    if ranked:
        if tier == "complex":
            return ranked[-1]
        if tier == "small":
            return ranked[0]
        return ranked[min(1, len(ranked) - 1)]
    return supported[0] if supported else None


def choose_model(prompt: str, mode: str = "execute", requested: str = "auto") -> dict[str, Any]:
    policy = _policy()
    reviewed = set(policy.get("reviewed_codex_models", []))
    catalog = reviewed_catalog()

    if requested != "auto":
        if requested not in reviewed:
            raise RoutingError("requested model is not in the reviewed Company HQ policy")
        if catalog["verified"]:
            available = {row["model"] for row in catalog["models"]}
            if requested not in available:
                raise RoutingError("requested reviewed model is not currently exposed by the native account")
        row = next((item for item in catalog.get("models", []) if item.get("model") == requested), {})
        return {
            "provider": "codex",
            "model": requested,
            "effort": _choose_effort(row, "standard") if row else None,
            "tier": "manual",
            "score": None,
            "reason": "explicit user model selection; provider default/medium effort where supported",
            "catalogVerified": catalog["verified"],
        }

    if not catalog["verified"]:
        raise RoutingError(
            "Auto routing requires the current native model catalog; "
            + str(catalog.get("reason") or "catalog verification failed")
        )

    score, reasons = complexity_score(prompt, mode)
    tier = _tier_for(score)
    rows = {row["model"]: row for row in catalog["models"]}
    available = set(rows)
    for model in _candidate_order(policy, tier):
        if model in available:
            return {
                "provider": "codex",
                "model": model,
                "effort": _choose_effort(rows[model], tier),
                "tier": tier,
                "score": score,
                "reason": "; ".join(reasons),
                "catalogVerified": True,
            }
    raise RoutingError(f"no reviewed available Codex model satisfies the {tier} capability tier")
