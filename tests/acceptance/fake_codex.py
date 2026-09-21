#!/usr/bin/env python3
"""Synthetic JSONL provider for acceptance tests; never loads account credentials."""
import json
import os
from pathlib import Path
import sys
import threading

if os.environ.get('COMPANY_HQ_ACCEPTANCE') != '1':
    raise SystemExit('This fixture only runs inside explicit acceptance tests')
project = Path(os.environ['HQ_ACCEPTANCE_PROJECT']).resolve(strict=True)
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
    if 'HOLD_FOR_STOP_TEST' in text:
        return
    if params.get('sandboxPolicy',{}).get('type') == 'readOnly':
        completed('Synthetic plan: create result.txt only after approval, then verify its exact contents. One small worker is sufficient.')
    else:
        assert params['sandboxPolicy']['writableRoots'] == [str(project)]
        assert params['sandboxPolicy']['networkAccess'] is False
        pending = 'fixture-approval-'+current_turn
        emit({'id':pending,'method':'item/commandExecution/requestApproval','params':{'threadId':'fixture-supervisor','turnId':current_turn,'cwd':str(project),'reason':'Synthetic acceptance write; no network or provider access','command':'write the approved fixture result'}})

for line in sys.stdin:
    message = json.loads(line)
    if 'result' in message and message.get('id') == pending:
        if message['result'].get('decision') == 'accept':
            (project/'result.txt').write_text('verified fixture result\n')
            emit({'method':'item/completed','params':{'threadId':'fixture-supervisor','item':{'id':'fixture-child-call','type':'collabAgentToolCall','receiverThreadIds':['fixture-worker-1'],'agentsStates':{'fixture-worker-1':{'status':'completed'}}}}})
            completed('Synthetic execution complete. result.txt contains the verified fixture result. This is simulated-provider evidence, not live model quality.')
        else:
            completed('Synthetic permission declined. No result written.')
        pending = None
        continue
    method, params = message.get('method'), message.get('params',{})
    if method == 'initialize': result = {'userAgent':'company-hq-synthetic-test'}
    elif method in ('thread/start','thread/resume'):
        assert Path(params['cwd']).resolve() == project
        result = {'thread':{'id':'fixture-supervisor'}}
    elif method == 'thread/goal/set':
        result = {'goal':{'tokenBudget':params['tokenBudget']}}
    elif method == 'turn/start':
        turn += 1; current_turn = 'fixture-turn-'+str(turn)
        result = {'turn':{'id':current_turn}}
    elif method == 'turn/steer': result = {'turnId':params['expectedTurnId']}
    elif method == 'turn/interrupt': result = {}
    else: continue
    emit({'id':message['id'],'result':result})
    if method == 'turn/start': threading.Timer(0.15, after_start, args=(params,)).start()
    if method == 'turn/interrupt': completed('Synthetic turn stopped by user.', 'interrupted')
