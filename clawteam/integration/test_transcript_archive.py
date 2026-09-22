from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from transcript_archive import TranscriptArchive

class ArchiveTest(unittest.TestCase):
    def test_restart_paging_concurrency_scope_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=TranscriptArchive(root)
            def add(n):archive.record('one',{'seq':n,'type':'message.completed','threadId':'native-one','itemId':str(n),'data':{'text':str(n),'secret':'excluded'}})
            with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(add,range(1,140)))
            archive.record('one',{'seq':150,'type':'message.completed','threadId':'native-one','itemId':'139','data':{'text':'duplicate'}})
            archive.record('one',{'seq':160,'type':'request.pending','data':{'text':'secret'}})
            restarted=TranscriptArchive(root);first=restarted.page('one',limit=100);second=restarted.page('one',before=first['before'])
            self.assertEqual(len(first['events'])+len(second['events']),139)
            self.assertIsNone(second['before']);self.assertEqual(restarted.page('two')['events'],[])
            self.assertEqual(first['events'][-1]['data'],{'text':'duplicate'});self.assertEqual(first['events'][-1]['seq'],139)
            self.assertEqual(next(root.rglob('*.sqlite')).stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):archive.page('../escape')

    def test_rejects_linked_database_and_replaced_root(self):
        import hashlib,os,sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'state';state.mkdir();archive=TranscriptArchive(state)
            outside=root/'outside.sqlite'
            db=sqlite3.connect(outside)
            try:db.execute('CREATE TABLE safe(value TEXT)');db.commit()
            finally:db.close()
            target=archive.root/(hashlib.sha256(b'one').hexdigest()+'.sqlite')
            os.link(outside,target)
            with self.assertRaises(ValueError):archive.record('one',{'seq':1,'type':'message.user','data':{'text':'bad'}})
            conn=sqlite3.connect(outside)
            try:self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('safe',)])
            finally:conn.close()
            archive.root.rename(state/'previous');archive.root.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError):archive.page('two')
