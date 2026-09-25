"""Private durable accepted chat messages, separate from the bounded event log."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

class TranscriptArchive:
    def __init__(self, root):
        self.root=Path(root)/'transcripts'
        if self.root.is_symlink(): raise ValueError('Invalid chat storage directory.')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root_identity=(self.root.stat().st_dev,self.root.stat().st_ino)
        os.chmod(self.root,0o700)

    @contextmanager
    def _connect(self,team):
        if not isinstance(team,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}',team):
            raise ValueError('Invalid chat.')
        root_stat=self.root.lstat()
        if not stat.S_ISDIR(root_stat.st_mode) or (root_stat.st_dev,root_stat.st_ino)!=self.root_identity: raise ValueError('Chat storage directory changed.')
        path=self.root/(hashlib.sha256(team.encode()).hexdigest()+'.sqlite')
        if path.is_symlink(): raise ValueError('Invalid chat storage.')
        fd=os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
        conn=None
        try:
            original=os.fstat(fd)
            if not stat.S_ISREG(original.st_mode) or original.st_nlink!=1: raise ValueError('Invalid chat database file.')
            os.fchmod(fd,0o600)
            def validate():
                current=path.lstat();root_now=self.root.lstat()
                if not stat.S_ISREG(current.st_mode) or current.st_nlink!=1 or (current.st_dev,current.st_ino)!=(original.st_dev,original.st_ino) or not stat.S_ISDIR(root_now.st_mode) or (root_now.st_dev,root_now.st_ino)!=self.root_identity:
                    raise ValueError('Chat database changed while opening.')
            validate()
            conn=sqlite3.connect(path,timeout=10)
            validate()
            conn.execute('CREATE TABLE IF NOT EXISTS messages (seq INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL, value TEXT NOT NULL)')
            with conn:
                yield conn
                validate()
        finally:
            if conn: conn.close()
            os.close(fd)

    def record(self,team,event):
        kind=event.get('type')
        if kind not in {'message.user','message.completed'}: return
        seq=event.get('seq')
        if not isinstance(seq,int) or seq<1: raise ValueError('Invalid message sequence.')
        # An assistant item is finalized once; repeated completions update it.
        identity=(f"assistant:{event.get('threadId')}:{event['itemId']}" if kind=='message.completed' and event.get('itemId') else f'{kind}:{seq}')
        data=event.get('data',{})
        safe={key:event.get(key) for key in ('seq','time','type','threadId','turnId','itemId')}
        safe['data']={'text':str(data.get('text',''))[:240000]}
        if kind=='message.user' and isinstance(data.get('attachments'),list):
            safe['data']['attachments']=[{key:item[key] for key in ('id','name','url') if isinstance(item.get(key),str)} for item in data['attachments'][:4] if isinstance(item,dict)]
        with self._connect(team) as conn:
            previous=conn.execute('SELECT seq FROM messages WHERE identity=?',(identity,)).fetchone()
            if previous: safe['seq']=previous[0]
            conn.execute('INSERT INTO messages(seq,identity,value) VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET value=excluded.value',
                         (safe['seq'],identity,json.dumps(safe)))

    def contains_attachments(self, team):
        # Check the complete accepted history, not just the compact handoff page.
        with self._connect(team) as conn:
            for (value,) in conn.execute('SELECT value FROM messages WHERE value LIKE ?', ('%"attachments":%',)):
                event = json.loads(value)
                if event.get('type') == 'message.user' and event.get('data', {}).get('attachments'):
                    return True
        return False

    def page(self,team,before=None,limit=60):
        if before is not None and (not isinstance(before,int) or isinstance(before,bool) or before<1): raise ValueError('Invalid history cursor.')
        limit=max(1,min(int(limit),100))
        with self._connect(team) as conn:
            rows=conn.execute('SELECT seq,value FROM messages WHERE seq < ? ORDER BY seq DESC LIMIT ?',
                              (before or 9223372036854775807,limit+1)).fetchall()
        visible=rows[:limit]
        return {'events':[json.loads(row[1]) for row in reversed(visible)],'before':visible[-1][0] if len(rows)>limit else None}
