"""One Company HQ backend owns a state directory at a time."""
import os
from pathlib import Path

class InstanceLock:
    def __init__(self,state):self.path=Path(state)/'.backend.lock';self.file=None
    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.file=self.path.open('a+b');os.chmod(self.path,0o600)
        try:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close();self.file=None
            raise RuntimeError('Company HQ is already running with this app data. Open its existing window or stop it before starting another instance.') from exc
        return self
    def close(self):
        if self.file:self.file.close();self.file=None
