"""Real browser + HTTP API + synthetic JSONL process. No real model calls."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['HQ_EVIDENCE_DIR']).resolve()
OUT.mkdir(parents=True, exist_ok=True)
errors = []
with tempfile.TemporaryDirectory(prefix='hq-browser-') as td:
    base = Path(td); project = base/'project'; project.mkdir()
    original = project/'README.md'; original.write_text('Acceptance fixture only\n')
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    fake = ROOT/'tests/acceptance/fake_codex.py'; fake.chmod(0o700)
    env = os.environ.copy()
    env.update(COMPANY_HQ_STATE_ROOT=str(base/'state'), COMPANY_HQ_CODEX_PATH=str(fake),
               COMPANY_HQ_ACCEPTANCE='1', HQ_ACCEPTANCE_PROJECT=str(project),
               PATH=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH',''))
    env.pop('COMPANY_HQ_DEMO',None)
    log = (OUT/'browser-server.txt').open('w')
    server = subprocess.Popen([sys.executable,str(ROOT/'clawteam/integration/secure_board.py'),'--port','0'],env=env,stdout=log,stderr=log)
    try:
        deadline = time.monotonic()+15; url = ''
        while time.monotonic() < deadline:
            text = (OUT/'browser-server.txt').read_text()
            match = re.search(r'http://127\.0\.0\.1:\d+', text)
            if match: url = match.group(0); break
            if server.poll() is not None: raise RuntimeError(text)
            time.sleep(0.1)
        assert url, 'Server did not publish a loopback address'
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url)
            page.get_by_role('button',name='+ Connect project',exact=True).click()
            page.get_by_label('Workspace name',exact=True).fill('Acceptance fixture')
            page.get_by_label('Project folder',exact=True).fill(str(project))
            page.get_by_label('Desired outcome',exact=True).fill('Synthetic plan to approved fixture result')
            page.get_by_role('button',name='Connect workspace',exact=True).click()
            expect(page.get_by_role('heading',name='Your project, step by step')).to_be_visible()
            page.get_by_label('Supervisor model').select_option('gpt-5.6-luna')
            page.get_by_label('Direction for the team').fill('Plan the fixture change; no writes before approval.')
            page.get_by_role('button',name='Discuss & plan',exact=True).click()
            approve = page.get_by_role('button',name='Approve plan & start execution',exact=True)
            expect(approve).to_be_visible(timeout=15000)
            assert not (project/'result.txt').exists(), 'Planning wrote a result'
            page.screenshot(path=str(OUT/'desktop-plan.png'),full_page=True)
            approve.click()
            once = page.get_by_role('button',name='Approve once',exact=True)
            expect(once).to_be_visible(timeout=15000)
            assert not (project/'result.txt').exists(), 'Execution bypassed explicit permission'
            once.click()
            expect(page.get_by_text('fixture-worker-1',exact=True)).to_be_visible(timeout=15000)
            assert (project/'result.txt').read_text() == 'verified fixture result\n'
            assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
            page.get_by_role('button',name='Close conversation',exact=True).click()
            page.screenshot(path=str(OUT/'desktop-result.png'),full_page=True)
            page.get_by_label('Direction for the team').fill('HOLD_FOR_STOP_TEST')
            page.get_by_role('button',name='Continue execution',exact=True).click()
            stop = page.get_by_role('button',name='Stop',exact=True)
            expect(stop).to_be_visible(timeout=15000); stop.click()
            expect(stop).not_to_be_visible(timeout=15000)
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='Close conversation',exact=True).click()
            expect(page.get_by_role('heading',name='Your project, step by step')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page-level horizontal overflow'
            page.screenshot(path=str(OUT/'narrow-result.png'),full_page=True)
            browser.close()
        assert not errors, errors
        (OUT/'browser-result.json').write_text(json.dumps({'passed':True,'transport':'synthetic JSONL fixture, not a live provider','checks':['connect','read-only plan','separate execution approval','permission approval','observed child ID','result file','source unchanged','stop','desktop','narrow no page overflow'],'page_errors':errors},indent=2))
    finally:
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill();server.wait(timeout=5)
        log.close()
