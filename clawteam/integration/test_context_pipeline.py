import os, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
from context_pipeline import ContextPipeline, MAX_BYTES, MAX_RECORDS

class ContextPipelineTest(unittest.TestCase):
 def test_private_isolation_pagination_and_failure_fallback(self):
  with tempfile.TemporaryDirectory() as temp:
   p=ContextPipeline(temp)
   a=p.record('team-a','/project/a',{'command':['pytest'],'stdout':'','stderr':'AssertionError: marker\n', 'exit_code':1})
   p.record('team-a','/project/a',{'command':['echo'],'stdout':'ok','stderr':'','exit_code':0})
   p.record('team-b','/project/a',{'command':['echo'],'stdout':'secret','stderr':'','exit_code':0})
   self.assertEqual(p.recall('team-a','/project/a',limit=1)['next_cursor'], 1)
   self.assertEqual(len(p.recall('team-b','/project/a')['items']), 1)
   self.assertIn('AssertionError', p.raw('team-a','/project/a',a.id)['text'])
 def test_cap_and_rtk_marker_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   rtk=Path(temp)/'rtk'; rtk.write_text(''); rtk.chmod(0o700); p=ContextPipeline(temp,rtk_path=rtk)
   with patch('context_pipeline.subprocess.run') as run:
    run.return_value.returncode=0; run.return_value.stdout='compressed'
    item=p.record('t','p',{'command':['pytest'],'stdout':'x'*(MAX_BYTES+4),'stderr':'FAILED marker','exit_code':1})
   self.assertEqual(item.rtk,'raw_fallback'); self.assertLessEqual(item.raw_bytes,MAX_BYTES); self.assertTrue(item.raw_truncated); self.assertGreater(item.original_raw_bytes, item.raw_bytes)
 def test_graph_is_explicit_and_broad_only(self):
  with tempfile.TemporaryDirectory() as temp:
   p=ContextPipeline(temp)
   self.assertEqual(p.query_graph(temp,'query')['status'],'deferred')
   self.assertEqual(p.query_graph(temp,'query',broad=True)['status'],'unavailable')
 def test_raw_retention_and_concurrent_index_are_bounded(self):
  with tempfile.TemporaryDirectory() as temp:
   p=ContextPipeline(temp)
   for i in range(MAX_RECORDS-8): p.record('t','p',{'command':['echo',str(i)],'stdout':str(i),'stderr':'','exit_code':0})
   threads=[threading.Thread(target=p.record,args=('t','p',{'command':['echo',str(i)],'stdout':str(i),'stderr':'','exit_code':0})) for i in range(MAX_RECORDS-8,MAX_RECORDS+8)]
   for thread in threads: thread.start()
   for thread in threads: thread.join()
   folder=next((Path(temp)/'context-evidence').glob('*/*'))
   self.assertEqual(len(p.recall('t','p',limit=50)['items']),50)
   self.assertEqual(len((folder/'index.jsonl').read_text().splitlines()),MAX_RECORDS)
   self.assertEqual(len(list(folder.glob('*.raw'))),MAX_RECORDS)
 def test_rtk_does_not_inherit_provider_secrets(self):
  with tempfile.TemporaryDirectory() as temp:
   rtk=Path(temp)/'rtk';rtk.write_text('');rtk.chmod(0o700);p=ContextPipeline(temp,rtk_path=rtk)
   with patch.dict(os.environ,{'FIXTURE_API_KEY':'secret','FIXTURE_TOKEN':'token'}), patch('context_pipeline.subprocess.run') as run:
    run.return_value.returncode=0;run.return_value.stdout='ok';p.record('t','p',{'command':['echo'],'stdout':'ok','stderr':'','exit_code':0})
   env=run.call_args.kwargs['env'];self.assertNotIn('FIXTURE_API_KEY',env);self.assertNotIn('FIXTURE_TOKEN',env)
if __name__ == '__main__': unittest.main()
