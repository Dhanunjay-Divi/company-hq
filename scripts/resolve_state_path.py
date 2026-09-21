#!/usr/bin/env python3
"""Resolve and validate one Company HQ component state directory without writing it."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "clawteam" / "integration"
sys.path.insert(0, str(INTEGRATION))

from runtime_config import ConfigurationError, component_state_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=["ruflo", "graft", "codebase-memory"])
    args = parser.parse_args()
    try:
        print(component_state_root(args.component))
    except ConfigurationError as exc:
        print(f"unsafe state configuration: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
