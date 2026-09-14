#!/usr/bin/env python3
"""Refresh public upstream metadata only. Never install or activate candidates."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import datetime, json, subprocess
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'docs/repository-candidates.json'
def api(path):
    p = subprocess.run(['gh','api',path],capture_output=True,text=True,timeout=40)
    if p.returncode: raise RuntimeError(p.stderr.strip()[:250])
    return json.loads(p.stdout)
def inspect(entry):
    entry = dict(entry)
    try:
        d=api('repos/'+entry['repo']); branch=d['default_branch']
        commit=api('repos/'+d['full_name']+'/commits/'+branch)
        entry['metadata']={'canonical_repo':d['full_name'],'url':d['html_url'],'description':d.get('description'),'archived':d['archived'],'license_spdx':(d.get('license') or {}).get('spdx_id'),'default_branch':branch,'observed_head':commit['sha'],'pushed_at':d['pushed_at']}
        entry.pop('metadata_error',None)
    except Exception as e: entry['metadata_error']=str(e)
    return entry
if __name__=='__main__':
    data=json.loads(CATALOG.read_text())
    with ThreadPoolExecutor(max_workers=4) as pool: data['repositories']=list(pool.map(inspect,data['repositories']))
    data['metadata_checked_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    CATALOG.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'repositories':len(data['repositories']),'metadata_errors':sum('metadata_error' in r for r in data['repositories'])}))
