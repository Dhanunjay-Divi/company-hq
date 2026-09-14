#!/usr/bin/env python3
"""Check tracked source for accidental private/runtime artifacts; no values printed."""
from pathlib import Path
import json, re, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS={'.git','node_modules','deps','venv','.venv','__pycache__','state','runs','bindings','logs','backups','dist'}
FORBIDDEN_NAMES={'auth.json','config.toml','saved-projects.json','capabilities.json','upstream-status.json','pinky-before.json','product-integrity.json','managed-default.json','ui-execution-receipt.json'}
SECRET_PATTERNS=[re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
def main():
    p=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    names=[x.decode() for x in p.stdout.split(b'\0') if x]
    errors=[]
    for name in names:
        rel=Path(name);path=ROOT/rel
        if set(rel.parts)&FORBIDDEN_PARTS or rel.name in FORBIDDEN_NAMES or rel.name.startswith('.env') and rel.name!='.env.example':errors.append((name,'forbidden path'))
        if path.is_symlink():errors.append((name,'symlink'));continue
        if not path.is_file():errors.append((name,'missing file'));continue
        if path.suffix in {'.db','.sqlite','.sqlite3','.dmg','.pyc','.zip'}:errors.append((name,'generated/private artifact'))
        data=path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):errors.append((name,'credential-like content'))
    print(json.dumps({'tracked_files':len(names),'findings':[{'path':n,'reason':why} for n,why in errors]}))
    return 1 if errors else 0
if __name__=='__main__':sys.exit(main())
