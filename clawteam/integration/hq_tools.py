"""Small native client tools for project-scoped HQ work; no second scheduler."""
from __future__ import annotations

from clawteam.team.manager import TeamManager
from clawteam.team.models import TaskStatus
from task_authority import TaskStore


def spec(name, description, properties, required):
    return {'type':'function','name':name,'description':description,
            'inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}


def tool_specs():
    text={'type':'string'}
    plan_key={
        'type':'string','pattern':'^[a-z][a-z0-9-]{0,63}$','minLength':1,'maxLength':64,
        'description':'Unique lowercase step key. Start with a letter; then use lowercase letters, digits, or hyphens.',
    }
    owner={
        'type':'string','minLength':1,'maxLength':120,
        'description':'Exact registered HQ team-member name returned by hq_tasks list. A native worker may perform the assignment, but this registered owner remains accountable.',
    }
    from project_context_mcp import TOOLS as context_specs
    context_tools = [spec(t['name'],t['description'],t['inputSchema']['properties'],t['inputSchema'].get('required',[])) for t in context_specs]
    return context_tools + [
        spec('hq_tasks','Read the canonical HQ work board and the registered owner names allowed in hq_plan. Update your own task after actual work and checks; status is not proof of test success.',
             {'action':{'enum':['list','update']},'taskId':text,'status':{'enum':['pending','in_progress','blocked','completed']},'offset':{'type':'integer','minimum':0}},['action']),
        spec('hq_plan','Record a bounded plan in HQ with exact registered owners returned by hq_tasks list, dependencies and acceptance checks. Does not start native workers: a worker may execute an assignment while the registered supervisor or team member remains its accountable owner. Reuse requestId on retry.',
             {'requestId':{'type':'string','pattern':'^[A-Za-z0-9-]{8,128}$','minLength':8,'maxLength':128},'plan':{'type':'object','properties':{'goal':{'type':'string','minLength':1,'maxLength':500},'steps':{'type':'array','minItems':1,'maxItems':20,'items':{'type':'object','properties':{'key':plan_key,'title':{'type':'string','minLength':1,'maxLength':160},'description':{'type':'string','minLength':1,'maxLength':4000},'owner':owner,'acceptance':{'type':'string','minLength':1,'maxLength':1000},'dependsOn':{'type':'array','uniqueItems':True,'maxItems':20,'items':plan_key}},'required':['key','title','description','owner','acceptance'],'additionalProperties':False}}},'required':['goal','steps'],'additionalProperties':False}},['requestId','plan']),
        spec('hq_command','Run a bounded command under this chat’s native access policy. Retain raw evidence and return filtered output when safe. Use for verification commands.',{'command':text},['command']),
        spec('hq_recall','Page project-scoped raw command evidence when compact output is insufficient.',{'id':text,'offset':{'type':'integer','minimum':0}},[]),
    ]


def _registered_owners(team_info):
    if not team_info:
        return []
    lead_id=getattr(team_info,'lead_agent_id',None)
    rows=[]
    seen=set()
    for member in getattr(team_info,'members',[]) or []:
        name=getattr(member,'name',None)
        if not isinstance(name,str) or not name or name in seen:
            continue
        seen.add(name)
        row={'name':name,'leader':bool(lead_id and getattr(member,'agent_id',None)==lead_id)}
        label=next((getattr(member,key,None) for key in ('display_name','label','agent_type')
                    if isinstance(getattr(member,key,None),str) and getattr(member,key,None).strip()),None)
        if label: row['label']=label.strip()[:160]
        rows.append(row)
    return rows


def _unknown_plan_owners(plan, allowed):
    if not isinstance(plan,dict) or not isinstance(plan.get('steps'),list):
        return []
    return sorted({step.get('owner') for step in plan['steps']
                   if isinstance(step,dict) and isinstance(step.get('owner'),str)
                   and 1 <= len(step['owner']) <= 120 and step['owner'] not in allowed})


def execute(bridge, session, tool, args):
    if not isinstance(args,dict): raise ValueError('Tool arguments must be an object.')
    allowed={row['name']:row['inputSchema'] for row in tool_specs()}
    schema=allowed.get(tool)
    if schema is None or set(args)-set(schema['properties']) or set(schema['required'])-set(args):
        raise ValueError('Unsupported HQ tool arguments.')
    team=session.team
    if tool in {'hq_context','hq_skills','hq_skill_read'}:
        from project_context import ProjectContext
        from project_context_mcp import call
        return call(ProjectContext(session.project,team),tool,args)
    if tool=='hq_tasks':
        store=TaskStore(team)
        team_info=TeamManager.get_team(team)
        owners=_registered_owners(team_info)
        if args['action']=='update':
            if session.mode=='plan': raise ValueError('Start execution before changing task progress.')
            task=store.update(args.get('taskId'),status=TaskStatus(args.get('status')),caller='overall-head')
            if task is None: raise ValueError('Task not found.')
        elif args['action']!='list': raise ValueError('Unknown task action.')
        offset=args.get('offset',0)
        if not isinstance(offset,int) or isinstance(offset,bool) or offset<0: raise ValueError('Invalid task cursor.')
        tasks=store.list_tasks();rows=[]
        for task in tasks[offset:offset+20]:
            value=task.model_dump(mode='json')
            rows.append({key:value.get(key) for key in ('id','subject','owner','status','blocked_by')})
        return {'tasks':rows,'nextOffset':offset+20 if len(tasks)>offset+20 else None,'total':len(tasks),
                'allowedOwners':[row['name'] for row in owners],'availableOwners':owners}
    if tool=='hq_plan':
        from workflow_plan import WorkflowPlans
        team_info=TeamManager.get_team(team)
        if not team_info: raise ValueError('HQ team is unavailable.')
        owners=_registered_owners(team_info)
        allowed=[row['name'] for row in owners]
        unknown=_unknown_plan_owners(args['plan'],set(allowed))
        if unknown:
            available=', '.join(allowed) if allowed else '(none)'
            raise ValueError(
                f"Unknown registered owner(s): {', '.join(unknown)}. Available registered owners: {available}. "
                "Use an exact name from hq_tasks list; native workers may execute assignments while a registered owner remains accountable."
            )
        return WorkflowPlans(bridge.state_dir.parent).apply(team,args['requestId'],args['plan'],allowed)
    if tool=='hq_command':
        from runtime_actions import command
        return command(bridge,bridge.state_dir.parent,team,args['command'])
    from runtime_actions import evidence
    offset=args.get('offset',0)
    if not isinstance(offset,int) or isinstance(offset,bool) or offset<0: raise ValueError('Invalid evidence offset.')
    return evidence(bridge.state_dir.parent,team,str(session.project),args.get('id'),offset)
