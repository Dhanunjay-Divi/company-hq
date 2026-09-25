"""Read-only, bounded ZCode child-session inventory fixtures."""
from __future__ import annotations

import unittest

from zcode_runtime import ZCodeRuntime


class Rpc:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def request(self, method, params, timeout=25):
        self.calls.append((method, params))
        return self.pages[params.get('endedCursor')]


class ZCodeWorkersTest(unittest.TestCase):
    def test_paginates_and_normalizes_only_verified_fields(self):
        pages = {
            None: {'revision': 7, 'childSessionIds': ['child-a', 'child-b', 'child-c'],
                   'running': [{'childSessionId': 'child-a', 'status': 'running', 'subagentType': 'research', 'title': 'Find facts'}],
                   'ended': {'total': 2, 'items': [{'childSessionId': 'child-b', 'status': 'success', 'agentId': 'agent-b'}], 'nextCursor': 'page-2'}},
            'page-2': {'revision': 7, 'childSessionIds': ['child-a', 'child-b', 'child-c'],
                       'running': [{'childSessionId': 'child-a', 'status': 'running', 'subagentType': 'research', 'title': 'Find facts'}],
                       'ended': {'total': 2, 'items': [{'childSessionId': 'child-c', 'status': 'cancelled', 'summary': 'Stopped'}]}},
        }
        runtime = ZCodeRuntime(session_id='root-session'); runtime.rpc = Rpc(pages)
        result = runtime.workers()
        self.assertTrue(result['available'])
        self.assertTrue(result['complete'])
        self.assertEqual(result['revision'], 7)
        self.assertEqual([row['threadId'] for row in result['workers']], ['child-a', 'child-b', 'child-c'])
        self.assertEqual(result['workers'][0], {'threadId': 'child-a', 'childThreadId': 'child-a', 'parentThreadId': 'root-session', 'status': 'running', 'nativeStatus': 'running', 'source': 'zcode-subagents', 'title': 'Find facts', 'role': 'research'})
        self.assertEqual(result['workers'][1]['status'], 'completed')
        self.assertEqual(result['workers'][2]['status'], 'stopped')
        self.assertNotIn('model', result['workers'][0])
        self.assertNotIn('nickname', result['workers'][0])
        self.assertEqual(runtime.status()['nativeStatus']['childrenVerified'], True)
        self.assertEqual(runtime.status()['nativeStatus']['activeChildCount'], 1)
        self.assertEqual(runtime.rpc.calls, [
            ('session/subagents', {'sessionId': 'root-session', 'endedLimit': 50}),
            ('session/subagents', {'sessionId': 'root-session', 'endedLimit': 50, 'endedCursor': 'page-2'}),
        ])

    def test_incomplete_or_unavailable_inventory_blocks_handoff(self):
        runtime = ZCodeRuntime(session_id='root-session')
        self.assertIsNone(runtime.status()['children'])
        runtime.rpc = Rpc({None: {'revision': 1, 'childSessionIds': ['child-a'], 'running': [], 'ended': {'total': 1, 'items': []}}})
        result = runtime.workers()
        self.assertFalse(result['available'])
        self.assertFalse(result['complete'])
        self.assertIsNone(result['workers'])
        self.assertIn('incomplete', result['error'])
        self.assertIsNone(runtime.status()['children'])
        self.assertEqual(runtime.status()['nativeStatus']['childrenVerified'], False)
        self.assertIsNone(runtime.status()['nativeStatus']['activeChildCount'])


if __name__ == '__main__':
    unittest.main()
