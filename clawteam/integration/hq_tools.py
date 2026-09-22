"""Small native client tools for project-scoped HQ work; no second scheduler."""
from clawteam.team.manager import TeamManager
from clawteam.team.models import TaskStatus
from task_authority import TaskStore


def spec(name, description, properties, required):
    return {'type':'function','name':name,'description':description,
            'inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}


def tool_specs():
    text={'type':'string'}
    return [
        spec('hq_tasks','Read the canonical HQ work board. Update your own task after actual work and checks; status is not proof of test success.',
             {'action':{'enum':['list','update']},'taskId':text,'status':{'enum':['pending','in_progress','blocked','completed']},'offset':{'type':'integer','minimum':0}},['action']),
        spec('hq_plan','Record a bounded plan in HQ with registered owners, dependencies and acceptance checks. Does not start workers. Reuse requestId on retry.',
             {'requestId':text,'plan':{'type':'object','properties':{'goal':text,'steps':{'type':'array','maxItems':20,'items':{'type':'object','properties':{'key':text,'title':text,'description':text,'owner':text,'acceptance':text,'dependsOn':{'type':'array','items':text}},'required':['key','title','description','owner','acceptance'],'additionalProperties':False}}},'required':['goal','steps'],'additionalProperties':False}},['requestId','plan']),
        spec('hq_command','Run a bounded command under this chat’s native access policy. Retain raw evidence and return filtered output when safe. Use for verification commands.',{'command':text},['command']),
        spec('hq_recall','Page project-scoped raw command evidence when compact output is insufficient.',{'id':text,'offset':{'type':'integer','minimum':0}},[]),
    ]


def execute(bridge, session, tool, args):
    if not isinstance(args,dict): raise ValueError('Tool arguments must be an object.')
    allowed={row['name']:row['inputSchema'] for row in tool_specs()}
    schema=allowed.get(tool)
    if schema is None or set(args)-set(schema['properties']) or set(schema['required'])-set(args):
        raise ValueError('Unsupported HQ tool arguments.')
    team=session.team
    if tool=='hq_tasks':
        store=TaskStore(team)
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
        return {'tasks':rows,'nextOffset':offset+20 if len(tasks)>offset+20 else None,'total':len(tasks)}
    if tool=='hq_plan':
        from workflow_plan import WorkflowPlans
        team_info=TeamManager.get_team(team)
        if not team_info: raise ValueError('HQ team is unavailable.')
        return WorkflowPlans(bridge.state_dir.parent).apply(team,args['requestId'],args['plan'],[member.name for member in team_info.members])
    if tool=='hq_command':
        from runtime_actions import command
        return command(bridge,bridge.state_dir.parent,team,args['command'])
    from runtime_actions import evidence
    offset=args.get('offset',0)
    if not isinstance(offset,int) or isinstance(offset,bool) or offset<0: raise ValueError('Invalid evidence offset.')
    return evidence(bridge.state_dir.parent,team,str(session.project),args.get('id'),offset)
