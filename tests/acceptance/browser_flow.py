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
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('HQ_EVIDENCE_DIR') or tempfile.mkdtemp(prefix='hq-evidence-')).resolve()
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
               HQ_ACCEPTANCE_MANAGED_ROOT=str(base/'state'/'clawteam'/'managed-workspaces'),
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
            expect(page.get_by_role('heading',name='What are we making today?')).to_be_visible()
            expect(page.get_by_label('Direction for the team')).to_be_visible()
            assert page.locator('.traffic-lights').count()==0, 'Duplicate fake window controls'
            page.screenshot(path=str(OUT/'chat-home.png'),full_page=True,animations='disabled')
            page.get_by_role('button',name='Settings',exact=True).click()
            expect(page.get_by_role('heading',name='Your workspace, connected.')).to_be_visible()
            page.screenshot(path=str(OUT/'settings.png'),full_page=True,animations='disabled')
            def failed_health(route): route.fulfill(status=503,content_type='application/json',body='{"error":"Fixture setup check unavailable"}')
            page.route('**/api/health',failed_health)
            page.get_by_role('button',name='Check again',exact=True).click()
            expect(page.get_by_role('alert')).to_have_text('Fixture setup check unavailable')
            page.unroute('**/api/health',failed_health)
            page.get_by_role('button',name='Check again',exact=True).click()
            expect(page.get_by_role('alert')).not_to_be_visible()
            page.get_by_role('button',name='Chat',exact=True).click()
            page.get_by_role('button',name='Add project',exact=True).click()
            page.get_by_label('Chat name (optional)',exact=True).fill('Acceptance fixture')
            page.get_by_label('Project folder',exact=True).fill(str(project))
            page.get_by_label('First message (optional)',exact=True).fill('Synthetic plan to approved fixture result')
            page.get_by_role('button',name='Connect project',exact=True).click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            page.get_by_role('button',name='Activity',exact=True).click()
            expect(page.get_by_text('Usage and budget signal',exact=True)).to_be_visible()
            page.get_by_role('button',name='Set budget',exact=True).click()
            page.get_by_label('Token ceiling',exact=True).fill('1000000')
            page.get_by_role('button',name='Save budget',exact=True).click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            expect(page.get_by_text('1,000,000',exact=True)).to_be_visible()
            page.get_by_role('button',name='How to use',exact=True).click()
            expect(page.get_by_role('heading',name='Use it like a small operating company beside your IDE')).to_be_visible()
            expect(page.get_by_text('Python now, Rust where it wins',exact=True)).to_be_visible()
            page.get_by_text('More tools',exact=True).click()
            page.get_by_role('button',name='Why this stack',exact=True).click()
            expect(page.get_by_role('heading',name='Evidence before adoption')).to_be_visible()
            expect(page.get_by_text('Top-40 catalog',exact=True)).to_be_visible()
            expect(page.get_by_text('777genius/agent-teams-ai',exact=True)).to_be_visible()
            page.get_by_role('button',name='Chat',exact=True).click()
            page.get_by_role('button',name='Choose model',exact=True).click()
            page.get_by_role('button',name=re.compile('GPT 5.6 Luna')).click()
            health = page.request.get(url+'/api/health').json()
            (OUT/'browser-health.json').write_text(json.dumps(health,indent=2))
            assert health['capabilities']['codex']['available'], health
            page.get_by_label('Direction for the team').fill('Plan the fixture change; no writes before approval.')
            expect(page.get_by_label('Direction for the team')).to_have_value('Plan the fixture change; no writes before approval.')
            page.screenshot(path=str(OUT/'before-plan.png'),full_page=True,animations='disabled')
            page.get_by_role('button',name='Send message',exact=True).click()
            approve = page.get_by_role('button',name='Approve plan & start execution',exact=True)
            expect(approve).to_be_visible(timeout=15000)
            assert not (project/'result.txt').exists(), 'Planning wrote a result'
            page.screenshot(path=str(OUT/'desktop-plan.png'),full_page=True,animations='disabled')
            approve.click()
            once = page.get_by_role('button',name='Approve once',exact=True)
            expect(once).to_be_visible(timeout=15000)
            assert not (project/'result.txt').exists(), 'Execution bypassed explicit permission'
            once.click()
            page.get_by_role('button',name='Toggle activity panel',exact=True).click()
            expect(page.get_by_text('fixture-worker-1',exact=True)).to_be_visible(timeout=15000)
            assert (project/'result.txt').read_text() == 'verified fixture result\n'
            assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
            page.get_by_role('button',name='Close activity',exact=True).click()
            page.screenshot(path=str(OUT/'desktop-result.png'),full_page=True,animations='disabled')
            page.get_by_label('Direction for the team').fill('HOLD_FOR_STOP_TEST')
            page.get_by_role('button',name='Send message',exact=True).click()
            stop = page.get_by_role('button',name='Stop',exact=True)
            expect(stop).to_be_visible(timeout=15000); stop.click()
            expect(stop).not_to_be_visible(timeout=15000)
            page.set_viewport_size({'width':390,'height':844})
            expect(page.get_by_label('Direction for the team')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page-level horizontal overflow'
            page.screenshot(path=str(OUT/'narrow-result.png'),full_page=True,animations='disabled')
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_role('button',name='New chat',exact=False).click()
            expect(page.get_by_role('heading',name='What are we making today?')).to_be_visible()
            page.get_by_label('Direction for the team').fill('Help me plan a useful small business without choosing a folder.')
            page.get_by_role('button',name='Send message',exact=True).click()
            expect(page.locator('.chat-message.user')).to_have_text('Help me plan a useful small business without choosing a folder.',timeout=15000)
            expect(page.locator('.chat-message.assistant')).to_contain_text('Synthetic plan',timeout=15000)
            chats=page.request.get(url+'/api/overview').json()
            managed=[]
            for chat in chats:
                profile=page.request.get(url+'/api/company/'+chat['name']).json()
                if profile.get('workspaceKind')=='managed':managed.append((chat,profile))
            assert len(managed)==1, managed
            managed_root=Path(managed[0][1]['projectRoot'])
            assert managed_root.is_relative_to((base/'state').resolve()), managed_root
            assert not list(managed_root.iterdir()), 'Planning changed the scratch directory'
            managed_status=page.request.get(url+'/api/runtime/'+managed[0][0]['name']+'/status').json()
            assert managed_status['model']=='gpt-6-astra', managed_status
            page.screenshot(path=str(OUT/'folderless-conversation.png'),full_page=True,animations='disabled')
            page.reload()
            expect(page.get_by_role('heading',name='What are we making today?')).to_be_visible()
            page.get_by_role('button',name='Help me plan a useful small business without choosing a folder.',exact=True).click()
            expect(page.locator('.chat-message.assistant')).to_contain_text('Synthetic plan',timeout=15000)
            page.get_by_role('button',name='New chat',exact=False).click()
            page.get_by_label('Direction for the team').fill('Draft kept when changing chats')
            page.get_by_role('button',name='Acceptance fixture',exact=True).click()
            page.get_by_role('button',name='New chat',exact=False).click()
            expect(page.get_by_label('Direction for the team')).to_have_value('Draft kept when changing chats')
            # Delay first-send creation, then navigate away: completion must not hijack the current chat.
            held=[]
            def hold_workspace(route):
                if route.request.method=='POST': held.append(route)
                else: route.continue_()
            page.route('**/api/workspaces',hold_workspace)
            page.get_by_label('Direction for the team').fill('Delayed background chat test')
            page.get_by_role('button',name='Send message',exact=True).click()
            page.get_by_role('button',name='Acceptance fixture',exact=True).click()
            assert held, 'Workspace POST was not intercepted'
            held[0].continue_()
            expect(page.get_by_role('button',name='Delayed background chat test',exact=True)).to_be_visible(timeout=15000)
            expect(page.locator('.chat-title b')).to_have_text('Acceptance fixture')
            page.unroute('**/api/workspaces',hold_workspace)
            page.get_by_role('button',name='New chat',exact=False).click()
            page.set_viewport_size({'width':390,'height':844})
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.orb-body').evaluate("el=>getComputedStyle(el).animationName")=='none'
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(OUT/'chat-home-narrow.png'),full_page=True,animations='disabled')
            page.get_by_role('button',name='Open navigation',exact=True).click()
            expect(page.get_by_role('button',name='Settings',exact=True)).to_be_visible()
            page.get_by_role('button',name='Dismiss navigation',exact=True).click()
            expect(page.get_by_role('button',name='Settings',exact=True)).not_to_be_in_viewport()
            # Restart the actual HTTP server against the same private state and resume its saved native binding.
            server.terminate(); server.wait(timeout=5)
            port=url.rsplit(':',1)[1]
            server=subprocess.Popen([sys.executable,str(ROOT/'clawteam/integration/secure_board.py'),'--port',port],env=env,stdout=log,stderr=log)
            restart_deadline=time.monotonic()+10
            while True:
                try:
                    with urllib.request.urlopen(url+'/api/health',timeout=1):break
                except Exception:
                    if time.monotonic()>restart_deadline:raise
                    time.sleep(.05)
            page.set_viewport_size({'width':1440,'height':1000})
            page.reload()
            page.get_by_role('button',name='Help me plan a useful small business without choosing a folder.',exact=True).click()
            expect(page.locator('.chat-message.user')).to_have_text('Help me plan a useful small business without choosing a folder.',timeout=15000)
            expect(page.locator('.chat-message.assistant')).to_have_count(1)
            page.screenshot(path=str(OUT/'restarted-chat.png'),full_page=True,animations='disabled')
            page.get_by_label('Direction for the team').fill('Continue the saved plan without writing files.')
            page.get_by_role('button',name='Send message',exact=True).click()
            expect(page.locator('.chat-message.assistant')).to_have_count(2,timeout=15000)
            expect(page.locator('.chat-message.user')).to_have_count(2)
            page.get_by_label('Direction for the team').fill('LONG_STREAM_TEST: keep earlier questions visible.')
            page.get_by_role('button',name='Send message',exact=True).click()
            expect(page.locator('.chat-message.assistant')).to_have_count(3,timeout=15000)
            expect(page.locator('.chat-message.assistant').last).to_contain_text('Synthetic plan',timeout=15000)
            expect(page.locator('.chat-message.user')).to_have_count(3)
            expect(page.locator('.chat-message.user').first).to_have_text('Help me plan a useful small business without choosing a folder.')
            browser.close()
        assert not errors, errors
        (OUT/'browser-result.json').write_text(json.dumps({'passed':True,'transport':'synthetic JSONL fixture, not a live provider','checks':['connect','read-only plan','separate execution approval','permission approval','observed child ID','result file','source unchanged','stop','desktop','narrow no page overflow','folderless first-send','auto flagship supervisor','conversation replay on page reload','per-chat drafts','reduced motion','mobile navigation','background first-send preserves navigation','server restart transcript replay','native resume without duplicate messages'],'page_errors':errors},indent=2))
    finally:
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill();server.wait(timeout=5)
        log.close()
