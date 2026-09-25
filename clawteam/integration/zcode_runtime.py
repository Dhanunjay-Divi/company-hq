"""ZCode protocol adapter using its native standalone account provider.

Account credentials are handled entirely by ZCode. See ZCODE-INTEGRATION.md for
why its desktop app-server needs the narrowly pinned compatibility entrypoint.
"""
from __future__ import annotations
import base64, hashlib, os, threading, time, uuid
from pathlib import Path
from native_rpc import NativeRpc
from provider_runtime import ProviderRuntime, ProviderRuntimeError
from claude_runtime import ClaudeCodeRuntime

PIN='b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529'
MAX_SESSION_ATTACHMENTS=100
MAX_SESSION_ATTACHMENT_BYTES=100*1024*1024
MAX_SUBAGENT_PAGES=20
SUBAGENT_PAGE_LIMIT=50
MAX_SUBAGENTS=200
_IMAGE_SUFFIXES={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/gif':'.gif'}
def zcode_command():
    from runtime_config import node_executable
    node=node_executable()
    entry=Path(os.environ.get('COMPANY_HQ_ZCODE_ENTRY','/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs'))
    return [str(node),str(entry)] if node and entry.is_file() else None

def reviewed_bundle(command=None):
    command=command or zcode_command()
    if not command:return False
    try:return hashlib.sha256(Path(command[-1]).read_bytes()).hexdigest()==PIN
    except OSError:return False

def runtime_env():
    command=zcode_command()
    resources=Path(command[-1]).parent.parent if command else Path('/Applications/ZCode.app/Contents/Resources')
    return {**os.environ,'ZCODE_BUILTIN_PROVIDER_CONFIG_FILE':str(resources/'config/provider/zcode-builtin.json'),'ZCODE_PERSONAL_PROVIDER_CONFIG_FILE':str(Path.home()/'.zcode/v2/provider_config.json')}
def login_command():
    command=zcode_command()
    if not command:raise ProviderRuntimeError('Install ZCode to connect.')
    return command+['login','--no-browser']
def runtime(**kwargs):return ZCodeRuntime(**kwargs)
def probe():
    from runtime_config import state_root
    command=zcode_command()
    if not command:return {'installed':False,'authenticated':False,'runtimeReady':False,'checksumVerified':False,'models':[]}
    if not reviewed_bundle(command):
        return {'installed':True,'authenticated':False,'runtimeReady':False,'checksumVerified':False,'models':[],
                'message':'ZCode was updated. Its execution adapter needs a compatibility review.'}
    folder=state_root()/'provider-checks/zai';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    client=runtime(access='plan')
    try:
        value=client.initialize(project=folder)
        return {'installed':True,'authenticated':True,'runtimeReady':True,'checksumVerified':True,'version':'0.16.9','models':value['models']}
    except ProviderRuntimeError as exc:return {'installed':True,'authenticated':False,'runtimeReady':True,'checksumVerified':True,'models':[],'message':str(exc)}
    finally:client.stop()

class ZCodeRuntime(ProviderRuntime):
    provider='zai'
    def __init__(self,*,model=None,access='workspace',session_id=None,rpc_factory=NativeRpc,shared_tools=False,**_):
        super().__init__(model=model)
        self.shared_tools=shared_tools
        if access not in ('plan','workspace','full'):raise ProviderRuntimeError('Unknown access mode')
        if session_id is not None and (not isinstance(session_id,str) or not session_id):raise ProviderRuntimeError('ZCode session ID is invalid')
        self.access=access;self.session_id=session_id;self.project=None;self.rpc=None;self.models=[]
        self.factory=rpc_factory;self.pending={};self.turn_id=None;self.generation=0;self.operation=threading.RLock();self.attachments=[];self.native_status={'childrenVerified':False,'activeChildCount':None};self.children=None
    def initialize(self,*,project,model=None):
        with self.operation:
            root=self._project(project)
            if self.rpc and root!=self.project:raise ProviderRuntimeError('GLM chat belongs to another project')
            if self.rpc:return {'models':self.models,'sessionId':self.session_id}
            command=zcode_command()
            if not command:raise ProviderRuntimeError('ZCode CLI is unavailable')
            if not reviewed_bundle(command):raise ProviderRuntimeError('ZCode was updated. Its execution adapter needs a compatibility review.')
            self.project=root;self._state='starting';self.generation+=1
            generation=self.generation
            self.rpc=self.factory([command[0],str(Path(__file__).with_name('zcode_standalone.cjs')),command[-1],'app-server'],root,lambda row:self._handle(row) if generation==self.generation else None,dialect='zcode',env=runtime_env())
            try:
                workspace={'workspacePath':root,'workspaceKey':root}
                if self.shared_tools:
                    from shared_tools import servers
                    mcp_servers=servers(root,team=getattr(self,'context_team',None),access=self.access)
                else:mcp_servers=[]
                args={'workspace':workspace,'mcpServers':mcp_servers}
                expected_session_id=self.session_id
                if expected_session_id:args['sessionId']=expected_session_id
                else:args.update(mode='plan',persistence='deferred',titleGenerationEnabled=False)
                result=self.rpc.request('session/resume' if self.session_id else 'session/create',args,timeout=45)
                session_id=result.get('session',{}).get('sessionId')
                if expected_session_id and session_id!=expected_session_id:raise ProviderRuntimeError('ZCode resumed a different session')
                if not isinstance(session_id,str) or not session_id:raise ProviderRuntimeError('ZCode returned no session identity')
                self.session_id=session_id
                reported=result.get('settings',{}).get('model',{})
                self.catalog={self._model_value(m.get('ref',{})):m for m in reported.get('available',[]) if m.get('ref') and not m.get('disabledReason')}
                self.models=[{'value':value,'displayName':m.get('label',value),'capabilities':m.get('properties',{}).get('inputFormat',{})} for value,m in self.catalog.items()]
                selected=model or self.model or self._model_value(reported.get('current',{}))
                if not self.models:raise ProviderRuntimeError('Sign in with the official ZCode CLI, then check the connection.')
                if selected not in self.catalog:raise ProviderRuntimeError('Select a model reported by ZCode')
                self.model=selected
                if selected!=self._model_value(reported.get('current',{})):
                    if args.get('sessionId'):raise ProviderRuntimeError('Start a new chat to change this GLM session model')
                    unused=self.session_id
                    selection=dict(self.catalog[selected]['ref'])
                    reasoning=self.catalog[selected].get('reasoning',{})
                    if reasoning.get('defaultLevel'):
                        selection['options']={'reasoningLevel':reasoning['defaultLevel']}
                    extra={'thoughtLevel':reasoning['defaultLevel']} if reasoning.get('defaultLevel') else {}
                    result=self.rpc.request('session/create',{**args,'model':selection,**extra},timeout=45)
                    self.session_id=result['session']['sessionId']
                    if not isinstance(self.session_id,str) or not self.session_id:raise ProviderRuntimeError('ZCode returned no session identity')
                    self.rpc.request('session/close',{'sessionId':unused})
                self.set_access(self.access);self._state='idle'
                self._event('runtime.started',sessionId=self.session_id,model=self.model,project=root)
                return {'models':self.models,'sessionId':self.session_id}
            except Exception:self.stop();raise
    @staticmethod
    def _model_value(ref):return str(ref.get('providerId',''))+'/'+str(ref.get('modelId',''))
    def set_access(self,access):
        if access not in ('plan','workspace','full'):raise ProviderRuntimeError('Unknown access mode')
        mode={'plan':'plan','workspace':'build','full':'yolo'}[access]
        if self.rpc and self.session_id:
            result=self.rpc.request('session/setMode',{'sessionId':self.session_id,'mode':mode})
            reported=result.get('settings',{}).get('mode',{}).get('current')
            if reported and reported!=mode:raise ProviderRuntimeError('ZCode did not apply the requested access mode')
        self.access=access;self._event('runtime.access',accessMode=access,sessionId=self.session_id)
        return {'accepted':True,'accessMode':access}
    def start(self,prompt,*,project,model=None,images=None,**_):
        self.initialize(project=project,model=model)
        if model and model!=self.model:
            if model not in self.catalog:raise ProviderRuntimeError('Select a model reported by ZCode')
            raise ProviderRuntimeError('Start a new chat to change this GLM session model')
        return self.send(prompt,images=images)
    def send(self,prompt,*,images=None,**_):
        prompt=self._prompt(prompt)
        self.quota_failure=None
        with self.operation:
            if not self.rpc or self._state!='idle' or self.pending:raise ProviderRuntimeError('Wait for the current GLM turn or connect first')
            staged=[]
            for image in images or []:
                if not self.catalog[self.model].get('properties',{}).get('inputFormat',{}).get('supportsImage'):raise ProviderRuntimeError('This GLM model does not report image support')
                source=ClaudeCodeRuntime._image_block(image)['source']
                try:data=base64.b64decode(source['data'],validate=True)
                except ValueError as exc:raise ProviderRuntimeError('GLM image attachment is not valid base64') from exc
                suffix=_IMAGE_SUFFIXES.get(source['media_type'])
                if not suffix:raise ProviderRuntimeError('This GLM model does not support this image type')
                staged.append((data,suffix))
            attachments=[]
            if staged:
                folder=self._attachment_folder()
                try:
                    entries=list(folder.iterdir())
                    existing=[path for path in entries if path.is_file() and not path.is_symlink()]
                    if len(existing)!=len(entries):raise OSError('invalid attachment storage')
                    used=sum(path.stat().st_size for path in existing)
                except OSError as exc:raise ProviderRuntimeError('GLM image attachment storage is unavailable') from exc
                if len(existing)+len(staged)>MAX_SESSION_ATTACHMENTS or used+sum(len(data) for data,_ in staged)>MAX_SESSION_ATTACHMENT_BYTES:
                    raise ProviderRuntimeError('This GLM session has reached its private image attachment limit')
                for data,suffix in staged:
                    path=folder/(str(uuid.uuid4())+suffix)
                    try:
                        path.write_bytes(data);path.chmod(0o600)
                    except OSError as exc:raise ProviderRuntimeError('GLM image attachment storage is unavailable') from exc
                    self.attachments.append(path);attachments.append({'type':'image','path':str(path)})
            turn=str(uuid.uuid4());self.turn_id=turn;self._state='running';generation=self.generation
            self._event('message.user',text=prompt,sessionId=self.session_id,turnId=turn)
            threading.Thread(target=self._run,args=(prompt,attachments,turn,generation),daemon=True).start()
            return {'accepted':True,'provider':'zai','sessionId':self.session_id,'turnId':turn}
    def _run(self,prompt,attachments,turn,generation):
        try:
            before=self.rpc.request('session/read',{'sessionId':self.session_id})
            old={m.get('info',{}).get('messageId') for m in before.get('messages',[])}
            baseline_turns=before.get('projection',{}).get('turnCount',0)
            args={'sessionId':self.session_id,'content':prompt,'inputId':turn}
            if attachments:args['attachments']=attachments
            self.rpc.request('session/send',args,timeout=45)
            last='';tools=set();usage_at=0;previous_usage=None
            while generation==self.generation:
                result=self.rpc.request('session/read',{'sessionId':self.session_id},timeout=45)
                projection=result.get('projection',{})
                self.native_status={k:projection.get(k) for k in ('status','currentTurnId','turnCount','activeToolCalls')}
                if time.monotonic()-usage_at>=20:
                    usage_at=time.monotonic()
                    try:
                        usage=self.rpc.request('session/usage',{'sessionId':self.session_id})
                        if usage!=previous_usage:
                            previous_usage=usage;self._event('usage',nativeUsage=usage,sessionId=self.session_id,turnId=turn)
                    except ProviderRuntimeError:pass
                messages=[m for m in result.get('messages',[]) if m.get('info',{}).get('messageId') not in old and m.get('info',{}).get('role')=='assistant']
                text='\n\n'.join(''.join(p.get('text','') for p in m.get('parts',[]) if p.get('type')=='text') for m in messages)
                if text.startswith(last) and len(text)>len(last):self._event('message.delta',text=text[len(last):],sessionId=self.session_id,turnId=turn)
                last=text
                for message in messages:
                    for index,part in enumerate(message.get('parts',[])):
                        if part.get('type')!='tool':continue
                        state=part.get('state',{}).get('status')
                        ident=part.get('callID') or part.get('toolCallId') or part.get('id') or f"{message.get('info',{}).get('messageId')}:{index}"
                        key=(ident,state)
                        if key not in tools:
                            tools.add(key);self._event('tool.activity',title=part.get('tool'),status=state,toolCallId=ident,sessionId=self.session_id,turnId=turn)
                for tool in projection.get('activeToolCalls',[]):
                    key=(tool.get('toolCallId'),tool.get('status'))
                    if key not in tools:tools.add(key);self._event('tool.activity',title=tool.get('toolName'),status=tool.get('status'),sessionId=self.session_id,turnId=turn)
                # ZCode retains projection.currentTurnId after completion.
                # runtime.activeTurnId is the live execution indicator; the
                # projection is durable history and its turn count can reset
                # during session recovery. Require new assistant evidence too.
                native_runtime=result.get('runtime')
                if isinstance(native_runtime,dict):
                    ended=not native_runtime.get('activeTurnId') and not native_runtime.get('pendingRequestIds') and not projection.get('activeToolCalls') and bool(messages) and not self.pending
                else:
                    ended=not projection.get('currentTurnId') and (projection.get('turnCount',0)>baseline_turns or any(m.get('info',{}).get('error') for m in messages))
                if projection.get('status') in ('idle','completed','error') and ended:
                    self._state='error' if projection.get('status')=='error' or any(m.get('info',{}).get('error') for m in messages) else 'idle'
                    from quota_errors import quota_failure
                    self.quota_failure=next((q for m in messages if (q:=quota_failure(m.get('info',{}).get('error')))),None)
                    try:usage=self.rpc.request('session/usage',{'sessionId':self.session_id})
                    except ProviderRuntimeError:usage=None
                    self._refresh_workers()
                    self._cancel_pending()
                    self._event('message.completed',text=last,sessionId=self.session_id,turnId=turn,isError=self._state=='error',nativeUsage=usage)
                    return
                time.sleep(.75)
        except Exception as exc:
            if generation==self.generation:self._state='error';self._event('runtime.error',message=str(exc),sessionId=self.session_id,turnId=turn)
    def _handle(self,row):
        method=row.get('method');p=row.get('params') or {};ident=row.get('id')
        if method=='hq/stream_closed':self._state='error';self._event('runtime.error',message='ZCode connection closed',sessionId=self.session_id,turnId=self.turn_id);return
        if ident is None:return
        if method=='session/requestRuntimePreferences':
            self.rpc.reply(ident,{'nativeSearchEnhancementsEnabled':True,'memoryEnabled':False,'askUserQuestionAutoResolutionEnabled':False,'modelContextBudgetStrategy':'preflight-v1'});return
        if method=='interaction/requestPermission':
            if not isinstance(p.get('sessionId'),str) or p['sessionId']!=self.session_id:self.rpc.reject(ident);return
            for key,(previous_id,previous) in list(self.pending.items()):
                if p.get('requestId') and previous.get('requestId')==p['requestId']:
                    self.pending[key]=(ident,p);return
            key=str(uuid.uuid4());self.pending[key]=(ident,p)
            self._event('approval.requested',requestId=key,tool=p.get('toolName','ZCode tool'),toolInput=p.get('input',{}),reason=p.get('reason'),sessionId=self.session_id,turnId=self.turn_id)
        elif method=='interaction/requestUserInput':
            if not isinstance(p.get('sessionId'),str) or p['sessionId']!=self.session_id:self.rpc.reject(ident);return
            key=str(uuid.uuid4());self.pending[key]=(ident,{**p,'hqKind':'question'})
            self._event('question.requested',requestId=key,toolInput={'questions':p.get('questions',[])},reason=p.get('prompt'),sessionId=self.session_id,turnId=self.turn_id)
        else:self.rpc.reject(ident)
    def respond(self,request_id,response):
        if not isinstance(response,dict) or request_id not in self.pending:raise ProviderRuntimeError('Native request is stale or unknown')
        ident,p=self.pending[request_id]
        allow=response.get('allow') is True or response.get('approved') is True or response.get('decision') in ('allow','approve','accept','approved')
        if p.get('hqKind')=='question':
            answers=response.get('answers',{})
            if allow and (not isinstance(answers,dict) or not answers):raise ProviderRuntimeError('Answer the provider question before continuing')
            self.rpc.reply(ident,{'action':'accept','content':{'answers':answers}} if allow else {'action':'decline'})
        else:self.rpc.reply(ident,{'decision':'allow' if allow else 'deny'})
        self.pending.pop(request_id,None);self._event('request.resolved',requestId=request_id,sessionId=self.session_id,turnId=self.turn_id)
        return {'accepted':True}
    def stop(self):
        self.generation+=1;rpc=self.rpc
        if rpc:
            try:
                if self.session_id and self._state=='running':rpc.request('session/stop',{'sessionId':self.session_id},timeout=5)
            except Exception:pass
            rpc.close()
        self.rpc=None;self._cancel_pending();self._state='offline'
        # Native history may refer to image paths; retain private attachments for resume.
        return {'accepted':True,'sessionId':self.session_id}
    def _cancel_pending(self):
        for key in list(self.pending):
            self.pending.pop(key,None);self._event('request.cancelled',requestId=key,sessionId=self.session_id,turnId=self.turn_id)
    def _attachment_folder(self):
        from runtime_config import state_root
        if not isinstance(self.session_id,str) or not self.session_id:raise ProviderRuntimeError('ZCode returned no session identity')
        root=state_root()/'provider-attachments'
        folder=root/hashlib.sha256(self.session_id.encode()).hexdigest()
        try:
            if root.is_symlink() or folder.is_symlink():raise OSError('symlink')
            root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
            folder.mkdir(exist_ok=True,mode=0o700);folder.chmod(0o700)
            if root.is_symlink() or folder.is_symlink() or not root.is_dir() or not folder.is_dir():raise OSError('invalid')
        except OSError as exc:raise ProviderRuntimeError('GLM image attachment storage is unavailable') from exc
        return folder
    @staticmethod
    def _child_text(value,limit=512):
        return value if isinstance(value,str) and value and len(value)<=limit else None
    def _worker_row(self,row,terminal):
        if not isinstance(row,dict):raise ProviderRuntimeError('ZCode returned an invalid child session record')
        child=self._child_text(row.get('childSessionId'))
        native_status=row.get('status')
        allowed={'success','failed','cancelled','lost'} if terminal else {'running','waiting','blocked'}
        if not child or native_status not in allowed:raise ProviderRuntimeError('ZCode returned an invalid child session record')
        status={'success':'completed','cancelled':'stopped','lost':'error'}.get(native_status,native_status)
        result={'threadId':child,'childThreadId':child,'parentThreadId':self.session_id,'status':status,'nativeStatus':native_status,'source':'zcode-subagents'}
        for source,target,limit in (('title','title',500),('summary','summary',2000),('subagentType','role',200),('agentId','agentId',512),('toolCallId','toolCallId',512)):
            value=self._child_text(row.get(source),limit)
            if value is not None:result[target]=value
        for key in ('startedAt','endedAt'):
            value=row.get(key)
            if isinstance(value,int) and not isinstance(value,bool) and value>=0:result[key]=value
        return result
    def _workers_unknown(self,error):
        self.children=None
        self.native_status={**self.native_status,'childrenVerified':False,'activeChildCount':None}
        return {'provider':'zai','rootThreadId':self.session_id,'available':False,'authoritative':False,'complete':False,'workers':None,'error':error}
    def _refresh_workers(self):
        if not self.rpc or not isinstance(self.session_id,str) or not self.session_id:
            return self._workers_unknown('Connect this GLM chat before checking child sessions')
        cursor=None;revision=None;child_ids=None;running={};ended={};ended_total=None
        try:
            for _ in range(MAX_SUBAGENT_PAGES):
                params={'sessionId':self.session_id,'endedLimit':SUBAGENT_PAGE_LIMIT}
                if cursor is not None:params['endedCursor']=cursor
                page=self.rpc.request('session/subagents',params,timeout=45)
                if not isinstance(page,dict):raise ProviderRuntimeError('ZCode returned an invalid child session inventory')
                current_revision=page.get('revision')
                ids=page.get('childSessionIds')
                ended_page=page.get('ended')
                if not isinstance(current_revision,int) or isinstance(current_revision,bool) or current_revision<0 or not isinstance(ids,list) or not isinstance(ended_page,dict):raise ProviderRuntimeError('ZCode returned an invalid child session inventory')
                ids={self._child_text(value) for value in ids}
                if None in ids or len(ids)>MAX_SUBAGENTS:raise ProviderRuntimeError('ZCode child session inventory exceeds the safe limit')
                if revision is None:revision=current_revision;child_ids=ids
                elif revision!=current_revision or child_ids!=ids:raise ProviderRuntimeError('ZCode child session inventory changed during pagination')
                rows=page.get('running')
                items=ended_page.get('items')
                total=ended_page.get('total')
                next_cursor=ended_page.get('nextCursor')
                if not isinstance(rows,list) or not isinstance(items,list) or not isinstance(total,int) or isinstance(total,bool) or total<0 or (next_cursor is not None and not self._child_text(next_cursor)) or len(rows)+len(items)>MAX_SUBAGENTS:raise ProviderRuntimeError('ZCode returned an invalid child session inventory')
                if ended_total is None:ended_total=total
                elif ended_total!=total:raise ProviderRuntimeError('ZCode child session inventory changed during pagination')
                for row in rows:
                    normalized=self._worker_row(row,False)
                    if normalized['threadId'] not in child_ids:raise ProviderRuntimeError('ZCode returned an unbound child session')
                    running[normalized['threadId']]=normalized
                for row in items:
                    normalized=self._worker_row(row,True)
                    if normalized['threadId'] not in child_ids:raise ProviderRuntimeError('ZCode returned an unbound child session')
                    ended[normalized['threadId']]=normalized
                if next_cursor is None:
                    if len(ended)!=ended_total or set(running)&set(ended) or set(running)|set(ended)!=child_ids:raise ProviderRuntimeError('ZCode child session inventory is incomplete')
                    workers=sorted([*running.values(),*ended.values()],key=lambda row:row['threadId'])
                    self.children=workers
                    self.native_status={**self.native_status,'childrenVerified':True,'activeChildCount':len(running)}
                    return {'provider':'zai','rootThreadId':self.session_id,'available':True,'authoritative':True,'complete':True,'revision':revision,'workers':workers,'error':None}
                if next_cursor==cursor:raise ProviderRuntimeError('ZCode child session pagination did not advance')
                cursor=next_cursor
            raise ProviderRuntimeError('ZCode child session inventory exceeded the pagination limit')
        except (ProviderRuntimeError,OSError,ValueError) as exc:
            return self._workers_unknown(str(exc))
    def workers(self):
        with self.operation:return self._refresh_workers()
    def tools(self):
        if not self.rpc:raise ProviderRuntimeError('Connect this GLM chat before checking tools')
        workspace={'workspacePath':self.project,'workspaceKey':self.project}
        if self.shared_tools:
            from shared_tools import servers
            mcp_servers=servers(self.project,team=getattr(self,'context_team',None),access=self.access)
        else:mcp_servers=[]
        # Native status mode inspects the global manager, not this session's
        # separately configured MCP connections. Explicit UI checks revalidate
        # the workspace definitions; never label that as session liveness.
        result=self.rpc.request('mcp/list',{'workspace':workspace,'mcpServers':mcp_servers,'mode':'connect'},timeout=45)
        skills=self.rpc.request('skills/referenceCatalog',{'workspace':workspace,'sessionId':self.session_id})
        inventory=[{'name':name,**data,'runtimeStatus':data.get('status'),'toolCount':data.get('toolCount')} for name,data in result.get('statuses',{}).items() if isinstance(data,dict)]
        return {'provider':'zai','available':True,'servers':inventory, 'skills':skills.get('skills',[]),'apps':[],'readOnly':True,'inventoryScope':'workspace','reason':'Workspace MCP check: configured servers were connected or revalidated. This is not the active chat session’s exact connection state. Native skills are managed in ZCode.'}
    def status(self):return {**super().status(),'sessionId':self.session_id,'project':self.project,'models':self.models,'accessMode':self.access,'nativeStatus':self.native_status,'children':self.children,'quotaFailure':getattr(self,'quota_failure',None)}
