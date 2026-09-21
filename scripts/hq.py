#!/usr/bin/env python3
"""Portable Company HQ setup and local launch helper.

Generated dependencies stay ignored inside the checkout. Runtime state stays in
XDG_STATE_HOME (or ~/.local/state/company-hq) unless COMPANY_HQ_STATE_ROOT is set.
No account files, HOME/CODEX_HOME, provider auth, or product repositories are changed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "clawteam" / "integration"
VENV = ROOT / "clawteam" / "venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
TEAM_UI = INTEGRATION / "team-ui"
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
from runtime_config import demo_project_root, health_snapshot, python_executable  # noqa: E402


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def setup() -> None:
    if not VENV_PYTHON.is_file():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "clawteam" / "requirements.txt")])
    run(["npm", "ci", "--ignore-scripts"], cwd=ROOT / "company-hq")
    run(["npm", "run", "build"], cwd=ROOT / "company-hq")
    print("Setup complete. Runtime state and provider accounts remain outside this checkout.")


def _launch_env(*, demo: bool) -> dict[str, str]:
    env = os.environ.copy()
    if demo:
        env["COMPANY_HQ_DEMO"] = "1"
    else:
        env.pop("COMPANY_HQ_DEMO", None)
    return env


def _team_ui(command: str, *, demo: bool, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python_executable()), str(TEAM_UI), command],
        cwd=INTEGRATION,
        env=_launch_env(demo=demo),
        capture_output=True,
        text=True,
        check=check,
    )


def start(*, demo: bool) -> str:
    result = _team_ui("start", demo=demo)
    print(result.stdout, end="")
    marker = "http://127.0.0.1:"
    for token in result.stdout.split():
        if token.startswith(marker):
            return token.rstrip()
    status = _team_ui("status", demo=demo)
    for token in status.stdout.split():
        if token.startswith(marker):
            return token.rstrip()
    raise RuntimeError("Company HQ started but its loopback URL was not reported")


def seed_demo(url: str) -> None:
    """Create one clearly synthetic workspace without starting any model."""
    project = demo_project_root()
    project.mkdir(parents=True, exist_ok=True)
    sample = project / "README.md"
    if not sample.exists():
        sample.write_text(
            "# Synthetic Company HQ demo project\n\n"
            "This folder is created only for model-free onboarding. No provider is called.\n",
            encoding="utf-8",
        )

    with urllib.request.urlopen(url + "/api/overview", timeout=3) as response:
        teams = json.load(response)
    if teams:
        return

    body = json.dumps({
        "label": "Synthetic demo",
        "project": str(project.resolve()),
        "goal": "Understand the Company HQ workflow without starting a model.",
    }).encode("utf-8")
    request = urllib.request.Request(
        url + "/api/workspaces",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Origin": url},
    )
    with urllib.request.urlopen(request, timeout=3):
        pass


def health() -> int:
    snapshot = health_snapshot()
    print(json.dumps(snapshot, indent=2))
    required = ("frontend", "routing")
    return 0 if all(snapshot["capabilities"][name]["available"] for name in required) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable Company HQ setup and launcher")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="install pinned Python/Node dependencies and build the UI")
    sub.add_parser("start", help="start the normal local workspace")
    sub.add_parser("demo", help="start a model-free synthetic workspace")
    for lifecycle in ("status", "stop"):
        command = sub.add_parser(lifecycle, help=f"{lifecycle} the local workspace")
        command.add_argument("--demo", action="store_true", help="target the model-free demo board")
    bootstrap = sub.add_parser("bootstrap", help="setup, build, and start in one command")
    bootstrap.add_argument("--demo", action="store_true", help="start model-free with synthetic fixture data")
    sub.add_parser("health", help="print capability status without starting providers")
    args = parser.parse_args()

    if args.command == "setup":
        setup()
        return 0
    if args.command == "health":
        return health()
    if args.command in {"status", "stop"}:
        result = _team_ui(args.command, demo=args.demo, check=False)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    if args.command == "bootstrap":
        setup()
        url = start(demo=args.demo)
        if args.demo:
            seed_demo(url)
            print("Stop demo with: python3 scripts/hq.py stop --demo")
        print(url)
        return 0
    if args.command == "demo":
        url = start(demo=True)
        seed_demo(url)
        print("Stop demo with: python3 scripts/hq.py stop --demo")
        print(url)
        return 0
    url = start(demo=False)
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
