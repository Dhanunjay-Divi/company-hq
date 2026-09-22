"""Validated, retry-safe plans over the single task authority."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
from runtime_config import clawteam_data_dir
from task_authority import TaskStore, _lock

KEY = re.compile(r'^[a-z][a-z0-9-]{0,63}$')

def validate(plan, members):
    if not isinstance(plan, dict) or set(plan) - {'goal', 'steps', 'executionStarted'}:
        raise ValueError('A plan needs a goal and steps.')
    goal = plan.get('goal')
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 500:
        raise ValueError('Enter a goal of at most 500 characters.')
    steps = plan.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError('A plan needs 1 to 20 steps.')
    clean, keys = [], set()
    for step in steps:
        if not isinstance(step, dict) or set(step) - {'key','title','description','owner','acceptance','dependsOn'}:
            raise ValueError('Unsupported plan step.')
        key = step.get('key')
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys:
            raise ValueError('Each step needs a unique lowercase key.')
        keys.add(key)
        for field, cap in [('title',160),('description',4000),('owner',120),('acceptance',1000)]:
            if not isinstance(step.get(field), str) or not 1 <= len(step[field].strip()) <= cap:
                raise ValueError('Each step needs a bounded title, description, owner and acceptance check.')
        if step['owner'] not in members:
            raise ValueError('A plan step has an unknown owner.')
        dependencies = step.get('dependsOn', [])
        if not isinstance(dependencies, list) or any(not isinstance(x,str) for x in dependencies):
            raise ValueError('Dependencies must be step keys.')
        clean.append({**step, 'dependsOn': list(dict.fromkeys(dependencies))})
    for step in clean:
        if any(dep not in keys or dep == step['key'] for dep in step['dependsOn']):
            raise ValueError('A plan has an invalid dependency.')
    return ordered(clean)

def ordered(steps):
    output, remaining, seen = [], list(steps), set()
    while remaining:
        ready = [step for step in remaining if set(step['dependsOn']) <= seen]
        if not ready:
            raise ValueError('A plan cannot contain dependency cycles.')
        for step in ready:
            output.append(step); seen.add(step['key']); remaining.remove(step)
    return output

class WorkflowPlans:
    def __init__(self, state_root=None, store_factory=None):
        self.root = (state_root or clawteam_data_dir()) / 'workflow-plans'
        self.store_factory = store_factory or TaskStore

    def preview(self, team, plan, members):
        if not isinstance(team,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',team):
            raise ValueError('Invalid team.')
        return {'goal':plan.get('goal','').strip() if isinstance(plan,dict) and isinstance(plan.get('goal'),str) else '',
                'executionStarted':False, 'steps':validate(plan,set(members))}

    def apply(self, team, request_id, plan, members):
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9-]{8,128}',request_id):
            raise ValueError('Invalid plan request.')
        card = self.preview(team,plan,members)
        digest = hashlib.sha256(json.dumps(card,sort_keys=True).encode()).hexdigest()
        folder = self.root / hashlib.sha256(team.encode()).hexdigest()[:32]
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        receipt = folder / (request_id + '.json')
        with _lock(folder):
            if receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved.get('payloadHash') != digest:
                    raise ValueError('This request ID belongs to a different plan.')
            else:
                # Persist identity BEFORE task mutation. A crash or partial import
                # can be retried, but cannot silently change the requested plan.
                self._save(receipt, {'payloadHash':digest})
            store = self.store_factory(team)
            ids = {}
            for task in store.list_tasks():
                meta = getattr(task,'metadata',{}) or {}
                if meta.get('workflowPlan') == request_id:
                    if meta.get('workflowHash') != digest:
                        raise ValueError('An existing task belongs to a different plan revision.')
                    key = meta.get('workflowKey')
                    if key in ids:
                        raise ValueError('Duplicate plan tasks require review before resuming.')
                    ids[key] = task.id
            for step in card['steps']:
                if step['key'] not in ids:
                    task = store.create(step['title'],step['description']+'\n\nAcceptance: '+step['acceptance'],
                        owner=step['owner'], blocked_by=[ids[x] for x in step['dependsOn']],
                        metadata={'workflowPlan':request_id,'workflowKey':step['key'],'workflowHash':digest})
                    ids[step['key']] = task.id
            observed = {t.id:t for t in store.list_tasks()}
            statuses = {key:str(getattr(observed.get(value),'status','unknown').value
                        if hasattr(getattr(observed.get(value),'status',None),'value')
                        else getattr(observed.get(value),'status','unknown')) for key,value in ids.items()}
            result = {**card,'requestId':request_id,'taskIDs':ids,'statuses':statuses,
                      'dependencies':{s['key']:[ids[d] for d in s['dependsOn']] for s in card['steps']}}
            self._save(receipt,{'payloadHash':digest,'result':result})
            return result

    @staticmethod
    def _save(path, value):
        tmp = path.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf8') as stream:
            os.chmod(tmp,0o600)
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
