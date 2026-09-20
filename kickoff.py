#!/usr/bin/env python3
"""Refresh shared tool/model metadata at project kickoff, without initializing the repo."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from discover import BASE, discover


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    project=Path(args.project).expanduser().resolve(strict=True)
    if not project.is_dir():parser.error('Project must be an existing directory')
    caps=discover(args.refresh)
    command=[sys.executable,'-B',str(BASE/'check_updates.py')]
    if args.refresh:command.append('--refresh')
    checked=subprocess.run(command,capture_output=True,text=True,timeout=35)
    try:
        report=json.loads(checked.stdout)
        candidates=[{'repo':r['repo'],'latest_release':r.get('latest_release'),
                     'source_changed':r.get('source_changed_since_review')}
                    for r in report['repositories'] if r.get('source_changed_since_review') or not r.get('reviewed_ref')]
    except (ValueError,KeyError): candidates=[]
    selected=caps['selection']
    # Company HQ routes each task itself. Do not rewrite the user's global Codex
    # model/effort defaults as a side effect of project kickoff.
    sync='global provider default preserved; Company HQ routes per task'
    print(json.dumps({'project':str(project),'supervisor':selected,'model_cache_used':caps['cached'],
          'codex_default_sync':sync,'new_models_for_review':caps['unreviewed_codex_models'],
          'upstream_check':'ok' if checked.returncode==0 else 'partial/unavailable',
          'upstream_candidates':candidates,
          'teams':'Use bounded native teams when independent work merits them; this command launches no workers.',
          'updates':'Relevant candidates are reviewed, staged and tested before automatic activation. No product initializer runs.'},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
