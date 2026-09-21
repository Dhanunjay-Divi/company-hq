#!/usr/bin/env python3
"""One-turn live smoke test. Run manually; it consumes a small Codex turn."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from codex_bridge import CodexBridge
from runtime_config import REPO_ROOT

TEAM = "bridge-luna-manual-verification"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="explicit synthetic/approved fixture project")
    parser.add_argument("--state", required=True, help="external runtime state directory")
    parser.add_argument("--receipt", required=True, help="external one-run receipt path")
    args = parser.parse_args()
    PROJECT = Path(args.project).expanduser().resolve(strict=True)
    STATE = Path(args.state).expanduser().resolve()
    RECEIPT = Path(args.receipt).expanduser().resolve()
    if not PROJECT.is_dir():
        parser.error("--project must be a directory")
    if PROJECT in {Path("/"), Path.home().resolve()}:
        parser.error("refusing filesystem root or account home as the fixture project")
    source = REPO_ROOT.resolve()
    home = Path.home().resolve()
    def validate_output(path: Path, label: str) -> Path:
        value = path.resolve()
        if value in {Path("/").resolve(), home, source, PROJECT}:
            parser.error(f"{label} must be external fixture state")
        if value.is_relative_to(source) or value.is_relative_to(PROJECT):
            parser.error(f"{label} must not overlap source or project files")
        return value
    STATE = validate_output(STATE, "--state")
    RECEIPT = validate_output(RECEIPT, "--receipt")
    validate_output(RECEIPT.parent, "--receipt parent")
    STATE.mkdir(parents=True, exist_ok=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    if RECEIPT.exists():
        print(f"Live smoke already completed; refusing to run again: {RECEIPT}")
        return 64
    bridge = CodexBridge(state_dir=STATE, request_timeout=20)
    receipt = {
        "model": "gpt-5.6-luna",
        "project": str(PROJECT),
        "team": TEAM,
    }
    try:
        started = bridge.start(
            TEAM,
            PROJECT,
            "Reply with exactly BRIDGE_LUNA_OK and nothing else. Do not use tools.",
            "gpt-5.6-luna",
        )
        receipt.update({
            "threadId": started["threadId"],
            "turnId": started["turnId"],
            "startState": started["state"],
        })
        after = 0
        event_types: list[str] = []
        final_text = ""
        deadline = time.time() + 90
        while time.time() < deadline:
            batch = bridge.events(TEAM, after)
            for event in batch["events"]:
                after = max(after, event["seq"])
                event_types.append(event["type"])
                if event["type"] == "message.completed":
                    final_text = event["data"].get("text", "")
            status = bridge.status(TEAM)
            for approval in status["pendingApprovals"]:
                bridge.approve(TEAM, approval["requestId"], "reject")
            if status["state"] in {"idle", "error"}:
                receipt["finalState"] = status["state"]
                if status.get("error"):
                    receipt["error"] = status["error"]
                break
            time.sleep(0.2)
        else:
            receipt["finalState"] = "timeout"
        receipt["eventTypes"] = sorted(set(event_types))
        receipt["finalText"] = final_text
        receipt["bridgeOk"] = (
            final_text.strip() == "BRIDGE_LUNA_OK"
            and receipt.get("finalState") == "idle"
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0 if receipt["bridgeOk"] else 1
    finally:
        bridge.shutdown_all()


if __name__ == "__main__":
    raise SystemExit(main())
