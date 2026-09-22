from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import runtime_actions


class NativeCommandTest(unittest.TestCase):
    def test_each_access_mode_is_sent_to_native_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            for mode, policy in [('plan','readOnly'),('execute','workspaceWrite'),('full','dangerFullAccess')]:
                bridge = Mock()
                bridge._require_session.return_value = SimpleNamespace(operation_lock=threading.Lock(),mode=mode,
                    connection=SimpleNamespace(running=lambda:True),project=state/'project')
                bridge._rpc.return_value = {'exitCode': 1, 'stdout': 'FAILED fixture.py:10', 'stderr': ''}
                with patch('runtime_actions.pipeline') as pipeline:
                    pipeline.return_value.record.return_value = SimpleNamespace(id='fixture',compact=None,raw_truncated=False,raw_bytes=20,compact_bytes=None,rtk='raw_fallback')
                    response=runtime_actions.command(bridge,state,'alpha','python -m pytest')
                method, params=bridge._rpc.call_args.args[1:]
                self.assertEqual(method,'command/exec')
                self.assertEqual(params['sandboxPolicy']['type'],policy)
                if mode=='execute': self.assertEqual(params['sandboxPolicy']['writableRoots'],[str(state/'project')])
                self.assertEqual(response['exitCode'],1)
                self.assertIn('FAILED',response['output'])

    def test_demo_never_executes(self):
        bridge=Mock()
        with patch('runtime_actions.demo_mode',return_value=True), self.assertRaises(ValueError):
            runtime_actions.command(bridge,Path('/tmp'),'alpha','ls')
        bridge._rpc.assert_not_called()


if __name__ == '__main__': unittest.main()
