#!/usr/bin/env python3
"""Fail if active portable source still embeds the original machine identity.

Historical verification/provenance files are allowed to describe the machine on
which they were produced. Runtime code, launchers, active instructions, and
current setup docs must not depend on it.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = ("archive/",)
SKIP_NAMES = {
    "docs/PACKAGING.md",
    "graft-0.18.0/INSTALLATION.json",
}
BANNED = (
    "/Users/" + "uno",
    "/Users/Shared/" + "agent-toolkit-codebase-memory-mcp-501",
)


def is_historical(name: str) -> bool:
    return (
        name.startswith(SKIP_PREFIXES)
        or name in SKIP_NAMES
        or name.endswith("/VERIFICATION.md")
        or name == "company-hq/VERIFICATION.md"
    )


def main() -> int:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    findings: list[dict[str, object]] = []
    checked = 0
    for raw in tracked:
        if not raw:
            continue
        name = raw.decode("utf-8")
        if is_historical(name):
            continue
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        checked += 1
        for token in BANNED:
            if token in text:
                findings.append({"path": name, "token": token})
    print(json.dumps({"checked_files": checked, "findings": findings}))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
