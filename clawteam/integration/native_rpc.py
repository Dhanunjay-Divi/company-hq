"""Small newline JSON-RPC transport; no credentials or account configuration."""
from __future__ import annotations
import json
import queue
import subprocess
import threading
from provider_runtime import ProviderRuntimeError

class NativeRpc:
    def __init__(self, command, project, callback, factory=subprocess.Popen, *, dialect='jsonrpc', env=None):
        self.dialect = dialect
        self.callback=callback; self.pending={}; self.lock=threading.RLock(); self.next_id=0; self.closed=False
        options = {'env': env} if env is not None else {}
        self.process=factory(command,cwd=str(project),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,start_new_session=True, **options)
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
    def write(self, value):
        if self.dialect == 'zcode':
            value = {key: item for key, item in value.items() if key != 'jsonrpc'}
        with self.lock:
            if self.closed or self.process.poll() is not None: raise ProviderRuntimeError('Native provider connection closed')
            try:self.process.stdin.write(json.dumps(value,separators=(',',':'))+'\n');self.process.stdin.flush()
            except (OSError,ValueError) as exc:raise ProviderRuntimeError('Native provider input closed') from exc
    def request(self,method,params,timeout=25):
        with self.lock:
            self.next_id+=1;ident=str(self.next_id) if self.dialect == 'zcode' else self.next_id;q=queue.Queue(maxsize=1);self.pending[ident]=q
        try:
            self.write({'jsonrpc':'2.0','id':ident,'method':method,'params':params})
            try:value=q.get(timeout=timeout)
            except queue.Empty as exc:raise ProviderRuntimeError(f'Native provider timed out: {method}') from exc
            if 'error' in value:
                err=value['error']; code=err.get('code') if isinstance(err,dict) else None
                # Classify actionable provider refusals without echoing URLs or private content.
                message=err.get('message','') if isinstance(err,dict) else ''
                if 'subscription does not have access to Kimi Code' in message:
                    raise ProviderRuntimeError('Kimi sign-in works, but this account does not currently have Kimi Code access. Activate the coding subscription, then retry.')
                if 'quota' in message.lower() or 'rate limit' in message.lower():
                    raise ProviderRuntimeError('The provider reported a usage limit. Check its account allowance before retrying.')
                raise ProviderRuntimeError(f'Native provider rejected {method} (code {code})')
            return value.get('result') or {}
        finally:
            with self.lock:self.pending.pop(ident,None)
    def notify(self,method,params):self.write({'jsonrpc':'2.0','method':method,'params':params})
    def reply(self,ident,result):self.write({'jsonrpc':'2.0','id':ident,'result':result})
    def reject(self,ident):self.write({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Unsupported client method'}})
    def _read(self):
        try:
            while True:
                line=self.process.stdout.readline(16*1024*1024+1)
                if not line:break
                if len(line)>16*1024*1024:
                    self.process.terminate();break
                try:value=json.loads(line)
                except (ValueError,TypeError):continue
                if not isinstance(value,dict):continue
                ident=value.get('id')
                with self.lock:q=self.pending.get(ident) if isinstance(ident,(str,int)) else None
                if q is not None and ('result' in value or 'error' in value):
                    try:q.put_nowait(value)
                    except queue.Full:pass
                else:
                    try:self.callback(value)
                    except Exception:pass
        finally:
            with self.lock:
                for q in self.pending.values():
                    try:q.put_nowait({'error':{'code':'stream_closed'}})
                    except queue.Full:pass
            if not self.closed:self.callback({'method':'hq/stream_closed','params':{}})
    def close(self):
        self.closed=True
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        for stream in (self.process.stdin,self.process.stdout):
            try:stream.close()
            except (OSError,ValueError):pass
