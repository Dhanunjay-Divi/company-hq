"""No account reads, provider calls, or prompts."""
import unittest
from unittest.mock import patch
from claude_connection import ClaudeConnection,official_url
import claude_tasks

class ClaudeConnectionTests(unittest.TestCase):
    def test_login_links_only_allow_official_https_hosts(self):
        self.assertTrue(official_url('https://claude.ai/oauth/authorize?code=example'))
        for url in ['http://claude.ai','https://claude.ai.evil.example/','https://user@claude.ai','file:///tmp/x','https://claude.ai:444','https://evil.example/?next=https://claude.ai']:
            self.assertFalse(official_url(url),url)
    def test_signed_out_check_does_not_initialize_a_session(self):
        with patch('claude_runtime.probe',return_value={'installed':True,'version':'test','authenticated':False}),patch('claude_runtime.runtime') as runtime:
            value=ClaudeConnection().check()
        runtime.assert_not_called();self.assertEqual(value['authentication'],'sign_in_required');self.assertEqual(value['models'],[])
    def test_missing_runtime_does_not_offer_desktop_login_as_connection(self):
        with patch('claude_runtime.probe',return_value={'installed':False,'authenticated':False}),patch('claude_runtime.runtime') as runtime:
            value=ClaudeConnection().check()
        runtime.assert_not_called()
        self.assertEqual(value['authentication'],'not_installed')
        self.assertFalse(value['runtimeReady'])
        self.assertIn('separate',value['message'])
    def test_metadata_filters_are_bounded_before_execution(self):
        with patch.object(claude_tasks,'_call',return_value={}) as call:
            for cursor in ['../x','0; echo x','-1','12345678']:
                with self.assertRaises(ValueError):claude_tasks.list_tasks(cursor=cursor)
            with self.assertRaises(ValueError):claude_tasks.read_task('../private')
            with self.assertRaises(ValueError):claude_tasks.list_tasks(archived=True)
            call.assert_not_called()
            claude_tasks.list_tasks(cursor='30',include_agents=True)
            self.assertEqual(call.call_args.args[0]['offset'],30)
