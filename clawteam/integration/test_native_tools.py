from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from native_tools import inventory


class NativeToolsInventoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-tools-')
        self.root = Path(self.temporary.name)
        for area in ('design', 'engineering'):
            folder = self.root / 'agency-agents' / 'upstream' / area
            folder.mkdir(parents=True)
            (folder / f'{area}.md').write_text('# role')

    def tearDown(self):
        self.temporary.cleanup()

    def test_paginates_and_stops_cursor_cycle_without_repeating_servers(self):
        pages = {
            None: {'data': [{'name': 'memory', 'runtimeStatus': 'connected', 'tools': {'lookup': {}}}], 'nextCursor': 'a'},
            'a': {'data': [{'name': 'browser', 'runtimeStatus': 'connected', 'tools': {'browse': {}}}], 'nextCursor': 'b'},
            'b': {'data': [{'name': 'duplicate-page', 'runtimeStatus': 'connected', 'tools': {}}], 'nextCursor': 'a'},
        }
        def rpc(method, params):
            if method == 'mcpServerStatus/list': return pages[params.get('cursor')]
            if method == 'app/installed': return {'apps': []}
            if method == 'skills/list': return {'data': []}
            raise AssertionError(method)
        value = inventory(rpc, 'thread-1', '/project', self.root)
        self.assertEqual([server['name'] for server in value['servers']], ['memory', 'browser', 'duplicate-page'])
        self.assertTrue(value['truncated'])
        self.assertEqual(value['roleLibrary']['count'], 2)

    def test_projects_schema_without_sensitive_fields(self):
        def rpc(method, _params):
            if method == 'mcpServerStatus/list': return {'data': [{'name': 'private-server', 'runtimeStatus': 'connected', 'authStatus': 'ready', 'path': '/private/path', 'token': 'secret', 'tools': {'safe': {}, 'alsoSafe': {}}}]}
            if method == 'app/installed': return {'apps': [{'id': 'app-one', 'runtimeName': 'App One', 'enabled': True, 'callable': True, 'credentials': 'secret'}]}
            if method == 'skills/list': return {'data': [{'skills': [{'name': 'safe-skill', 'description': 'x' * 900, 'enabled': True, 'path': '/private/skill'}]}]}
            raise AssertionError(method)
        value = inventory(rpc, 'thread-1', '/project', self.root)
        self.assertEqual(set(value['servers'][0]), {'name', 'authStatus', 'runtimeStatus', 'tools', 'toolsError'})
        self.assertEqual(value['apps'], [{'id': 'app-one', 'name': 'App One', 'enabled': True, 'callable': True}])
        self.assertEqual(len(value['skills'][0]['description']), 600)
        self.assertNotIn('secret', repr(value))
        self.assertNotIn('/private', repr(value))

    def test_partial_and_null_failures_keep_other_inventory_and_report_generic_errors(self):
        def rpc(method, _params):
            if method == 'mcpServerStatus/list': return None
            if method == 'app/installed': return {'apps': [{'id': 'callable', 'enabled': True, 'callable': True}, None]}
            if method == 'skills/list': return {'data': [{'skills': None, 'errors': ['bad file']}, None]}
            raise AssertionError(method)
        value = inventory(rpc, 'thread-1', '/project', self.root)
        self.assertEqual(value['servers'], [])
        self.assertEqual(value['apps'][0]['id'], 'callable')
        self.assertEqual(value['skills'], [])
        self.assertEqual({error['source'] for error in value['errors']}, {'MCP', 'Skills'})
        self.assertTrue(all('/' not in error['message'] for error in value['errors']))
