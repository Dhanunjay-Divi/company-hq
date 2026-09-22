#!/usr/bin/env python3
"""Capture a command once, then privately retain its evidence for Company HQ recall."""
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'clawteam' / 'integration'))
from context_pipeline import ContextPipeline

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--state-root', required=True, type=Path); p.add_argument('--team', required=True); p.add_argument('--project', required=True, type=Path); p.add_argument('command', nargs=argparse.REMAINDER)
    a=p.parse_args(); command=a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command: p.error('command is required after --')
    run=subprocess.run(command, cwd=a.project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    pipe=ContextPipeline(a.state_root, rtk_path=Path(__file__).resolve().parents[1] / 'build/tools/rtk')
    record=pipe.record(a.team, a.project, {'command':command,'stdout':run.stdout,'stderr':run.stderr,'exit_code':run.returncode})
    print(f'Evidence {record.id}; raw recall is available through the scoped evidence API.', file=sys.stderr)
    if record.compact is not None: sys.stdout.write(record.compact)
    else: sys.stdout.write(run.stdout); sys.stderr.write(run.stderr)
    return run.returncode
if __name__ == '__main__': raise SystemExit(main())
