#!/usr/bin/env python3
"""Run the pinned Graft structural graph without repository integration."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if os.name == "nt":
    import msvcrt
else:
    import fcntl


REPO_ROOT = Path(__file__).resolve().parent
INSTALL = Path(os.environ.get("COMPANY_HQ_GRAFT_INSTALL", REPO_ROOT / "graft-0.18.0")).expanduser().resolve()
GRAFT = INSTALL / "node_modules" / ".bin" / ("graft.cmd" if os.name == "nt" else "graft")
_state_base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")).expanduser()
_global_state = Path(os.environ.get("COMPANY_HQ_STATE_ROOT", _state_base / "company-hq")).expanduser()
STATE = Path(os.environ.get("COMPANY_HQ_GRAFT_STATE_ROOT", _global_state / "graft")).resolve()

# These variables are irrelevant to the reviewed structural command paths.
# Removing them is defense in depth; it is not a network sandbox.
MODEL_ENV_KEYS = (
    "GRAFT_API_KEY",
    "GRAFT_BASE_URL",
    "GRAFT_MODEL",
    "GRAFT_PROVIDER",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "ORCAROUTER_API_KEY",
)


def validate_state_root() -> Path:
    state = STATE.resolve()
    home = Path.home().resolve()
    source = REPO_ROOT.resolve()
    if state in {Path(state.anchor).resolve(), home, source} or state.is_relative_to(source):
        raise ValueError(f"unsafe Graft state root: {state}")
    probe = state
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if probe.is_file():
        probe = probe.parent
    if any((parent / ".git").exists() for parent in (probe, *probe.parents)):
        raise ValueError("Graft state root must not be inside a Git working tree")
    return state


def canonical_project(raw: str) -> Path:
    project = Path(raw).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError(f"project is not a directory: {project}")
    return project


def project_state(project: Path) -> tuple[str, Path]:
    project_id = hashlib.sha256(os.fsencode(project)).hexdigest()
    return project_id, STATE / "projects" / project_id


def safe_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in MODEL_ENV_KEYS:
        env.pop(key, None)
    env.update(
        {
            "DO_NOT_TRACK": "1",
            "GRAFT_NO_GITIGNORE": "1",
            "GRAFT_NO_IGNORE": "1",
        }
    )
    return env


def record_project(project: Path, project_id: str, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    metadata = {
        "schema": 1,
        "project_id": project_id,
        "canonical_project": os.fspath(project),
        "graph_dir": os.fspath(state_dir / "graph"),
    }
    target = state_dir / "project.json"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state_dir,
            prefix=".project.json.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.chmod(temporary.name, 0o600)
            temporary.write(json.dumps(metadata, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


@contextmanager
def project_write_lock(state_dir: Path):
    """Serialize graph writers for one canonical project."""
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_dir / ".structural.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        if os.name == "nt":
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            while True:
                os.lseek(descriptor, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    # LK_LOCK gives up after a bounded retry window. Poll the
                    # non-blocking primitive instead so long graph builds are
                    # serialized just like POSIX flock without a false timeout.
                    import time
                    time.sleep(0.1)
        else:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            acquired = True
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def run_graft(arguments: list[str]) -> int:
    if not GRAFT.is_file():
        print(f"Pinned Graft executable is missing: {GRAFT}", file=sys.stderr)
        return 1
    try:
        completed = subprocess.run(
            [os.fspath(GRAFT), *arguments],
            env=safe_environment(),
            check=False,
        )
        return completed.returncode
    except KeyboardInterrupt:
        return 130


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pinned, local-only Graft structural graph wrapper."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build a deterministic structural graph")
    build.add_argument("project", help="repository directory to read")

    query = subparsers.add_parser("query", help="query an existing structural graph")
    query.add_argument("project", help="repository directory to read")
    query.add_argument("question", help="plain-language structural query")
    query.add_argument("--json", action="store_true", help="emit upstream JSON output")
    query.add_argument("--source", action="store_true", help="include bounded source excerpts")
    query.add_argument("--no-refresh", action="store_true", help="do not refresh a stale graph")

    viz = subparsers.add_parser(
        "viz", help="explicitly serve the existing graph on 127.0.0.1"
    )
    viz.add_argument("project", help="repository directory to identify")
    viz.add_argument("--explicit", action="store_true", required=True)
    viz.add_argument("--port", type=int, default=4400)

    args = parser.parse_args()
    try:
        validate_state_root()
        project = canonical_project(args.project)
    except (FileNotFoundError, OSError, ValueError) as error:
        parser.error(str(error))
    project_id, state_dir = project_state(project)
    graph_dir = state_dir / "graph"

    if args.command == "build":
        with project_write_lock(state_dir):
            record_project(project, project_id, state_dir)
            return run_graft(
                [
                    "--dir",
                    os.fspath(graph_dir),
                    "build",
                    os.fspath(project),
                    "--no-gitignore",
                    "--no-ignore",
                ]
            )

    if not graph_dir.is_dir():
        print(f"No graph for {project}. Run the build command first.", file=sys.stderr)
        return 1

    if args.command == "query":
        command = [
            "--dir",
            os.fspath(graph_dir),
            "ask",
            args.question,
            os.fspath(project),
        ]
        if args.json:
            command.append("--json")
        if args.source:
            command.append("--source")
        if args.no_refresh:
            command.append("--no-refresh")
        with project_write_lock(state_dir):
            return run_graft(command)

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return run_graft(
        [
            "--dir",
            os.fspath(graph_dir),
            "viz",
            os.fspath(project),
            "--no-open",
            "--port",
            str(args.port),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
