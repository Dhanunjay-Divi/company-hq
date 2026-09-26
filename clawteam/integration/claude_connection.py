"""Explicit official CLI sign-in and model discovery; no model prompts."""
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import threading
from urllib.parse import urlparse
from runtime_config import state_root

ALLOWED_HOSTS={'claude.ai','console.anthropic.com','platform.claude.com','auth.anthropic.com'}

def official_url(value):
    try:
        url=urlparse(value)
        return url.scheme=='https' and url.hostname in ALLOWED_HOSTS and not url.username and not url.password and url.port in (None,443)
    except ValueError: return False

class ClaudeConnection:
    def __init__(self):
        self.lock=threading.RLock();self.operation=threading.Lock();self.process=None
        self.value={'authentication':'not_checked','models':[]}

    def snapshot(self):
        with self.lock: return dict(self.value)

    def check(self):
        from claude_runtime import probe, runtime
        with self.operation:
            info=probe()
            value={'authentication':'signed_in' if info.get('authenticated') else 'not_installed' if not info.get('installed') else 'sign_in_required',
                   'installed':bool(info.get('installed')),'runtimeReady':bool(info.get('version')),
                   'models':[],'usageWindows':[],'usageScope':'account_allowance',
                   'message':'Claude Code sign-in is verified.' if info.get('authenticated') else 'Claude Code is not installed. Claude Desktop sign-in is separate from HQ.' if not info.get('installed') else 'Sign in with the official Claude Code login. Desktop sign-in may be separate.'}
            if info.get('authenticated'):
                folder=state_root()/'provider-checks'/'claude';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
                client=runtime(access='plan')
                try:
                    result=client.initialize(project=folder)
                    value['models']=[row['value'] for row in result.get('models',[]) if isinstance(row.get('value'),str)]
                    value['modelDetails']=result.get('models',[])
                finally: client.stop()
            with self.lock:
                if self.process is not None and self.process.poll() is None:
                    value['authentication']='signing_in';value['message']='Finish the official login in your browser, then check status.'
                    if self.value.get('authUrl'):value['authUrl']=self.value['authUrl']
                self.value=value
            return self.snapshot()

    def connect(self):
        from claude_runtime import login_command
        if os.name=='nt': raise ValueError('Use Claude Code auth login in a terminal on Windows, then check status here.')
        with self.operation:
            with self.lock:
                if self.process is not None and self.process.poll() is None:return dict(self.value)
            import pty
            master,slave=pty.openpty()
            try:
                process=subprocess.Popen(login_command(),stdin=slave,stdout=slave,stderr=slave,start_new_session=True,close_fds=True)
            except Exception:
                os.close(master);raise
            finally:os.close(slave)
            with self.lock:
                self.process=process
                self.value={'authentication':'signing_in','models':[], 'message':'The official Claude Code login is opening. Complete sign-in in your browser.'}
            def watch():
                tail=''
                try:
                    while process.poll() is None:
                        if not select.select([master],[],[],0.5)[0]:continue
                        data=os.read(master,8192)
                        if not data:break
                        tail=(tail+data.decode('utf8','replace'))[-16384:]
                        for url in re.findall(r'https://[^\s\x1b<>"\']+',tail):
                            if official_url(url):
                                with self.lock:
                                    if self.process is process:self.value['authUrl']=url
                except OSError:pass
                finally:
                    os.close(master)
                    with self.lock:
                        if self.process is process:
                            self.process=None;self.value.pop('authUrl',None)
                            self.value['authentication']='not_checked'
                            self.value['message']='Login closed. Check status to verify your connection.'
            threading.Thread(target=watch,daemon=True,name='claude-login').start()
            return self.snapshot()

    def cancel(self):
        with self.operation:
            with self.lock:process=self.process;self.process=None
            if process is not None and process.poll() is None:
                try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
                except ProcessLookupError:pass
            with self.lock:self.value={'authentication':'not_checked','models':[],'message':'Sign-in cancelled.'}
            return self.snapshot()

    def close(self):self.cancel()
