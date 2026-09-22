from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from codex_bridge import CodexBridge, _usage_summary
from test_codex_bridge import FakeFactory
from hq_tools import execute, tool_specs

class HQToolsTest(unittest.TestCase):
    def test_bound_native_client_tool_and_stale_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);project=path/'project';project.mkdir();factory=FakeFactory()
            bridge=CodexBridge(path/'state',connection_factory=factory)
            self.addCleanup(bridge.shutdown_all)
            bridge.start('team',project,'fixture','gpt-5.6-terra')
            conn=factory.connections[0]
            params={'threadId':'thr-1','turnId':'turn-1-1','tool':'hq_tasks','arguments':{'action':'list'},'callId':'call-1'}
            with patch('hq_tools.execute',return_value={'tasks':[]}) as call:
                conn.emit({'id':'tool-call','method':'item/tool/call','params':params})
                for _ in range(50):
                    if any(x.get('id')=='tool-call' and 'result' in x for x in conn.sent):break
                    time.sleep(.01)
                call.assert_called_once()
                result=next(x for x in conn.sent if x.get('id')=='tool-call' and 'result' in x)
                self.assertTrue(result['result']['success'])
                conn.emit({'id':'bad-call','method':'item/tool/call','params':{**params,'threadId':'unrelated'}})
                self.assertEqual(call.call_count,1)
                self.assertFalse(conn.sent[-1]['result']['success'])
            start=next(x for x in conn.sent if x.get('method')=='thread/start')
            self.assertEqual(start['params']['dynamicTools'],tool_specs())
    def test_planning_cannot_mark_tasks_and_strict_arguments(self):
        session=SimpleNamespace(team='team',mode='plan')
        with patch('hq_tools.TaskStore') as store:
            with self.assertRaises(ValueError):execute(None,session,'hq_tasks',{'action':'update','taskId':'t','status':'completed'})
            store.return_value.update.assert_not_called()
        with self.assertRaises(ValueError):execute(None,session,'hq_command',{'command':'pwd','project':'/tmp'})
    def test_reasoning_not_double_counted(self):
        value=_usage_summary({'total':{'inputTokens':100,'outputTokens':30,'reasoningOutputTokens':20,'totalTokens':130}})
        self.assertEqual(value['outputTokens'],30);self.assertEqual(value['reasoningTokens'],20);self.assertEqual(value['totalTokens'],130)

class AcceptedInputTest(unittest.TestCase):
    def test_archive_failure_does_not_resubmit_or_lose_accepted_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);project=path/'project';project.mkdir();factory=FakeFactory()
            bridge=CodexBridge(path/'state',connection_factory=factory)
            self.addCleanup(bridge.shutdown_all)
            with patch.object(bridge._transcripts,'record',side_effect=OSError('disk fixture')):
                result=bridge.start('team',project,'accepted fixture','gpt-5.6-terra')
            self.assertEqual(result['state'],'running');self.assertTrue(result['historyWarning'])
            self.assertEqual(len([x for x in factory.connections[0].sent if x.get('method')=='turn/start']),1)
            self.assertEqual([x['data']['text'] for x in bridge.events('team')['events'] if x['type']=='message.user'],['accepted fixture'])
            bridge._event(bridge._require_session('team'),'fixture.retry',{})
            self.assertIsNone(bridge.status('team')['historyWarning'])
            self.assertEqual(bridge._transcripts.page('team')['events'][0]['data']['text'],'accepted fixture')
    def test_stop_winning_action_lock_rejects_delayed_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);project=path/'project';project.mkdir();factory=FakeFactory()
            bridge=CodexBridge(path/'state',connection_factory=factory);self.addCleanup(bridge.shutdown_all)
            bridge.start('team',project,'fixture','gpt-5.6-terra');session=bridge._require_session('team');conn=factory.connections[0]
            with patch('hq_tools.execute') as execute_tool:
                with session.operation_lock:
                    conn.emit({'id':'delayed','method':'item/tool/call','params':{'threadId':'thr-1','turnId':'turn-1-1','tool':'hq_tasks','arguments':{'action':'list'},'callId':'call'}})
                    bridge.stop('team')
                for _ in range(50):
                    if any(x.get('id')=='delayed' and 'result' in x for x in conn.sent):break
                    time.sleep(.01)
                execute_tool.assert_not_called()
                self.assertFalse(next(x for x in conn.sent if x.get('id')=='delayed')['result']['success'])
