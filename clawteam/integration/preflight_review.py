"""Independent preflight review for Company HQ routing plans.

The preferred reviewer is a different provider family using an already-authorized
native coding runtime. Reviewers run in an empty temporary directory and receive
only the compact routing plan, never the product repository.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from capability_router import load_catalog


class ReviewError(RuntimeError):
    pass


def review_prompt(plan: dict[str, Any]) -> str:
    allowed = [item["id"] for item in load_catalog().get("agents", [])]
    compact = {
        "goal": plan.get("goal"),
        "facets": plan.get("facets"),
        "risk": plan.get("risk"),
        "supervisor": plan.get("supervisor"),
        "agents": [{"id": a["id"], "covers": a.get("covers", [])} for a in plan.get("agents", [])],
        "skills": [s["id"] for s in plan.get("skills", [])],
        "tools": [t["id"] for t in plan.get("tools", [])],
    }
    schema = {
        "verdict": "approve|revise|block",
        "confidence": 0.0,
        "addAgents": [],
        "removeAgents": [],
        "riskNotes": [],
        "reason": "short reason",
    }
    return (
        "Act as an independent preflight reviewer for an AI software team. "
        "Check whether the proposed team, skills, tools, risk level and supervisor tier "
        "match the requested outcome. Prefer the smallest capable team. Do not solve the "
        "user task and do not provide chain-of-thought. Return JSON only matching "
        + json.dumps(schema, separators=(",", ":"))
        + ". Only add agent IDs from this allowlist: "
        + json.dumps(allowed)
        + ". Block only for a material safety/capability problem. PLAN="
        + json.dumps(compact, separators=(",", ":"), ensure_ascii=False)
    )


def parse_review(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ReviewError("reviewer returned no text")
    raw = text.strip()
    candidates = [raw]
    candidates.extend(re.findall(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", raw, flags=re.S | re.I))
    first, last = raw.find("{"), raw.rfind("}")
    if first >= 0 and last > first:
        candidates.append(raw[first:last + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict) or value.get("verdict") not in {"approve", "revise", "block"}:
            continue
        confidence = value.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = None
        value["confidence"] = confidence
        for key in ("addAgents", "removeAgents", "riskNotes"):
            if not isinstance(value.get(key), list):
                value[key] = []
        value["reason"] = str(value.get("reason", ""))[:1200]
        return value
    raise ReviewError("reviewer response was not valid review JSON")


def _claude_review(prompt: str, risk: str) -> dict[str, Any]:
    executable = shutil.which("claude")
    if not executable:
        raise ReviewError("Claude Code is not installed")
    override = os.environ.get("COMPANY_HQ_CLAUDE_REVIEW_MODEL", "").strip()
    if override:
        models = [override]
    elif risk == "high":
        models = ["claude-fable-5", "opus"]
    elif risk == "medium":
        models = ["opus", "sonnet"]
    else:
        models = ["sonnet"]
    failures: list[str] = []
    for model in models:
        with tempfile.TemporaryDirectory(prefix="company-hq-review-claude-") as temp:
            completed = subprocess.run(
                [executable, "-p", prompt, "--output-format", "json", "--model", model,
                 "--permission-mode", "plan", "--max-turns", "1"],
                cwd=temp, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=120, check=False,
            )
        if completed.returncode != 0:
            failures.append((completed.stderr or completed.stdout or "Claude review failed").strip()[-500:])
            continue
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError:
            envelope = None
        result_text = envelope.get("result") if isinstance(envelope, dict) else None
        try:
            review = parse_review(result_text if isinstance(result_text, str) else completed.stdout)
        except ReviewError as exc:
            failures.append(str(exc))
            continue
        review.update({"providerFamily": "anthropic", "model": model, "crossFamily": True, "backend": "claude-code"})
        return review
    raise ReviewError("Claude review unavailable: " + " | ".join(failures))


def _opencode_family(model: str) -> str:
    provider = model.split("/", 1)[0].lower()
    return {"moonshotai": "moonshot", "kimi": "moonshot", "z-ai": "zai", "gemini": "google"}.get(provider, provider)


def _opencode_review(prompt: str, executor_family: str) -> dict[str, Any]:
    model = os.environ.get("COMPANY_HQ_REVIEW_MODEL", "").strip()
    if not model:
        raise ReviewError("No explicit OpenCode reviewer model is configured")
    executable = shutil.which("opencode")
    if not executable:
        raise ReviewError("OpenCode is not installed")
    family = _opencode_family(model)
    if family == executor_family:
        raise ReviewError("Configured OpenCode reviewer is not cross-family")
    with tempfile.TemporaryDirectory(prefix="company-hq-review-opencode-") as temp:
        completed = subprocess.run(
            [executable, "run", "--format", "json", "--model", model, "--dir", temp, prompt],
            cwd=temp, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=120, check=False,
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "OpenCode review failed").strip()[-1000:]
        raise ReviewError(detail)
    review = parse_review(completed.stdout)
    review.update({"providerFamily": family, "model": model, "crossFamily": True, "backend": "opencode"})
    return review


def _codex_review(prompt: str, plan: dict[str, Any]) -> dict[str, Any]:
    from codex_bridge import CodexBridge
    from runtime_config import codex_executable

    model = "gpt-6-astra" if plan.get("risk", {}).get("level") == "high" else "gpt-5.6-sol"
    with tempfile.TemporaryDirectory(prefix="company-hq-review-codex-") as temp:
        root = Path(temp)
        project, state = root / "empty-project", root / "state"
        project.mkdir(); state.mkdir()
        bridge = CodexBridge(state_dir=state, codex_path=codex_executable(), max_events=120)
        team = "preflight-" + uuid.uuid4().hex[:10]
        try:
            bridge.start(team, project, prompt, model)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = bridge.status(team)
                if status["state"] == "error":
                    raise ReviewError(str(status.get("error") or "Codex review failed"))
                if status["state"] == "awaiting_approval":
                    raise ReviewError("isolated Codex reviewer requested an unexpected approval")
                if status["state"] == "idle" and status.get("turnId"):
                    break
                time.sleep(0.1)
            else:
                raise ReviewError("Codex review timed out")
            events = bridge.events(team, 0).get("events", [])
            text = "\\n".join(
                str(event.get("data", {}).get("text", ""))
                for event in events if event.get("type") == "message.completed"
            )
            review = parse_review(text)
            review.update({"providerFamily": "openai", "model": model, "crossFamily": False, "backend": "codex-isolated"})
            return review
        finally:
            bridge.shutdown_all()


def review_plan(plan: dict[str, Any], *, executor_family: str = "openai", allow_model_calls: bool = True) -> dict[str, Any]:
    if not plan.get("preflightReview", {}).get("required"):
        return {"verdict": "approve", "confidence": 1.0, "addAgents": [], "removeAgents": [],
                "riskNotes": [], "reason": "No build execution requested; preflight model review skipped.",
                "providerFamily": "policy", "model": "none", "crossFamily": False, "backend": "policy"}
    if not allow_model_calls:
        return {"verdict": "approve", "confidence": None, "addAgents": [], "removeAgents": [],
                "riskNotes": ["model review skipped in model-free validation"], "reason": "Model-free validation path.",
                "providerFamily": "policy", "model": "none", "crossFamily": False, "backend": "policy"}

    prompt = review_prompt(plan)
    errors: list[str] = []
    risk = str(plan.get("risk", {}).get("level", "low"))
    for reviewer in (lambda: _claude_review(prompt, risk),
                     lambda: _opencode_review(prompt, executor_family),
                     lambda: _codex_review(prompt, plan)):
        try:
            return reviewer()
        except (OSError, subprocess.SubprocessError, ReviewError, ValueError) as exc:
            errors.append(str(exc)[:300])
    raise ReviewError("No preflight reviewer completed successfully: " + " | ".join(errors))


def review_is_sufficient(plan: dict[str, Any], review: dict[str, Any]) -> bool:
    return review.get("verdict") != "block" and review.get("providerFamily") is not None
