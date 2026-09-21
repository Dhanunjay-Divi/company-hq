#!/usr/bin/env python3
"""Synthetic JSONL provider for acceptance tests; never loads account credentials."""
import json
import os
from pathlib import Path
import sys
import threading

if os.environ.get('COMPANY_HQ_ACCEPTANCE') != '1':
    raise SystemExit('This fixture only runs inside explicit acceptance tests')
fixture_project = Path(os.environ['HQ_ACCEPTANCE_PROJECT']).resolve(strict=True)
managed_root = Path(os.environ['HQ_ACCEPTANCE_MANAGED_ROOT']).resolve()
project = fixture_project
owned_cwds = {fixture_project}
lock = threading.Lock()
turn = 0
current_turn = ''
pending = None

def emit(message):
    with lock:
        print(json.dumps(message), flush=True)

def completed(text, status='completed'):
    emit({'method':'item/completed','params':{'threadId':'fixture-supervisor','turnId':current_turn,'item':{'id':current_turn+'-reply','type':'agentMessage','text':text}}})
    emit({'method':'thread/tokenUsage/updated','params':{'threadId':'fixture-supervisor','tokenUsage':{'total':{'inputTokens':200*turn,'cachedInputTokens':40*turn,'outputTokens':30*turn,'totalTokens':230*turn}}}})
    emit({'method':'turn/completed','params':{'threadId':'fixture-supervisor','turn':{'id':current_turn,'status':status}}})

def after_start(params):
    global pending
    text = ' '.join(x.get('text','') for x in params.get('input',[]))
    images = [item for item in params.get('input',[]) if item.get('type')=='localImage']
    for item in images:
        content=Path(item['path']).read_bytes()
        assert content.startswith(b'\x89PNG\r\n\x1a\n'), 'Image content did not reach native fixture'
    image_note = f' Received {len(images)} image attachment(s).' if images else ''
    if 'HOLD_FOR_STOP_TEST' in text:
        return
    if params.get('sandboxPolicy',{}).get('type') == 'readOnly':
        if 'LONG_STREAM_TEST' in text:
            for _ in range(600):
                emit({'method':'item/agentMessage/delta','params':{'threadId':'fixture-supervisor','turnId':current_turn,'itemId':current_turn+'-reply','delta':'x'}})
        completed('Synthetic plan: create result.txt only after approval, then verify its exact contents. One small worker is sufficient.' + image_note)
    elif params.get('sandboxPolicy', {}).get('type') == 'workspaceWrite':
        assert params['sandboxPolicy']['writableRoots'] == [str(project)]
        assert params['sandboxPolicy']['networkAccess'] is False
        pending = 'fixture-approval-'+current_turn
        emit({'id':pending,'method':'item/commandExecution/requestApproval','params':{'threadId':'fixture-supervisor','turnId':current_turn,'cwd':str(project),'reason':'Synthetic acceptance write; no network or provider access','command':'write the approved fixture result'}})
    elif params.get('sandboxPolicy', {}).get('type') == 'dangerFullAccess':
        assert params.get('approvalPolicy') == 'never'
        completed('Synthetic full access turn completed without a fixture write.')
    else:
        raise AssertionError(f"Unexpected sandbox policy: {params.get('sandboxPolicy')}")


for line in sys.stdin:
    message = json.loads(line)
    if 'result' in message and message.get('id') == pending:
        if message['result'].get('decision') == 'accept':
            assert project in owned_cwds, f'Fixture may write only its owned cwd: {project}'
            (project/'result.txt').write_text('verified fixture result\n')
            emit({'method':'item/completed','params':{'threadId':'fixture-supervisor','item':{'id':'fixture-child-call','type':'collabAgentToolCall','receiverThreadIds':['fixture-worker-1'],'agentsStates':{'fixture-worker-1':{'status':'completed'}}}}})
            completed('Synthetic execution complete. result.txt contains the verified fixture result. This is simulated-provider evidence, not live model quality.')
        else:
            completed('Synthetic permission declined. No result written.')
        pending = None
        continue
    method, params = message.get('method'), message.get('params',{})
    if method == 'initialize': result = {'userAgent':'company-hq-synthetic-test'}
    elif method == 'account/read': result = {'account':{'type':'chatgpt','email':'private-fixture@example.invalid','planType':'pro'},'requiresOpenaiAuth':True}
    elif method == 'model/list': result = {'data':[{'id':'gpt-6-astra','model':'gpt-6-astra','hidden':False},{'id':'gpt-5.6-luna','model':'gpt-5.6-luna','hidden':False}]}
    elif method == 'account/rateLimits/read': result = {'rateLimitsByLimitId':{'codex':{'limitId':'codex','limitName':'Codex','primary':{'usedPercent':28,'windowDurationMins':300,'resetsAt':1790000000},'secondary':{'usedPercent':61,'windowDurationMins':10080,'resetsAt':1790200000}}}}
    elif method == 'account/login/start': result = {'type':'chatgpt','loginId':'fixture-login','authUrl':'https://auth.openai.com/fixture'}
    elif method == 'account/login/cancel': result = {'status':'canceled'}
    elif method in ('thread/start','thread/resume'):
        candidate = Path(params['cwd']).resolve()
        if candidate.parent == managed_root:
            assert candidate.is_dir()
            owned_cwds.add(candidate)
            project = candidate
        else:
            assert candidate == fixture_project
            project = fixture_project
        result = {'thread':{'id':'fixture-supervisor'}}
    elif method == 'thread/goal/set':
        result = {'goal':{'tokenBudget':params['tokenBudget']}}
    elif method == 'turn/start':
        turn += 1; current_turn = 'fixture-turn-'+str(os.getpid())+'-'+str(turn)
        result = {'turn':{'id':current_turn}}
    elif method == 'turn/steer': result = {'turnId':params['expectedTurnId']}
    elif method == 'turn/interrupt': result = {}
    else: continue
    emit({'id':message['id'],'result':result})
    if method == 'turn/start': threading.Timer(0.15, after_start, args=(params,)).start()
    if method == 'turn/interrupt': completed('Synthetic turn stopped by user.', 'interrupted')
