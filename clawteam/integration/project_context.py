"""Canonical, read-only project, board, and reviewed-skill context."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

from runtime_config import REPO_ROOT
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from task_authority import TaskStore

_TEAM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\Z")
_MAX_PAGE = 24_000


class ContextError(ValueError):
    pass


def validate_team(team: str) -> str:
    if not isinstance(team, str) or not _TEAM.fullmatch(team):
        raise ContextError("invalid project context team")
    return team


def workspace_project(team: str) -> Path:
    """Resolve the public Company HQ workspace binding for one team."""
    from clawteam.team.manager import TeamManager
    from company_profile import load_profile
    from runtime_config import clawteam_data_dir
    group = TeamManager.get_team(team)
    if group is None:
        raise ContextError("project context team is unavailable")
    profile = load_profile(clawteam_data_dir(), team, {member.name for member in group.members})
    raw = profile.get("projectRoot")
    if not isinstance(raw, str) or not raw:
        raise ContextError("project context team has no workspace binding")
    try:
        bound = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContextError("project context workspace is unavailable") from exc
    if not bound.is_dir():
        raise ContextError("project context workspace is invalid")
    return bound


class ProjectContext:
    """A launch-bound view; skills are references, never permissions."""

    def __init__(self, project: str | Path, team: str, *, skill_roots: tuple[Path, ...] | None = None, store_factory: Callable[[str], Any] = TaskStore, binding_resolver: Callable[[str], Path] = workspace_project) -> None:
        try:
            root = Path(project).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ContextError("project context root is unavailable") from exc
        if not root.is_dir() or root == Path.home().resolve() or root == Path("/"):
            raise ContextError("project context root is invalid")
        self.project = root
        self.team = validate_team(team)
        try:
            if Path(binding_resolver(self.team)).resolve(strict=True) != self.project:
                raise ContextError("project context does not match the team workspace")
        except ContextError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ContextError("project context workspace binding is unavailable") from exc
        self.store_factory = store_factory
        # This fixed list is the only discovery boundary: repository skills and
        # the reviewed local Codex skill library. Callers cannot supply paths.
        self.include_agency = skill_roots is None
        self.skill_roots = skill_roots or (REPO_ROOT / "skills", Path.home() / ".codex" / "skills")

    def identity(self) -> dict[str, str]:
        return {"projectRoot": str(self.project), "projectName": self.project.name, "team": self.team,
                "relationship": "User → outer reviewer → HQ supervisor → department leaders → workers",
                "authority": "The documented canonical board is the one task authority; context does not inject policy or permissions."}

    def board(self, *, cursor: int = 0, limit: int = 50) -> dict[str, Any]:
        if not isinstance(cursor, int) or cursor < 0 or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ContextError("invalid board page")
        tasks = self.store_factory(self.team).list_tasks()
        rows = []
        for task in tasks[cursor:cursor + limit]:
            rows.append({"id": str(task.id), "subject": str(getattr(task, "subject", ""))[:300],
                         "description": str(getattr(task, "description", ""))[:1200],
                         "status": str(getattr(task.status, "value", task.status)), "owner": str(getattr(task, "owner", ""))[:160],
                         "priority": str(getattr(getattr(task, "priority", ""), "value", getattr(task, "priority", "")))})
        next_cursor = cursor + len(rows)
        return {"team": self.team, "tasks": rows, "nextCursor": next_cursor if next_cursor < len(tasks) else None}

    @staticmethod
    def _description(path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:8192]
        except OSError:
            return ""
        match = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
        return match.group(1).strip()[:500] if match else ""

    def _registered(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        for root in self.skill_roots:
            if root.is_symlink() or not root.is_dir():
                continue
            for skill in root.iterdir():
                manifest = skill / "SKILL.md"
                if not skill.is_dir() or skill.is_symlink() or manifest.is_symlink() or not manifest.is_file():
                    continue
                # Repository skills take precedence over reviewed library names.
                found.setdefault(skill.name, skill.resolve())
        agency = REPO_ROOT / "agency-agents"
        if self.include_agency and agency.is_dir() and not agency.is_symlink() and (agency/"USE.md").is_file():
            found["agency-agents"] = agency.resolve()
        return found

    def skills(self) -> list[dict[str, str]]:
        return [{"name": name, "description": "Specialist role guidance for product, engineering, design, research, marketing and delivery. Read USE.md, then only the relevant upstream role." if name == "agency-agents" else self._description(path / "SKILL.md")} for name, path in sorted(self._registered().items())]

    def skill_read(self, name: str, relative_path: str = "SKILL.md", *, cursor: int = 0, limit: int = _MAX_PAGE) -> dict[str, Any]:
        registry = self._registered()
        root = registry.get(name)
        if root is None:
            raise ContextError("unknown reviewed skill")
        if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise ContextError("invalid skill reference path")
        if not isinstance(cursor, int) or cursor < 0 or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE:
            raise ContextError("invalid skill page")
        if name == "agency-agents" and relative_path == "SKILL.md":
            relative_path = "USE.md"
        target = root / relative_path
        probe = root
        for component in Path(relative_path).parts:
            probe = probe / component
            if probe.is_symlink():
                raise ContextError("skill reference is not an approved regular file")
        try:
            resolved = target.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ContextError("skill reference is unavailable") from exc
        if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.stat().st_size > 2_000_000:
            raise ContextError("skill reference is not an approved regular file")
        text = resolved.read_text(encoding="utf-8", errors="replace")
        page = text[cursor:cursor + limit]
        next_cursor = cursor + len(page)
        return {"name": name, "path": relative_path, "text": page, "nextCursor": next_cursor if next_cursor < len(text) else None}


def launched_context() -> ProjectContext:
    project, team = os.environ.get("COMPANY_HQ_CONTEXT_PROJECT"), os.environ.get("COMPANY_HQ_CONTEXT_TEAM")
    if not project or not team:
        raise ContextError("project context launch binding is missing")
    return ProjectContext(project, team)
