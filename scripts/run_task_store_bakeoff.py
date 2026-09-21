#!/usr/bin/env python3
"""Model-free task-store bakeoff for Beads in external-state mode."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, env, timeout=60):
    started = time.perf_counter()
    p = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        timeout=timeout, check=False,
    )
    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "seconds": round(time.perf_counter() - started, 3),
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def json_value(result):
    text = result["stdout"].strip()
    return json.loads(text) if text else None


def main() -> int:
    exe = os.environ.get("BAKEOFF_BEADS")
    if not exe:
        print(json.dumps({"available": False, "reason": "BAKEOFF_BEADS not configured"}, indent=2))
        return 2

    with tempfile.TemporaryDirectory(prefix="company-hq-beads-") as td:
        base = Path(td)
        workspace = base / "workspace"
        state = base / "state" / "beads"
        workspace.mkdir(parents=True)
        state.parent.mkdir(parents=True)
        env = os.environ.copy()
        env.update({
            "BEADS_DIR": str(state),
            "BD_NON_INTERACTIVE": "1",
            "CI": "true",
        })

        init = run([
            exe, "init", "--quiet", "--non-interactive", "--skip-agents",
            "--skip-hooks", "--prefix", "hq"
        ], cwd=workspace, env=env, timeout=120)
        if not init["ok"]:
            print(json.dumps({"available": True, "init": init}, indent=2))
            return 1

        created = {}
        for issue_id, title in [
            ("hq-plan", "Plan feature"),
            ("hq-build", "Build feature"),
            ("hq-review", "Review feature"),
        ]:
            result = run([
                exe, "create", title, "--id", issue_id, "--type", "task",
                "--priority", "1", "--json"
            ], cwd=workspace, env=env)
            created[issue_id] = result

        deps = [
            run([exe, "dep", "add", "hq-build", "hq-plan"], cwd=workspace, env=env),
            run([exe, "dep", "add", "hq-review", "hq-build"], cwd=workspace, env=env),
        ]
        ready_before = run([exe, "ready", "--json"], cwd=workspace, env=env)
        ready_before_data = json_value(ready_before) or []
        ready_before_ids = [x.get("id") for x in ready_before_data if isinstance(x, dict)]

        claim = run([exe, "update", "hq-plan", "--claim", "--json"], cwd=workspace, env=env)
        close_plan = run([exe, "close", "hq-plan", "Planned", "--json"], cwd=workspace, env=env)
        ready_after_plan = run([exe, "ready", "--json"], cwd=workspace, env=env)
        ready_after_plan_data = json_value(ready_after_plan) or []
        ready_after_plan_ids = [x.get("id") for x in ready_after_plan_data if isinstance(x, dict)]

        close_build = run([exe, "close", "hq-build", "Built", "--json"], cwd=workspace, env=env)
        ready_after_build = run([exe, "ready", "--json"], cwd=workspace, env=env)
        ready_after_build_data = json_value(ready_after_build) or []
        ready_after_build_ids = [x.get("id") for x in ready_after_build_data if isinstance(x, dict)]

        cycle = run([exe, "dep", "add", "hq-plan", "hq-review"], cwd=workspace, env=env)
        list_all = run([exe, "list", "--json"], cwd=workspace, env=env)
        workspace_files = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*"))

        results = {
            "schema": 1,
            "beads": {
                "version": "1.3.0",
                "init_ok": init["ok"],
                "creates_ok": all(v["ok"] for v in created.values()),
                "deps_ok": all(v["ok"] for v in deps),
                "ready_before": ready_before_ids,
                "claim_ok": claim["ok"],
                "ready_after_plan": ready_after_plan_ids,
                "ready_after_build": ready_after_build_ids,
                "cycle_rejected": not cycle["ok"],
                "cycle_error_excerpt": (cycle["stdout"] + cycle["stderr"])[-1000:],
                "workspace_pollution": workspace_files,
                "state_exists": state.exists(),
                "timings_seconds": {
                    "init": init["seconds"],
                    "create_total": round(sum(v["seconds"] for v in created.values()), 3),
                    "ready": ready_before["seconds"],
                    "claim": claim["seconds"],
                },
                "list_output_bytes": len((list_all["stdout"] + list_all["stderr"]).encode()),
            },
        }
        results["beads"]["semantic_pass"] = (
            results["beads"]["creates_ok"]
            and results["beads"]["deps_ok"]
            and ready_before_ids == ["hq-plan"]
            and claim["ok"]
            and ready_after_plan_ids == ["hq-build"]
            and ready_after_build_ids == ["hq-review"]
            and results["beads"]["cycle_rejected"]
            and workspace_files == []
        )

    output = ROOT / "benchmarks" / "task-store-results.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if results["beads"]["semantic_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
