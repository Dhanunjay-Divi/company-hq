"""Deterministic, token-free capability routing for Company HQ.

The registry carries compact metadata for the full audited capability pool. This
module selects the minimum useful agents/skills/tools before any model is called.
The returned packet is deliberately small so a reviewer and supervisor do not
need the entire catalog in context.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CATALOG_PATH = REPO_ROOT / "capabilities" / "catalog.json"
MODEL_POLICY_PATH = REPO_ROOT / "capabilities" / "model-policy.json"

_BUILD_WORDS = {
    "build", "create", "implement", "add", "develop", "fix", "refactor", "migrate",
    "design", "ship", "deploy", "change", "update", "rewrite",
}
_HIGH_RISK = {
    "auth", "oauth", "jwt", "security", "permission", "secret", "encryption",
    "payment", "billing", "pci", "prod", "production", "deploy", "release",
    "migration", "database migration", "delete", "destructive", "infrastructure",
    "terraform", "kubernetes", "credential",
}
_MEDIUM_RISK = {
    "architecture", "distributed", "schema", "database", "api", "backend",
    "dependency", "refactor", "ci", "docker", "observability", "pipeline",
}
_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build",
    ".next", "target", "coverage", "__pycache__",
}
_EXT_FACETS = {
    ".tsx": {"frontend"}, ".jsx": {"frontend"}, ".vue": {"frontend"},
    ".css": {"frontend"}, ".scss": {"frontend"}, ".html": {"frontend"},
    ".py": {"backend"}, ".java": {"backend"}, ".kt": {"backend"}, ".go": {"backend"},
    ".rs": {"backend"}, ".cs": {"backend"}, ".php": {"backend"}, ".rb": {"backend"},
    ".sql": {"data"}, ".ipynb": {"data", "research"},
}
_NAME_FACETS = {
    "dockerfile": {"devops"}, "docker-compose.yml": {"devops"},
    "docker-compose.yaml": {"devops"}, "terraform.tf": {"devops"},
    "pom.xml": {"backend"}, "build.gradle": {"backend"}, "build.gradle.kts": {"backend"},
    "package.json": {"frontend", "backend"}, "pyproject.toml": {"backend"},
    "cargo.toml": {"backend"}, "requirements.txt": {"backend"},
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid policy file: {path}")
    return value


def load_catalog() -> dict[str, Any]:
    return _load_json(CATALOG_PATH)


def load_model_policy() -> dict[str, Any]:
    return _load_json(MODEL_POLICY_PATH)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#._-]+", text.lower()))


def project_signals(project: Path | None, max_entries: int = 500) -> dict[str, Any]:
    """Inspect only names/extensions; do not read project file contents."""
    if project is None:
        return {"facets": [], "sampled": 0, "manifests": []}
    try:
        root = Path(project).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return {"facets": [], "sampled": 0, "manifests": []}
    if not root.is_dir():
        return {"facets": [], "sampled": 0, "manifests": []}

    facets: set[str] = set()
    manifests: set[str] = set()
    sampled = 0
    for path in root.rglob("*"):
        if sampled >= max_entries:
            break
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part.lower() in _IGNORE_DIRS for part in relative.parts[:-1]):
            continue
        if not path.is_file():
            continue
        sampled += 1
        name = path.name.lower()
        suffix = path.suffix.lower()
        facets.update(_EXT_FACETS.get(suffix, set()))
        facets.update(_NAME_FACETS.get(name, set()))
        if name in _NAME_FACETS:
            manifests.add(name)
    return {
        "facets": sorted(facets),
        "sampled": sampled,
        "manifests": sorted(manifests),
    }


def _facet_matches(goal: str, catalog: dict[str, Any]) -> tuple[set[str], dict[str, list[str]]]:
    lowered = goal.lower()
    token_set = _tokens(goal)
    matched: set[str] = set()
    evidence: dict[str, list[str]] = {}
    for facet, triggers in catalog.get("facets", {}).items():
        hits: list[str] = []
        for raw in triggers:
            trigger = str(raw).lower()
            if " " in trigger:
                hit = trigger in lowered
            else:
                hit = trigger in token_set or trigger in lowered
            if hit:
                hits.append(trigger)
        if hits:
            matched.add(facet)
            evidence[facet] = hits[:6]
    return matched, evidence


def _risk(goal: str, facets: set[str]) -> tuple[str, list[str]]:
    lowered = goal.lower()
    reasons: list[str] = []
    for term in sorted(_HIGH_RISK):
        if term in lowered:
            reasons.append(term)
    if reasons:
        return "high", reasons[:8]

    medium = [term for term in sorted(_MEDIUM_RISK) if term in lowered]
    if medium or len(facets & {"architecture", "data", "devops", "refactor"}) >= 2 or len(facets) >= 4:
        return "medium", (medium or ["multi-component change"])[:8]
    return "low", ["bounded/local change"]


def _choose_agents(facets: set[str], catalog: dict[str, Any], build_request: bool) -> list[dict[str, Any]]:
    agents = catalog.get("agents", [])
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for agent in agents:
        covers = set(agent.get("covers", []))
        overlap = facets & covers
        if not overlap:
            continue
        scored.append((len(overlap), int(agent.get("priority", 0)), agent))
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]["id"]))

    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    for _, _, agent in scored:
        new = (set(agent.get("covers", [])) & facets) - covered
        if not new:
            continue
        selected.append({
            "id": agent["id"],
            "covers": sorted(new),
            "source": agent.get("source", []),
            "packet": agent.get("packet", ""),
        })
        covered.update(new)
        if len(selected) >= 4:
            break

    implementation_facets = facets & {"backend", "frontend", "data", "devops", "refactor"}
    ids = {a["id"] for a in selected}
    if build_request and implementation_facets and "qa-engineer" not in ids:
        qa = next((a for a in agents if a.get("id") == "qa-engineer"), None)
        if qa:
            selected.append({
                "id": qa["id"],
                "covers": ["verification"],
                "source": qa.get("source", []),
                "packet": qa.get("packet", ""),
            })
    return selected[:5]


def _choose_skills(facets: set[str], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for skill in catalog.get("skills", []):
        overlap = facets & set(skill.get("facets", []))
        if overlap:
            scored.append((len(overlap), skill["id"], skill))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "id": skill["id"],
            "source": skill.get("source"),
            "load": skill.get("load", "on-demand"),
            "packet": skill.get("packet", ""),
        }
        for _, _, skill in scored[:6]
    ]


def _choose_tools(facets: set[str], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for tool in catalog.get("tools", []):
        overlap = facets & set(tool.get("facets", []))
        if overlap:
            candidates.append((len(overlap), int(tool.get("preference", 0)), tool["id"], tool))
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))

    selected: list[dict[str, Any]] = []
    groups: set[str] = set()
    code_intel = {"codegraph", "serena", "graphify", "codebase-memory", "graft"}
    token_tools = {"rtk", "headroom"}
    for _, _, _, tool in candidates:
        tool_id = tool["id"]
        if tool_id in code_intel:
            group = "code-intelligence"
            # Serena complements the structural graph for explicit refactors.
            if group in groups and not (tool_id == "serena" and "refactor" in facets):
                continue
        elif tool_id in token_tools:
            group = "token-output"
            if group in groups:
                continue
        else:
            group = tool_id
            if group in groups:
                continue
        selected.append({
            "id": tool_id,
            "status": tool.get("status"),
            "source": tool.get("source"),
            "packet": tool.get("packet", ""),
        })
        groups.add(group)
        if len(selected) >= 5:
            break
    return selected


def route_task(goal: str, project: Path | None = None) -> dict[str, Any]:
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be non-empty text")
    if len(goal) > 24_000:
        raise ValueError("goal is too large for capability routing")

    catalog = load_catalog()
    model_policy = load_model_policy()
    facets, evidence = _facet_matches(goal, catalog)
    signals = project_signals(project)
    facets.update(signals["facets"])

    lowered = goal.lower()
    build_request = bool(_BUILD_WORDS & _tokens(goal)) or any(
        phrase in lowered for phrase in ("can you build", "please build", "need to build")
    )
    if build_request and not facets:
        facets.add("backend")
        evidence["backend"] = ["generic implementation fallback"]

    risk, risk_reasons = _risk(goal, facets)
    model_tier = model_policy["supervisor_auto_selection"][risk]["tier"]
    codex_model = model_policy["tiers"][model_tier]["codex_default"]

    agents = _choose_agents(facets, catalog, build_request)
    skills = _choose_skills(facets, catalog)
    tools = _choose_tools(facets, catalog)

    review_policy = model_policy["preflight_review"][f"{risk}_risk"]
    return {
        "schema": 1,
        "goal": goal.strip(),
        "buildRequest": build_request,
        "facets": sorted(facets),
        "facetEvidence": evidence,
        "projectSignals": signals,
        "risk": {"level": risk, "reasons": risk_reasons},
        "supervisor": {
            "tier": model_tier,
            "codexModel": codex_model,
            "reason": model_policy["supervisor_auto_selection"][risk]["reason"],
        },
        "agents": agents,
        "skills": skills,
        "tools": tools,
        "preflightReview": {
            "required": bool(build_request),
            "crossFamily": review_policy["cross_family"],
            "tier": review_policy["tier"],
        },
        "constraints": [
            "Spawn only agents that own independent useful work.",
            "Load only the listed skill packets; never inject the full skill catalog.",
            "Use code intelligence before broad repository rereads when available.",
            "Keep ClawTeam as the canonical task authority.",
            "Do not let a secondary framework become a competing scheduler.",
        ],
    }


def apply_review(plan: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Apply only known reviewer changes; arbitrary model output cannot create new roles."""
    result = json.loads(json.dumps(plan))
    known_agents = {a["id"]: a for a in load_catalog().get("agents", [])}
    current = {a["id"]: a for a in result.get("agents", [])}

    for agent_id in review.get("removeAgents", []) if isinstance(review.get("removeAgents"), list) else []:
        current.pop(str(agent_id), None)

    for agent_id in review.get("addAgents", []) if isinstance(review.get("addAgents"), list) else []:
        agent = known_agents.get(str(agent_id))
        if agent and agent["id"] not in current and len(current) < 5:
            current[agent["id"]] = {
                "id": agent["id"],
                "covers": sorted(set(agent.get("covers", [])) & set(result.get("facets", []))) or ["review-added"],
                "source": agent.get("source", []),
                "packet": agent.get("packet", ""),
            }

    result["agents"] = list(current.values())[:5]
    result["review"] = {
        "verdict": review.get("verdict", "revise"),
        "confidence": review.get("confidence"),
        "providerFamily": review.get("providerFamily"),
        "model": review.get("model"),
        "crossFamily": bool(review.get("crossFamily")),
        "reason": str(review.get("reason", ""))[:1200],
        "riskNotes": [str(x)[:500] for x in review.get("riskNotes", [])[:6]]
        if isinstance(review.get("riskNotes"), list) else [],
    }
    return result


def compact_packet(plan: dict[str, Any]) -> str:
    packet = {
        "facets": plan.get("facets", []),
        "risk": plan.get("risk", {}),
        "supervisor": plan.get("supervisor", {}),
        "agents": [
            {"id": a["id"], "covers": a.get("covers", []), "packet": a.get("packet", "")}
            for a in plan.get("agents", [])
        ],
        "skills": [
            {"id": s["id"], "source": s.get("source"), "packet": s.get("packet", "")}
            for s in plan.get("skills", [])
        ],
        "tools": [
            {"id": t["id"], "status": t.get("status"), "packet": t.get("packet", "")}
            for t in plan.get("tools", [])
        ],
        "review": plan.get("review"),
        "constraints": plan.get("constraints", []),
    }
    return json.dumps(packet, separators=(",", ":"), ensure_ascii=False)
