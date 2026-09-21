"""Real browser + HTTP API + synthetic JSONL process. No real model calls."""
from pathlib import Path
import base64
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
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLJ7wAAAABJRU5ErkJggg==')


def provider_payload(*, five_hour=28, weekly=61, include_five_hour=True):
    windows = []
    if include_five_hour:
        windows.append({'id': 'five-hour', 'usedPercent': five_hour, 'windowDurationMins': 300, 'resetsAt': 1790000000})
    windows.append({'id': 'weekly', 'usedPercent': weekly, 'windowDurationMins': 10080, 'resetsAt': 1790200000})
    return {'checkedAt': '2026-09-21T12:00:00Z', 'providers': [
        {'id': 'codex', 'label': 'Codex', 'installed': True, 'cliInstalled': True, 'runtimeReady': True,
         'authentication': 'signed_in', 'usageWindows': windows, 'models': ['gpt-6-astra']},
        {'id': 'claude', 'label': 'Claude', 'installed': True, 'desktopInstalled': True, 'runtimeReady': False,
         'authentication': 'not_checked', 'reason': 'Desktop application detected; HQ adapter unavailable.'},
    ]}


with tempfile.TemporaryDirectory(prefix='hq-browser-') as td:
    base = Path(td)
    project = base / 'project'
    project.mkdir()
    original = project / 'README.md'
    original.write_text('Acceptance fixture only\n')
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    fake = ROOT / 'tests/acceptance/fake_codex.py'
    fake.chmod(0o700)
    env = os.environ.copy()
    env.update(COMPANY_HQ_STATE_ROOT=str(base / 'state'), COMPANY_HQ_CODEX_PATH=str(fake),
               COMPANY_HQ_ACCEPTANCE='1', HQ_ACCEPTANCE_PROJECT=str(project),
               HQ_ACCEPTANCE_MANAGED_ROOT=str(base / 'state' / 'clawteam' / 'managed-workspaces'),
               PATH=str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', ''))
    env.pop('COMPANY_HQ_DEMO', None)
    log = (OUT / 'browser-server.txt').open('w')
    server = subprocess.Popen([sys.executable, str(ROOT / 'clawteam/integration/secure_board.py'), '--port', '0'], env=env, stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 15
        url = ''
        while time.monotonic() < deadline:
            match = re.search(r'http://127\.0\.0\.1:\d+', (OUT / 'browser-server.txt').read_text())
            if match:
                url = match.group(0)
                break
            if server.poll() is not None:
                raise RuntimeError((OUT / 'browser-server.txt').read_text())
            time.sleep(.1)
        assert url, 'Server did not publish a loopback address'

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.on('pageerror', lambda e: errors.append(str(e)))
            providers = provider_payload()
            opened = []
            picker_results = [{'cancelled': True, 'path': ''}, {'cancelled': False, 'path': str(project)}]

            def provider_route(route):
                if route.request.method == 'GET':
                    route.fulfill(content_type='application/json', body=json.dumps(providers))
                elif route.request.url.endswith('/codex/check'):
                    route.fulfill(content_type='application/json', body=json.dumps(providers['providers'][0]))
                elif route.request.url.endswith('/claude/open'):
                    opened.append(route.request.url)
                    route.fulfill(content_type='application/json', body=json.dumps({'message': 'Provider app opened.', 'desktopInstalled': True, 'runtimeReady': False}))
                else:
                    route.continue_()

            def picker_route(route):
                assert route.request.method == 'POST'
                assert route.request.post_data_json == {}
                route.fulfill(content_type='application/json', body=json.dumps(picker_results.pop(0)))

            page.route('**/api/providers**', provider_route)
            page.route('**/api/folders/pick', picker_route)
            page.goto(url)
            expect(page.get_by_role('heading', name='What are we making today?')).to_be_visible()
            expect(page.get_by_label('Direction for the team')).to_be_visible()
            expect(page.get_by_label('Work mode')).to_have_value('auto')
            assert page.locator('.traffic-lights').count() == 0, 'Duplicate fake window controls'
            page.screenshot(path=str(OUT / 'chat-home.png'), full_page=True, animations='disabled')

            page.get_by_role('button', name='Settings', exact=True).click()
            expect(page.get_by_role('heading', name='Connections and allowance')).to_be_visible()
            expect(page.get_by_text('5-hour account allowance', exact=False)).to_be_visible()
            expect(page.get_by_text('72% remaining', exact=True)).to_be_visible()
            expect(page.get_by_text('Weekly account allowance', exact=False)).to_be_visible()
            expect(page.get_by_text('39% remaining', exact=True)).to_be_visible()
            visible_text = page.locator('body').inner_text()
            assert 'private-fixture@example.invalid' not in visible_text
            assert 'API key' not in visible_text
            page.get_by_role('button', name=re.compile('Codex')).last.click()
            expect(page.get_by_role('dialog')).to_be_visible()
            expect(page.get_by_role('dialog').get_by_text('Signed in', exact=True)).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.get_by_role('dialog')).not_to_be_visible()
            page.get_by_role('button', name=re.compile('Codex')).last.click()
            page.get_by_label('Close provider details').click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            page.get_by_role('button', name=re.compile('Claude')).last.click()
            expect(page.get_by_text('HQ execution adapter unavailable', exact=True)).to_be_visible()
            page.get_by_role('button', name='Open provider app', exact=True).click()
            page.wait_for_timeout(100)
            assert len(opened) == 1, opened
            page.get_by_label('Close provider details').click()

            # Window values are separate: an overspent 5-hour window does not affect weekly remaining.
            providers = provider_payload(five_hour=125, weekly=59, include_five_hour=False)
            page.get_by_role('button', name='Check again', exact=True).click()
            expect(page.get_by_text('5-hour account allowance', exact=True)).to_be_visible()
            expect(page.get_by_text('Not reported', exact=True).first).to_be_visible()
            expect(page.get_by_text('41% remaining', exact=True)).to_be_visible()
            assert '0% remaining' not in page.locator('body').inner_text(), 'missing 5-hour must stay unknown'
            providers = provider_payload(five_hour=125, weekly=59)
            page.get_by_role('button', name='Check again', exact=True).click()
            expect(page.get_by_text('0% remaining', exact=True)).to_be_visible()
            expect(page.get_by_text(re.compile(r'125% used'))).to_be_visible()
            expect(page.get_by_text('41% remaining', exact=True)).to_be_visible()
            page.screenshot(path=str(OUT / 'settings.png'), full_page=True, animations='disabled')

            # Folder picking is optional and cancellation leaves the first-message draft intact.
            page.get_by_role('button', name='Chat', exact=True).click()
            page.get_by_role('button', name='Add project', exact=True).click()
            page.get_by_label('First message (optional)', exact=True).fill('Synthetic plan to approved fixture result')
            page.get_by_role('button', name='Choose folder…', exact=True).click()
            expect(page.locator('input[name=project]')).to_have_value('')
            expect(page.get_by_label('First message (optional)', exact=True)).to_have_value('Synthetic plan to approved fixture result')
            page.get_by_role('button', name='Choose folder…', exact=True).click()
            expect(page.locator('input[name=project]')).to_have_value(str(project))
            page.get_by_label('Chat name (optional)', exact=True).fill('Acceptance fixture')
            page.get_by_role('button', name='Connect project', exact=True).click()
            expect(page.get_by_role('dialog')).not_to_be_visible()

            # Switching from a budget dialog to a project dialog clears uncontrolled form values.
            page.get_by_role('button', name='Activity', exact=True).click()
            expect(page.get_by_text('Usage and budget signal', exact=True)).to_be_visible()
            page.get_by_role('button', name='Set budget', exact=True).click()
            page.get_by_label('Chat allowance (tokens)', exact=True).fill('1000000')
            page.get_by_label('Close dialog').click()
            page.get_by_role('button', name='Chat', exact=True).click()
            page.get_by_role('button', name='Project attached', exact=True).click()
            expect(page.get_by_label('Chat name (optional)', exact=True)).to_have_value('')
            page.get_by_label('Close dialog').click()
            page.get_by_role('button', name='Activity', exact=True).click()
            page.get_by_role('button', name='Set budget', exact=True).click()
            page.get_by_label('Chat allowance (tokens)', exact=True).fill('1000000')
            page.get_by_role('button', name='Save budget', exact=True).click()
            expect(page.get_by_text(re.compile(r'1,000,000 reported tokens'))).to_be_visible()
            page.get_by_role('button', name='Chat', exact=True).click()

            # Legacy plan-first remains an explicit choice, with both plan and native write approvals.
            page.get_by_label('Work mode').select_option('plan')
            page.get_by_role('button', name='Choose model', exact=True).click()
            page.get_by_role('button', name=re.compile('GPT 5.6 Luna')).click()
            page.locator('input[type=file]').set_input_files({'name': 'fixture.png', 'mimeType': 'image/png', 'buffer': PNG})
            expect(page.get_by_role('img', name='fixture.png')).to_be_visible()
            page.get_by_label('Direction for the team').fill('Plan the fixture change; no writes before approval.')
            page.get_by_role('button', name='Send message', exact=True).click()
            approve_plan = page.get_by_role('button', name='Approve plan & start execution', exact=True)
            expect(approve_plan).to_be_visible(timeout=15000)
            assert not (project / 'result.txt').exists(), 'Planning wrote a result'
            approve_plan.click()
            expect(page.get_by_role('button', name='Approve once', exact=True)).to_be_visible(timeout=15000)
            page.get_by_role('button', name='Approve once', exact=True).click()
            expect(page.get_by_text('Synthetic execution complete', exact=False)).to_be_visible(timeout=15000)
            assert (project / 'result.txt').read_text() == 'verified fixture result\n'
            assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
            image = page.get_by_role('img', name='fixture.png').last
            image_url = image.get_attribute('src')
            assert image_url and image_url.startswith(url + '/api/attachments/'), image_url
            page.reload()
            page.get_by_role('button', name='Acceptance fixture', exact=True).click()
            expect(page.get_by_role('img', name='fixture.png')).to_be_visible(timeout=15000)
            assert urllib.request.urlopen(image_url, timeout=5).read() == PNG

            # Full access is an explicit new-chat selection, persisted as full and sent as native dangerFullAccess.
            page.get_by_role('button', name='New chat', exact=False).click()
            expect(page.get_by_label('Work mode')).to_have_value('plan')
            page.get_by_label('Work mode').select_option('full')
            page.get_by_label('Direction for the team').fill('Full access fixture: transport contract only.')
            page.get_by_role('button', name='Send message', exact=True).click()
            assert page.get_by_role('button', name='Approve plan & start execution', exact=True).count() == 0
            expect(page.locator('.chat-message.assistant').last).to_contain_text('Synthetic full access turn completed without a fixture write.', timeout=15000)
            full_chats = json.loads(urllib.request.urlopen(url + '/api/overview', timeout=5).read())
            full_team = next(chat['name'] for chat in full_chats if chat.get('name', '').startswith('full-access-fixture'))
            full_status = json.loads(urllib.request.urlopen(url + '/api/runtime/' + full_team + '/status', timeout=5).read())
            assert full_status['accessMode'] == 'full', full_status
            assert full_status['mode'] == 'execute', full_status
            assert page.get_by_role('button', name='Decline', exact=True).count() == 0

            # A fresh folderless chat defaults to automatic work: it reaches native approval directly.
            page.get_by_role('button', name='New chat', exact=False).click()
            expect(page.get_by_label('Work mode')).to_have_value('full')
            page.get_by_label('Work mode').select_option('auto')
            page.get_by_label('Direction for the team').fill('Auto mode fixture: request a safe write.')
            page.get_by_role('button', name='Send message', exact=True).click()
            assert page.get_by_role('button', name='Approve plan & start execution', exact=True).count() == 0
            decline = page.get_by_role('button', name='Decline', exact=True)
            expect(decline).to_be_visible(timeout=15000)
            decline.click()
            page.wait_for_timeout(1200)
            assert 'Synthetic permission declined. No result written.' in page.locator('body').inner_text()
            chats = json.loads(urllib.request.urlopen(url + '/api/overview', timeout=5).read())
            managed = [(chat, json.loads(urllib.request.urlopen(url + '/api/company/' + chat['name'], timeout=5).read())) for chat in chats]
            managed = [(chat, profile) for chat, profile in managed if profile.get('workspaceKind') == 'managed']
            assert len(managed) == 2, managed
            for _, profile in managed:
                scratch = Path(profile['projectRoot'])
                assert scratch.is_relative_to((base / 'state').resolve()), scratch
                assert not list(scratch.iterdir()), 'Synthetic managed chat changed scratch files'

            page.get_by_role('button', name='New chat', exact=False).click()
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.get_by_label('Direction for the team')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page-level horizontal overflow'
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.orb-body').evaluate("el=>getComputedStyle(el).animationName") == 'none'
            page.get_by_role('button', name='Open navigation', exact=True).click()
            expect(page.get_by_role('button', name='Settings', exact=True)).to_be_visible()
            page.get_by_role('button', name='Dismiss navigation', exact=True).click()
            browser.close()

        assert not errors, errors
        (OUT / 'browser-result.json').write_text(json.dumps({
            'passed': True,
            'transport': 'synthetic JSONL fixture, not a live provider',
            'checks': ['connections and separate account windows', 'provider dialog close and desktop open route',
                       'folder picker cancel/chosen path and draft preservation', 'image preview, replay, and byte-preserving attachment read', 'budget dialog reset',
                       'explicit plan-first approvals', 'full-access native transport contract', 'folderless automatic native approval and decline',
                       'managed scratch isolation', 'desktop and narrow layout'],
            'page_errors': errors,
        }, indent=2))
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        log.close()
