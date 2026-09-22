#!/usr/bin/env python3
"""Portable Company HQ setup and local launch helper.

Generated dependencies stay ignored inside the checkout. Runtime state stays in
XDG_STATE_HOME (or ~/.local/state/company-hq) unless COMPANY_HQ_STATE_ROOT is set.
No account files, HOME/CODEX_HOME, provider auth, or product repositories are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "clawteam" / "integration"
VENV = ROOT / "clawteam" / "venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
TEAM_UI = INTEGRATION / "team-ui"
CODEBASE_MEMORY = ROOT / "codebase-memory-mcp-0.10.8"
CODEBASE_MEMORY_BIN = CODEBASE_MEMORY / "bin" / ("codebase-memory-mcp.exe" if os.name == "nt" else "codebase-memory-mcp")
CODEBASE_MEMORY_RELEASE = "https://github.com/DeusData/codebase-memory-mcp/releases/download/v0.10.8"
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
from runtime_config import demo_project_root, health_snapshot, python_executable  # noqa: E402


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def ensure_integration_venv() -> None:
    if not VENV_PYTHON.is_file():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "clawteam" / "requirements.txt")])


def ensure_ruflo_dependencies() -> None:
    # Installs only the pinned, ignored dependency tree needed by the reviewed
    # project-scoped MCP facade. Lifecycle scripts stay disabled; this does not
    # run Ruflo init, hooks, daemons, provider auth, or project rewrites.
    run([
        "npm",
        "ci",
        "--prefix",
        str(ROOT / "ruflo-3.41.2"),
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ])


def _codebase_memory_asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    if system == "darwin":
        return f"codebase-memory-mcp-darwin-{arch}.tar.gz"
    if system == "linux":
        return f"codebase-memory-mcp-linux-{arch}-portable.tar.gz"
    if system == "windows":
        return f"codebase-memory-mcp-windows-{arch}.zip"
    raise RuntimeError(f"unsupported codebase-memory platform: {platform.system()} {platform.machine()}")


def _expected_checksum(asset_name: str) -> str:
    checksum_path = CODEBASE_MEMORY / "download" / "checksums.txt"
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == asset_name:
            return parts[0]
    raise RuntimeError(f"missing checksum for {asset_name}")


def ensure_codebase_memory_binary() -> None:
    # The repository keeps provenance and the guard, not release binaries. Install
    # the pinned executable into an ignored local path after archive verification.
    if CODEBASE_MEMORY_BIN.is_file() and os.access(CODEBASE_MEMORY_BIN, os.X_OK):
        return
    asset = _codebase_memory_asset_name()
    expected = _expected_checksum(asset)
    url = f"{CODEBASE_MEMORY_RELEASE}/{asset}"
    CODEBASE_MEMORY_BIN.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="company-hq-cbm-") as temp_name:
        temp = Path(temp_name)
        archive = temp / asset
        print(f"+ download {url}", flush=True)
        urllib.request.urlretrieve(url, archive)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"checksum mismatch for {asset}: expected {expected}, got {actual}")
        binary_name = CODEBASE_MEMORY_BIN.name
        payload = None
        if asset.endswith(".zip"):
            with zipfile.ZipFile(archive) as package:
                for member in package.infolist():
                    member_path = Path(member.filename)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise RuntimeError(f"unsafe path in {asset}: {member.filename}")
                    if member_path.name == binary_name:
                        payload = package.read(member)
                        break
        else:
            with tarfile.open(archive, "r:gz") as package:
                for member in package.getmembers():
                    member_path = Path(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise RuntimeError(f"unsafe path in {asset}: {member.name}")
                    if member_path.name == binary_name and member.isfile():
                        extracted = package.extractfile(member)
                        if extracted is not None:
                            payload = extracted.read()
                        break
        if payload is None:
            raise RuntimeError(f"{asset} did not contain {binary_name}")
        temporary = CODEBASE_MEMORY_BIN.with_name(f".{CODEBASE_MEMORY_BIN.name}.{os.getpid()}.tmp")
        temporary.write_bytes(payload)
        temporary.chmod(0o755)
        temporary.replace(CODEBASE_MEMORY_BIN)


def setup() -> None:
    ensure_integration_venv()
    ensure_ruflo_dependencies()
    ensure_codebase_memory_binary()
    from install_engines import install_engines
    install_engines()
    run(["npm", "ci", "--ignore-scripts"], cwd=ROOT / "company-hq")
    run(["npm", "run", "build"], cwd=ROOT / "company-hq")
    run([sys.executable, str(ROOT / "company-hq" / "build-source.py")])
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


def checks() -> int:
    ensure_integration_venv()
    commands = [
        [sys.executable, "-m", "unittest", "-v", "test_check_updates", "test_discover", "test_provider_registry"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        [str(VENV_PYTHON), "-m", "unittest", "discover", "-s", "clawteam/integration", "-p", "test_*.py", "-v"],
        ["node", "--test", "tests/test_draft_storage.mjs", "tests/test_native_team_view.mjs"],
        [sys.executable, "scripts/check_source_bundle.py"],
        [sys.executable, "scripts/check_portability.py"],
    ]
    for command in commands:
        run(command)
    return health()


def health() -> int:
    snapshot = health_snapshot()
    print(json.dumps(snapshot, indent=2))
    required = ("frontend", "routing")
    return 0 if all(snapshot["capabilities"][name]["available"] for name in required) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable Company HQ setup and launcher")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="install pinned Python/Node/Ruflo/code-index dependencies and build the UI")
    sub.add_parser("start", help="start the normal local workspace")
    sub.add_parser("demo", help="start a model-free synthetic workspace")
    for lifecycle in ("status", "stop"):
        command = sub.add_parser(lifecycle, help=f"{lifecycle} the local workspace")
        command.add_argument("--demo", action="store_true", help="target the model-free demo board")
    bootstrap = sub.add_parser("bootstrap", help="setup, build, and start in one command")
    bootstrap.add_argument("--demo", action="store_true", help="start model-free with synthetic fixture data")
    sub.add_parser("health", help="print capability status without starting providers")
    sub.add_parser("check", help="run the complete model-free validation suite")
    args = parser.parse_args()

    if args.command == "setup":
        setup()
        return 0
    if args.command == "health":
        return health()
    if args.command == "check":
        return checks()
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
