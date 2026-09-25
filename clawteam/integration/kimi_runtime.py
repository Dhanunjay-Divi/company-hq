"""Kimi Code 2.x native ACP: subscription sign-in stays with the official CLI."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import threading
import uuid
from native_rpc import NativeRpc
from provider_runtime import ProviderRuntime,ProviderRuntimeError
from claude_runtime import ClaudeCodeRuntime

def kimi_binary():
    candidates=[os.environ.get('COMPANY_HQ_KIMI_PATH'),shutil.which('kimi'),str(Path.home()/'.kimi-code/bin/kimi'),str(Path.home()/'.local/share/company-hq/providers/kimi/2.0.2/kimi')]
    return next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file() and os.access(p,os.X_OK)),None)
def login_command():
    binary=kimi_binary()
    if not binary:raise ProviderRuntimeError('Install the official Kimi Code CLI to connect.')
    return [binary,'login']
def runtime(**kwargs):return KimiRuntime(**kwargs)
def probe():
    from runtime_config import state_root
    binary=kimi_binary()
    if not binary:return {'installed':False,'authenticated':False,'runtimeReady':False,'models':[]}
    folder=state_root()/'provider-checks/kimi';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    client=runtime(access='plan')
    try:
        value=client.initialize(project=folder)
        return {'installed':True,'authenticated':True,'runtimeReady':True,'version':client.version,'models':value['models']}
    except ProviderRuntimeError as exc:
        return {'installed':True,'authenticated':False,'runtimeReady':True,'models':[],'message':str(exc)}
    finally:client.stop()

class KimiRuntime(ProviderRuntime):
    provider='kimi'
    def __init__(self,*,model=None,access='workspace',session_id=None,rpc_factory=NativeRpc,shared_tools=False,**_):
        super().__init__(model=model)
        self.shared_tools=shared_tools
        if access not in ('plan','workspace','full'):raise ProviderRuntimeError('Unknown access mode')
        if session_id is not None and (not isinstance(session_id,str) or not session_id):raise ProviderRuntimeError('Kimi session ID is invalid')
        self.access=access;self.session_id=session_id;self.project=None;self.rpc=None;self.models=[];self.version=None
        self.factory=rpc_factory;self.pending={};self.turn_id=None;self.chunks=[];self.generation=0;self.operation=threading.RLock()
    def initialize(self,*,project,model=None):
        with self.operation:
            root=self._project(project)
            if self.rpc and root!=self.project:raise ProviderRuntimeError('Kimi chat belongs to another project')
            if self.rpc:return {'models':self.models,'sessionId':self.session_id}
            binary=kimi_binary()
            if not binary:raise ProviderRuntimeError('Official Kimi CLI is unavailable')
            self.project=root;self._state='starting';self.generation+=1
            generation=self.generation
            self.rpc=self.factory([binary,'acp'],root,lambda row:self._handle(row) if generation==self.generation else None)
            try:
                init=self.rpc.request('initialize',{'protocolVersion':1,'clientInfo':{'name':'company-hq','version':'0.1.0'},'clientCapabilities':{}})
                self.version=init.get('agentInfo',{}).get('version');self.capabilities=init.get('agentCapabilities',{})
                self.rpc.request('authenticate',{'methodId':'login'})
                from shared_tools import servers
                params={'cwd':root,'mcpServers':servers(root,team=getattr(self,"context_team",None),access=self.access) if self.shared_tools else []}
                expected_session_id=self.session_id
                if expected_session_id:params['sessionId']=expected_session_id
                result=self.rpc.request('session/load' if self.session_id else 'session/new',params)
                sid=result.get('sessionId')
                if expected_session_id and sid!=expected_session_id:
                    raise ProviderRuntimeError('Kimi resumed a different session')
                if not isinstance(sid,str) or not sid:raise ProviderRuntimeError('Kimi returned no session identity')
                self.session_id=sid
                self.config_options=result.get('configOptions',[])
                entry=next((o for o in self.config_options if o.get('id')=='model'),{})
                self.models=[{'value':o['value'],'displayName':o.get('name',o['value'])} for o in entry.get('options',[]) if isinstance(o,dict) and isinstance(o.get('value'),str)]
                selected=model or self.model or entry.get('currentValue')
                if selected not in {o['value'] for o in self.models}:raise ProviderRuntimeError('Select a model reported by Kimi')
                self.model=selected
                self.rpc.request('session/set_config_option',{'sessionId':sid,'configId':'model','value':selected})
                self.set_access(self.access);self._state='idle'
                self._event('runtime.started',sessionId=sid,model=self.model,project=root)
                return {'models':self.models,'sessionId':sid,'capabilities':self.capabilities}
            except Exception:
                self.stop();raise
    def start(self,prompt,*,project,model=None,images=None,**_):
        self.initialize(project=project,model=model)
        if model and model!=self.model:
            if model not in {o['value'] for o in self.models}:raise ProviderRuntimeError('Select a model reported by Kimi')
            self.rpc.request('session/set_config_option',{'sessionId':self.session_id,'configId':'model','value':model})
            self.model=model
        return self.send(prompt,images=images)
    def set_access(self,access):
        if access not in ('plan','workspace','full'):raise ProviderRuntimeError('Unknown access mode')
        mode={'plan':'plan','workspace':'auto','full':'yolo'}[access]
        if self.rpc and self.session_id:self.rpc.request('session/set_mode',{'sessionId':self.session_id,'modeId':mode})
        self.access=access;self._event('runtime.access',accessMode=access,sessionId=self.session_id)
        return {'accepted':True,'accessMode':access}
    def send(self,prompt,*,images=None,**_):
        prompt=self._prompt(prompt)
        with self.operation:
            if self._state!='idle' or not self.rpc:raise ProviderRuntimeError('Wait for the current Kimi turn or connect first')
            if self.pending:raise ProviderRuntimeError('Respond to the pending native request')
            blocks=[{'type':'text','text':prompt}]
            for image in images or []:
                if not self.capabilities.get('promptCapabilities',{}).get('image'):raise ProviderRuntimeError('This Kimi runtime does not report image support')
                source=ClaudeCodeRuntime._image_block(image)['source'];blocks.append({'type':'image','data':source['data'],'mimeType':source['media_type']})
            self.turn_id=str(uuid.uuid4());turn=self.turn_id;generation=self.generation;self.chunks=[];self._state='running'
            self._event('message.user',text=prompt,sessionId=self.session_id,turnId=turn)
            threading.Thread(target=self._run,args=(blocks,turn,generation),daemon=True).start()
            return {'accepted':True,'provider':self.provider,'sessionId':self.session_id,'turnId':turn}
    def _run(self,blocks,turn,generation):
        try:
            result=self.rpc.request('session/prompt',{'sessionId':self.session_id,'prompt':blocks},timeout=3600)
            if generation!=self.generation:return
            self._state='idle'
            self._event('message.completed',text=''.join(self.chunks),sessionId=self.session_id,turnId=turn,stopReason=result.get('stopReason'),isError=result.get('stopReason')=='cancelled')
        except Exception as exc:
            if generation==self.generation:
                self._state='error';self._event('runtime.error',message=str(exc),sessionId=self.session_id,turnId=turn)
    def _handle(self,row):
        method=row.get('method');p=row.get('params') or {};ident=row.get('id')
        if method=='hq/stream_closed':
            self._state='error';self._event('runtime.error',message='Kimi connection closed',turnId=self.turn_id);return
        if ident is not None:
            if method=='session/request_permission':
                if not isinstance(p.get('sessionId'),str) or p['sessionId']!=self.session_id:
                    self.rpc.reject(ident);return
                key=str(uuid.uuid4());self.pending[key]=(ident,p)
                tool=p.get('toolCall',{})
                self._event('approval.requested',requestId=key,tool=tool.get('title','Kimi tool'),toolInput=tool.get('rawInput',{}),sessionId=self.session_id,turnId=self.turn_id)
            else:self.rpc.reject(ident)
            return
        if method!='session/update' or p.get('sessionId')!=self.session_id:return
        update=p.get('update') or {};kind=update.get('sessionUpdate')
        if kind=='agent_message_chunk' and self._state=='running':
            text=(update.get('content') or {}).get('text')
            if isinstance(text,str):self.chunks.append(text);self._event('message.delta',text=text,sessionId=self.session_id,turnId=self.turn_id)
        elif kind in ('tool_call','tool_call_update'):
            self._event('tool.activity',title=update.get('title'),status=update.get('status'),toolCallId=update.get('toolCallId'),sessionId=self.session_id,turnId=self.turn_id)
        elif kind=='config_option_update':self._event('runtime.config',options=update.get('configOptions'),sessionId=self.session_id)
    def respond(self,request_id,response):
        if not isinstance(response,dict):raise ProviderRuntimeError('Provide an approval response')
        value=self.pending.get(request_id)
        if not value:raise ProviderRuntimeError('Native request is stale or unknown')
        ident,params=value;allow=response.get('allow') is True or response.get('approved') is True or response.get('decision') in ('allow','accept','approved')
        choice=next((o for o in params.get('options',[]) if o.get('kind')==('allow_once' if allow else 'reject_once')),None)
        outcome={'outcome':'selected','optionId':choice['optionId']} if choice else {'outcome':'cancelled'}
        self.rpc.reply(ident,{'outcome':outcome});self.pending.pop(request_id,None)
        self._event('request.resolved',requestId=request_id,sessionId=self.session_id,turnId=self.turn_id)
        return {'accepted':True}
    def stop(self):
        self.generation+=1;rpc=self.rpc
        if rpc:
            try:
                if self.session_id and self._state=='running':rpc.notify('session/cancel',{'sessionId':self.session_id})
            except Exception:pass
            rpc.close()
        self.rpc=None;self.pending.clear();self._state='offline'
        return {'accepted':True,'sessionId':self.session_id}
    def status(self):return {**super().status(),'sessionId':self.session_id,'project':self.project,'models':self.models,'accessMode':self.access}
