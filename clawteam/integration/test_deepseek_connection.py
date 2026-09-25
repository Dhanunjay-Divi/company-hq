"""Fixture-only DeepSeek connection checks."""
import io
import threading
import unittest

from deepseek_connection import DeepSeekConnection


class Response:
    def __init__(self, body, url): self.body, self.url = body, url
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.body
    def geturl(self): return self.url


class Opener:
    def __init__(self, rows): self.rows, self.requests = list(rows), []
    def open(self, req, timeout):
        self.requests.append(req); value = self.rows.pop(0)
        if isinstance(value, Exception): raise value
        return value


class DeepSeekConnectionTests(unittest.TestCase):
    def test_close_wins_over_inflight_connection(self):
        entered, release = threading.Event(), threading.Event()
        class BlockingOpener(Opener):
            def open(self, req, timeout):
                entered.set()
                self.assert_released = release.wait(2)
                return super().open(req, timeout)
        opener = BlockingOpener([Response(b'{"data":[{"id":"model-a"}]}', 'https://api.deepseek.com/models'), Response(b'{}', 'https://api.deepseek.com/user/balance')])
        conn = DeepSeekConnection(opener=opener)
        thread = threading.Thread(target=lambda: conn.connect('fixture-secret'))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            conn.close()
        finally:
            release.set(); thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(conn.key_for_runtime())
        self.assertFalse(conn.snapshot()['signed_in'])
        self.assertEqual(conn.snapshot()['models'], [])

    def test_models_and_optional_balance_are_parsed_without_key_exposure(self):
        opener = Opener([Response(b'{"data":[{"id":"model-a","object":"model","owned_by":"deepseek"}]}', 'https://api.deepseek.com/models'), Response(b'{"is_available":true,"balance_infos":[{"currency":"CNY","total_balance":"3.00","granted_balance":"1","topped_up_balance":"2"},{"currency":"USD","total_balance":"NaN"}]}', 'https://api.deepseek.com/user/balance')])
        value = DeepSeekConnection(opener=opener, binary=lambda: '/fixture/claude').connect('secret-key')
        self.assertEqual(value['authentication'], 'signed_in'); self.assertEqual(value['models'], ['model-a'])
        self.assertEqual(value['balances'][0]['total_balance'], '3.00'); self.assertNotIn('secret-key', repr(value))
        self.assertEqual(opener.requests[0].get_header('Authorization'), 'Bearer secret-key')

    def test_failed_auth_or_redirect_clears_prior_session_state(self):
        good = Response(b'{"data":[{"id":"model-a"}]}', 'https://api.deepseek.com/models')
        balance = Response(b'{}', 'https://api.deepseek.com/user/balance')
        bad = Response(b'{}', 'https://elsewhere.example/models')
        conn = DeepSeekConnection(opener=Opener([good, balance, bad]))
        conn.connect('good'); value = conn.check()
        self.assertEqual(value['authentication'], 'sign_in_required'); self.assertEqual(value['models'], [])
        self.assertIsNone(conn.key_for_runtime())

    def test_invalid_key_never_requests_and_close_is_session_only(self):
        opener = Opener([]); conn = DeepSeekConnection(opener=opener)
        self.assertEqual(conn.connect(' bad ')['authentication'], 'sign_in_required'); self.assertEqual(opener.requests, [])
        conn.close(); self.assertIsNone(conn.key_for_runtime())

    def test_models_and_snapshots_reject_or_isolate_unsafe_data(self):
        self.assertEqual(DeepSeekConnection._models({'data': [{'id': 'x' * 201}, {'id': 'ok\n'}, {'id': 'same'}, {'id': 'same'}]}), [{'value': 'same'}])
        conn = DeepSeekConnection(opener=Opener([Response(b'{"data":[{"id":"safe"}]}', 'https://api.deepseek.com/models'), Response(b'{}', 'https://api.deepseek.com/user/balance')]))
        snapshot = conn.connect('safe-key'); snapshot['modelDetails'][0]['value'] = 'mutated'
        self.assertEqual(conn.snapshot()['modelDetails'][0]['value'], 'safe'); self.assertIn('checkedAt', snapshot)
