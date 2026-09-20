"""Portable Company HQ runtime configuration.

This module keeps source checkout, application state, project workspaces, and
provider account homes separate. It never rewrites HOME/CODEX_HOME or copies
authentication artifacts.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any


INTEGRATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = INTEGRATION_DIR.parents[1]
FRONTEND_DIR = REPO_ROOT / "company-hq"


class ConfigurationError(RuntimeError):
    """Unsafe or invalid local runtime configuration."""


def _expand(raw: str | os.PathLike[str]) -> Path:
    return Path(raw).expanduser().resolve()


def _default_state_root() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = _expand(xdg) if xdg else Path.home().resolve() / ".local" / "state"
    return base / "company-hq"


def state_root() -> Path:
    raw = os.environ.get("COMPANY_HQ_STATE_ROOT")
    path = _expand(raw) if raw else _default_state_root().resolve()
    source = REPO_ROOT.resolve()
    home = Path.home().resolve()
    if path in {Path("/").resolve(), home, source} or path.is_relative_to(source):
        raise ConfigurationError(
            "COMPANY_HQ_STATE_ROOT must be outside the source checkout, filesystem root, and account home"
        )
    return path


def demo_mode() -> bool:
    return os.environ.get("COMPANY_HQ_DEMO", "").strip() == "1"


def clawteam_data_dir() -> Path:
    testing = os.environ.get("CLAWTEAM_INTEGRATION_TESTING") == "1"
    test_override = os.environ.get("CLAWTEAM_INTEGRATION_TEST_DATA_DIR") if testing else None
    if test_override:
        return _expand(test_override)
    base = state_root()
    return base / ("demo/clawteam" if demo_mode() else "clawteam")


def runtime_dir(data_dir: Path | None = None) -> Path:
    return (Path(data_dir).resolve() if data_dir else clawteam_data_dir()) / "runtime"


def routing_path() -> Path:
    raw = os.environ.get("COMPANY_HQ_ROUTING_PATH")
    return _expand(raw) if raw else REPO_ROOT / "routing.json"


def saved_projects_path() -> Path:
    raw = os.environ.get("COMPANY_HQ_SAVED_PROJECTS_PATH")
    return _expand(raw) if raw else state_root() / "saved-projects.json"


def capabilities_path() -> Path:
    raw = os.environ.get("COMPANY_HQ_CAPABILITIES_PATH")
    return _expand(raw) if raw else state_root() / "capabilities.json"


def ruflo_launcher() -> Path:
    raw = os.environ.get("COMPANY_HQ_RUFLO_LAUNCHER")
    return _expand(raw) if raw else REPO_ROOT / "ruflo-integration" / "ruflo-mcp"


def graft_install_root() -> Path:
    raw = os.environ.get("COMPANY_HQ_GRAFT_INSTALL")
    return _expand(raw) if raw else REPO_ROOT / "graft-0.18.0"


def graft_state_root() -> Path:
    raw = os.environ.get("COMPANY_HQ_GRAFT_STATE_ROOT")
    return _expand(raw) if raw else state_root() / "graft"


def codebase_memory_launcher() -> Path:
    raw = os.environ.get("COMPANY_HQ_CODEBASE_MEMORY_LAUNCHER")
    if raw:
        return _expand(raw)
    return REPO_ROOT / "codebase-memory-mcp-0.10.8" / "bin" / "codebase-memory-mcp-mcp"


def python_executable() -> Path:
    raw = os.environ.get("COMPANY_HQ_PYTHON")
    if raw:
        return _expand(raw)
    venv = REPO_ROOT / "clawteam" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return venv.absolute() if venv.is_file() else Path(sys.executable).absolute()


def codex_executable() -> Path:
    raw = os.environ.get("COMPANY_HQ_CODEX_PATH")
    if raw:
        return _expand(raw)
    discovered = shutil.which("codex")
    if discovered:
        return Path(discovered).resolve()
    mac_app = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    return mac_app


def frontend_dist() -> Path:
    return FRONTEND_DIR / "dist"


def demo_project_root() -> Path:
    return state_root() / "demo" / "project"


def _availability(path: Path, *, executable: bool = False) -> dict[str, Any]:
    exists = path.is_file()
    available = exists and (not executable or os.access(path, os.X_OK))
    return {
        "available": available,
        "path": str(path),
        "reason": None if available else ("missing executable" if executable else "missing file"),
    }


def _compound_availability(
    launcher: Path,
    required: list[tuple[Path, bool]],
) -> dict[str, Any]:
    launcher_status = _availability(launcher, executable=True)
    if not launcher_status["available"]:
        return launcher_status
    for required_path, executable in required:
        status = _availability(required_path, executable=executable)
        if not status["available"]:
            return {
                "available": False,
                "path": str(launcher),
                "reason": f"dependency unavailable: {required_path}",
            }
    return {"available": True, "path": str(launcher), "reason": None}


def health_snapshot(data_dir: Path | None = None) -> dict[str, Any]:
    """Return truthful local capability status without starting providers."""
    state = Path(data_dir).resolve() if data_dir else clawteam_data_dir().resolve()
    routing = routing_path()
    ruflo = ruflo_launcher()
    graft_bin = graft_install_root() / "node_modules" / ".bin" / (
        "graft.cmd" if os.name == "nt" else "graft"
    )
    cbm = codebase_memory_launcher()
    cbm_binary = cbm.parent / "codebase-memory-mcp"
    cbm_guard = cbm.parent / "mcp_guard.py"
    ruflo_handler = REPO_ROOT / "ruflo-3.41.2" / "node_modules" / "@claude-flow" / "cli" / "dist" / "src" / "mcp-tools" / "memory-tools.js"
    codex = codex_executable()
    return {
        "schema": 1,
        "mode": "demo" if demo_mode() else "normal",
        "sourceRoot": str(REPO_ROOT.resolve()),
        "stateRoot": str(state_root().resolve()),
        "clawteamState": str(state),
        "accountHomePreserved": True,
        "modelExecutionEnabled": not demo_mode(),
        "capabilities": {
            "frontend": _availability(frontend_dist() / "index.html"),
            "routing": _availability(routing),
            "codex": _availability(codex, executable=True),
            "rufloMemory": _compound_availability(ruflo, [(ruflo_handler, False)]),
            "graft": _availability(graft_bin, executable=True),
            "codebaseMemory": _compound_availability(
                cbm, [(cbm_binary, True), (cbm_guard, False)]
            ),
        },
    }
