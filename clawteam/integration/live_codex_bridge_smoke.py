#!/usr/bin/env python3
"""One-turn live smoke test. Run manually; it consumes a small Codex turn."""
from __future__ import annotations

import json
import time
from pathlib import Path

from codex_bridge import CodexBridge

PROJECT = Path(
    "/Users/uno/.local/share/agent-toolkit/fixtures/codex-bridge-luna-20260913"
)
STATE = Path(
    "/Users/uno/.local/share/agent-toolkit/clawteam/verification/"
    "codex-bridge-luna-runtime"
)
TEAM = "bridge-luna-verification-20260913"
RECEIPT = Path(
    "/Users/uno/.local/share/agent-toolkit/clawteam/verification/"
    "codex-bridge-luna-receipt.json"
)


def main() -> int:
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
