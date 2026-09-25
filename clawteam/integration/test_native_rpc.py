"""Exercise both wire dialects against a tiny actual stdio process, not a model."""
import sys
import tempfile
import unittest
from native_rpc import NativeRpc
from provider_runtime import ProviderRuntimeError

SERVER = r'''
import json,sys
for line in sys.stdin:
 d=json.loads(line)
 if d.get('method')=='fail':
  v={'id':d['id'],'error':{'code':403,'message':'Your current subscription does not have access to Kimi Code right now'}}
 else:v={'id':d['id'],'result':{'identifierType':type(d['id']).__name__,'jsonrpc':d.get('jsonrpc'),'params':d.get('params')}}
 print(json.dumps(v),flush=True)
'''
class NativeRpcTest(unittest.TestCase):
 def test_dialects_keep_ids_and_envelopes_compatible(self):
  with tempfile.TemporaryDirectory() as folder:
   for dialect,kind,version in [('jsonrpc','int','2.0'),('zcode','str',None)]:
    rpc=NativeRpc([sys.executable,'-u','-c',SERVER],folder,lambda value:None,dialect=dialect)
    try:
     result=rpc.request('echo',{'value':'hello'})
     self.assertEqual((result['identifierType'],result['jsonrpc']),(kind,version))
     self.assertEqual(result['params'],{'value':'hello'})
    finally:rpc.close()
 def test_subscription_error_is_actionable_without_echoing_raw_response(self):
  with tempfile.TemporaryDirectory() as folder:
   rpc=NativeRpc([sys.executable,'-u','-c',SERVER],folder,lambda value:None)
   try:
    with self.assertRaisesRegex(ProviderRuntimeError,'Activate the coding subscription'):
     rpc.request('fail',{})
   finally:rpc.close()
