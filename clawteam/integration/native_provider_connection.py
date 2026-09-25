"""Provider-owned sign-in and sanitized capability discovery, without model prompts."""
import importlib
import subprocess
import threading
from urllib.parse import urlparse
import re

MODULES={'kimi':'kimi_runtime','zai':'zcode_runtime'}
class NativeProviderConnection:
    def __init__(self,provider):
        if provider not in MODULES:raise ValueError('Unsupported provider')
        self.provider=provider;self.lock=threading.RLock();self.operation=threading.Lock();self.process=None
        self.value={'authentication':'not_checked','models':[],'usageWindows':[]}
    def snapshot(self):
        with self.lock:return dict(self.value)
    def check(self):
        with self.operation:
            module=importlib.import_module(MODULES[self.provider]);info=module.probe()
            details=info.get('models',[])
            value={'authentication':'signed_in' if info.get('authenticated') else 'sign_in_required','installed':bool(info.get('installed')),'runtimeReady':bool(info.get('runtimeReady')),'models':[m['value'] for m in details if isinstance(m,dict) and isinstance(m.get('value'),str)],'modelDetails':details,'usageWindows':[], 'usageScope':'account_allowance','message':'Sign-in and model discovery verified. Ready for a task.' if info.get('authenticated') else info.get('message','Sign in with the provider, then check the connection.')}
            with self.lock:
                if info.get('authenticated'):value['message']='Sign-in and model list verified. Coding entitlement is checked when the provider accepts a task.'
                if self.process and self.process.poll() is None:value.update(authentication='signing_in',message='Finish the official sign-in in your browser, then check status.')
                self.value=value
            return self.snapshot()
    def connect(self):
        info=self.check()
        if info.get('authentication')=='signed_in':return info
        module=importlib.import_module(MODULES[self.provider])
        with self.operation:
            if self.process and self.process.poll() is None:return self.snapshot()
            kwargs={'stdin':subprocess.DEVNULL,'stdout':subprocess.PIPE,'stderr':subprocess.STDOUT,'text':True,'start_new_session':True}
            if hasattr(module,'runtime_env'):kwargs['env']=module.runtime_env()
            process=subprocess.Popen(module.login_command(),**kwargs);self.process=process
            with self.lock:self.value.update(authentication='signing_in',message='Complete the provider’s official sign-in in your browser, then check status.')
            def watch():
                for line in process.stdout:
                    for url in re.findall(r'https://[^\s<>\x1b]+',line):
                        try:
                            host=urlparse(url).hostname or ''
                            allowed=('kimi.com','kimi.ai') if self.provider=='kimi' else ('z.ai','bigmodel.cn')
                            if any(host==base or host.endswith('.'+base) for base in allowed):
                                with self.lock:self.value['authUrl']=url[:3000]
                        except ValueError:pass
                code=process.wait()
                with self.lock:
                    if self.process is process:self.value.update(authentication='not_checked' if code==0 else 'sign_in_required',message='Sign-in finished. Check status to verify access.' if code==0 else 'Sign-in was not completed. Try again or sign in using the provider app.')
            threading.Thread(target=watch,daemon=True).start()
        return self.snapshot()
    def cancel(self):
        with self.operation:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill()
            self.process=None
            with self.lock:self.value={'authentication':'not_checked','models':[]}
        return self.snapshot()
    def close(self):self.cancel()
