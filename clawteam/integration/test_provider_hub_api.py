from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import hq_api
from provider_hub import ProviderHub
from test_provider_hub import FakeCodex,FakeClaude

class Handler:
    def __init__(self,path=''):self.path=path;self.response=None;self.error=None
    def _serve_json(self,value):self.response=value
    def _json_error(self,status,message):self.error=(status,message)

class ProviderHubAPITest(unittest.TestCase):
    def test_shutdown_does_not_create_state_or_reopen_runtime(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temp,patch.dict(hq_api._provider_hubs,{},clear=True):
            state=Path(temp)/'unused'
            hq_api.shutdown_runtime(state)
            self.assertFalse(state.exists())
            hub=Mock();hq_api._provider_hubs[(state/'runtime').resolve()]=hub
            hq_api.shutdown_runtime(state);hq_api.shutdown_runtime(state)
            hub.shutdown_all.assert_called_once()
            self.assertFalse(state.exists())

    def test_claude_selected_via_route_then_restart_keeps_provider_and_history(self):
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp)/'state';project=Path(temp)/'project';project.mkdir()
            hub=ProviderHub(state/'runtime',codex=FakeCodex(),runtime_factory=lambda provider,**kwargs:FakeClaude(**kwargs))
            with patch('hq_api.bridge',return_value=hub),patch('hq_api.project_for',return_value=project),patch('hq_api.demo_mode',return_value=False):
                handler=Handler()
                hq_api.handle_post(handler,state,'/api/runtime/fixture/start',{'provider':'claude','model':'sonnet','prompt':'fixture acceptance','workMode':'auto'})
                self.assertIsNone(handler.error);self.assertEqual(handler.response['provider'],'claude')
                handler=Handler('/api/runtime/fixture/status');hq_api.handle_get(handler,state)
                self.assertEqual(handler.response['provider'],'claude');self.assertEqual(handler.response['mode'],'execute')
            hub.shutdown_all()
            recovered=ProviderHub(state/'runtime',codex=FakeCodex(),runtime_factory=lambda provider,**kwargs:FakeClaude(**kwargs))
            self.addCleanup(recovered.shutdown_all)
            with patch('hq_api.bridge',return_value=recovered),patch('hq_api.project_for',return_value=project):
                handler=Handler('/api/runtime/fixture/status');hq_api.handle_get(handler,state)
                self.assertEqual(handler.response['provider'],'claude')
                handler=Handler('/api/runtime/fixture/history');hq_api.handle_get(handler,state)
                self.assertTrue(any(e['type']=='message.user' and e['data']['text']=='fixture acceptance' for e in handler.response['events']))
    def test_unknown_provider_never_starts_native_runtime(self):
        with tempfile.TemporaryDirectory() as temp,patch('hq_api.bridge') as bridge,patch('hq_api.project_for',return_value=Path(temp)),patch('hq_api.demo_mode',return_value=False):
            handler=Handler();hq_api.handle_post(handler,Path(temp),'/api/runtime/fixture/start',{'provider':'grok','model':'invented','prompt':'fixture'})
            self.assertEqual(handler.error[0],400);bridge.return_value.start.assert_not_called()
