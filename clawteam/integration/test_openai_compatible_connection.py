"""Fixture-only OpenAI-compatible connection checks; no network or live keys."""
import json
import threading
import unittest
from urllib import error

from openai_compatible_connection import (
    MAX_RESPONSE,
    PROBE_MAX_TOKENS,
    OpenAICompatibleConnection,
    _parse_models,
    validated_base_url,
)

BASE = "https://api.example.com/v1"
MODELS_BODY = b'{"object":"list","data":[{"id":"fixture-model","object":"model","owned_by":"fixture"}]}'
CHAT_BODY = b'{"choices":[{"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}'


class Response:
    def __init__(self, body, url):
        self.body, self.url = body, url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, n):
        return self.body

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, rows=()):
        self.rows, self.requests = list(rows), []

    def open(self, req, timeout):
        self.requests.append(req)
        if not self.rows:
            raise error.URLError("fixture: no scripted response")
        value = self.rows.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def models_response(url=BASE + "/models", body=MODELS_BODY):
    return Response(body, url)


def http_error(code):
    return error.HTTPError("https://api.example.com/fixture", code, "fixture", None, None)


class OpenAICompatibleConnectionTests(unittest.TestCase):
    def test_base_url_requires_https_or_loopback_http(self):
        self.assertEqual(validated_base_url("https://api.example.com/v1/"), "https://api.example.com/v1")
        self.assertEqual(validated_base_url(" http://127.0.0.1:8000/v1 "), "http://127.0.0.1:8000/v1")
        self.assertEqual(validated_base_url("http://localhost:11434"), "http://localhost:11434")
        self.assertEqual(validated_base_url("http://[::1]:8080/v1"), "http://[::1]:8080/v1")
        self.assertEqual(validated_base_url("http://127.8.8.8/v1"), "http://127.8.8.8/v1")
        for value in (
            None, 123, "", "   ", "api.example.com/v1", "ftp://api.example.com/v1",
            "http://api.example.com/v1", "http://192.168.1.5/v1", "https://",
            "https://user:pass@api.example.com/v1", "https://api.example.com/v1?x=1",
            "https://api.example.com/v1#frag", "https://api.example.com:99999/v1",
            "https://exämple.com/v1", "https://api.example.com/v1 has space",
        ):
            with self.assertRaises(ValueError, msg=repr(value)):
                validated_base_url(value)

    def test_invalid_configuration_never_reaches_the_network(self):
        opener = Opener()
        conn = OpenAICompatibleConnection(opener=opener)
        for kwargs in (
            {"base_url": "http://api.example.com/v1", "model": "m"},
            {"base_url": BASE, "model": ""},
            {"base_url": BASE, "model": "x" * 201},
            {"base_url": BASE, "model": "bad model"},
            {"base_url": BASE, "model": "m", "api_key": "bad\nkey"},
            {"base_url": BASE, "model": "m", "temperature": 7},
            {"base_url": BASE, "model": "m", "temperature": "warm"},
            {"base_url": BASE, "model": "m", "context_hint": 10},
        ):
            with self.assertRaises(ValueError, msg=repr(kwargs)):
                conn.connect(**kwargs)
        self.assertEqual(opener.requests, [])

    def test_connect_lists_models_with_key_and_redacts_everywhere(self):
        opener = Opener([models_response()])
        conn = OpenAICompatibleConnection(opener=opener)
        value = conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "signed_in")
        self.assertTrue(value["signed_in"])
        self.assertEqual(value["models"], ["fixture-model"])
        self.assertEqual(value["modelDetails"][0]["ownedBy"], "fixture")
        self.assertEqual(value["verification"], "model_listing")
        self.assertTrue(value["runtimeReady"])
        self.assertIn("not generation proof", value["message"])
        self.assertIn("checkedAt", value)
        self.assertEqual(opener.requests[0].full_url, BASE + "/models")
        self.assertEqual(opener.requests[0].get_header("Authorization"), "Bearer fixture-secret")
        self.assertNotIn("fixture-secret", repr(value))
        self.assertNotIn("fixture-secret", json.dumps(value))
        self.assertEqual(conn.config_for_runtime()["key"], "fixture-secret")
        self.assertEqual(conn.key_for_runtime(), "fixture-secret")
        value["modelDetails"][0]["value"] = "mutated"
        self.assertEqual(conn.snapshot()["models"], ["fixture-model"])

    def test_connect_without_key_omits_authorization(self):
        opener = Opener([models_response()])
        conn = OpenAICompatibleConnection(opener=opener)
        value = conn.connect(base_url=BASE, model="fixture-model", api_key="  ")
        self.assertEqual(value["authentication"], "signed_in")
        self.assertIn("without a key", value["message"])
        self.assertIsNone(opener.requests[0].get_header("Authorization"))
        self.assertIsNone(conn.key_for_runtime())

    def test_redirects_are_refused_and_clear_the_session(self):
        redirected = Opener([models_response(url="https://elsewhere.example/v1/models")])
        conn = OpenAICompatibleConnection(opener=redirected)
        value = conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "connection_failed")
        self.assertIn("redirect", value["message"])
        self.assertIsNone(conn.key_for_runtime())
        self.assertIsNone(conn.config_for_runtime())
        self.assertNotIn("fixture-secret", repr(value))
        moved = OpenAICompatibleConnection(opener=Opener([http_error(302)]))
        value = moved.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "connection_failed")
        self.assertIn("redirect", value["message"])

    def test_auth_failures_require_sign_in_and_drop_the_key(self):
        conn = OpenAICompatibleConnection(opener=Opener([http_error(401)]))
        value = conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "sign_in_required")
        self.assertFalse(value["signed_in"])
        self.assertIsNone(value["verification"])
        self.assertEqual(value["models"], [])
        self.assertIn("rejected the API key", value["message"])
        self.assertIsNone(conn.key_for_runtime())
        keyless = OpenAICompatibleConnection(opener=Opener([http_error(403)]))
        value = keyless.connect(base_url=BASE, model="fixture-model")
        self.assertEqual(value["authentication"], "sign_in_required")
        self.assertIn("requires an API key", value["message"])

    def test_unsupported_listing_stays_unverified_until_a_generation_test(self):
        opener = Opener([http_error(404)])
        conn = OpenAICompatibleConnection(opener=opener)
        value = conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "not_checked")
        self.assertIsNone(value["verification"])
        self.assertFalse(value["runtimeReady"])
        self.assertIn("generation test", value["message"])
        # The quota-consuming chat-completion probe never runs implicitly.
        self.assertEqual(len(opener.requests), 1)
        self.assertIsNone(conn.config_for_runtime())
        self.assertIsNone(conn.key_for_runtime())
        opener.rows.append(Response(CHAT_BODY, BASE + "/chat/completions"))
        value = conn.test_generation()
        self.assertEqual(value["authentication"], "signed_in")
        self.assertEqual(value["verification"], "generation")
        self.assertEqual(value["models"], ["fixture-model"])

    def test_unlisted_model_requires_explicit_generation_proof(self):
        opener = Opener([models_response(), Response(CHAT_BODY, BASE + "/chat/completions")])
        conn = OpenAICompatibleConnection(opener=opener)
        value = conn.connect(base_url=BASE, model="other-model", api_key="fixture-secret")
        self.assertEqual(value["authentication"], "model_unavailable")
        self.assertFalse(value["runtimeReady"])
        self.assertIsNone(conn.config_for_runtime())
        self.assertEqual(len(opener.requests), 1)
        proven = conn.test_generation()
        self.assertEqual(proven["verification"], "generation")
        self.assertIn("other-model", proven["models"])
        self.assertEqual(conn.config_for_runtime()["model"], "other-model")

    def test_generation_test_distinguishes_listing_from_generation_proof(self):
        opener = Opener([models_response(), Response(CHAT_BODY, BASE + "/chat/completions")])
        conn = OpenAICompatibleConnection(opener=opener)
        conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(conn.snapshot()["verification"], "model_listing")
        value = conn.test_generation()
        self.assertEqual(value["authentication"], "signed_in")
        self.assertEqual(value["verification"], "generation")
        self.assertIn("generated text", value["message"])
        request = opener.requests[1]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, BASE + "/chat/completions")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "fixture-model")
        self.assertEqual(payload["max_tokens"], PROBE_MAX_TOKENS)
        self.assertEqual(len(payload["messages"]), 1)
        self.assertNotIn("tools", payload)
        self.assertNotIn("stream", payload)
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-secret")
        self.assertNotIn("fixture-secret", json.dumps(value))

    def test_generation_test_failures_report_without_proof(self):
        empty = OpenAICompatibleConnection(opener=Opener([
            models_response(),
            Response(b'{"choices":[{"message":{"role":"assistant","content":"  "}}]}', BASE + "/chat/completions"),
        ]))
        empty.connect(base_url=BASE, model="fixture-model")
        value = empty.test_generation()
        self.assertEqual(value["authentication"], "connection_failed")
        self.assertIsNone(value["verification"])
        self.assertIn("no assistant text", value["message"])
        broken = OpenAICompatibleConnection(opener=Opener([models_response(), http_error(500)]))
        broken.connect(base_url=BASE, model="fixture-model")
        value = broken.test_generation()
        self.assertEqual(value["authentication"], "connection_failed")
        self.assertIn("HTTP 500", value["message"])
        unconfigured_opener = Opener()
        unconfigured = OpenAICompatibleConnection(opener=unconfigured_opener)
        self.assertEqual(unconfigured.test_generation()["authentication"], "not_checked")
        self.assertEqual(unconfigured_opener.requests, [])

    def test_check_reverifies_and_close_wins_over_inflight_connect(self):
        opener = Opener([models_response(), models_response(), http_error(500)])
        conn = OpenAICompatibleConnection(opener=opener)
        conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        self.assertEqual(conn.check()["authentication"], "signed_in")
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(conn.check()["authentication"], "connection_failed")
        self.assertIsNone(conn.key_for_runtime())

        entered, release = threading.Event(), threading.Event()

        class Blocking(Opener):
            def open(self, req, timeout):
                entered.set()
                release.wait(2)
                return super().open(req, timeout)

        blocking = Blocking([models_response()])
        slow = OpenAICompatibleConnection(opener=blocking)
        thread = threading.Thread(target=lambda: slow.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret"))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            slow.close()
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(slow.key_for_runtime())
        closed = slow.snapshot()
        self.assertFalse(closed["signed_in"])
        self.assertEqual(closed["authentication"], "not_checked")
        self.assertIn("closed", closed["message"].lower())
        self.assertIsNone(slow.config_for_runtime())

    def test_check_keeps_earlier_generation_proof(self):
        opener = Opener([
            models_response(),
            Response(CHAT_BODY, BASE + "/chat/completions"),
            models_response(),
        ])
        conn = OpenAICompatibleConnection(opener=opener)
        conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        conn.test_generation()
        self.assertEqual(conn.check()["verification"], "generation")

    def test_transport_bounds_and_sanitizes_responses(self):
        oversized = OpenAICompatibleConnection(opener=Opener([Response(b"x" * (MAX_RESPONSE + 1), BASE + "/models")]))
        value = oversized.connect(base_url=BASE, model="fixture-model")
        self.assertEqual(value["authentication"], "connection_failed")
        self.assertIn("too large", value["message"])
        invalid = OpenAICompatibleConnection(opener=Opener([Response(b"not json", BASE + "/models")]))
        self.assertIn("invalid JSON", invalid.connect(base_url=BASE, model="fixture-model")["message"])
        unreachable = OpenAICompatibleConnection(opener=Opener([error.URLError("fixture down")]))
        self.assertIn("request failed", unreachable.connect(base_url=BASE, model="fixture-model")["message"])

    def test_model_listing_parse_rejects_unsafe_rows(self):
        rows = {"data": [{"id": "x" * 201}, {"id": "bad id"}, {"id": "same"}, {"id": "same"}, {"id": "ok", "owned_by": "fixture"}, "not-a-dict"]}
        self.assertEqual(_parse_models(rows), [{"value": "same"}, {"value": "ok", "ownedBy": "fixture"}])
        self.assertEqual(_parse_models([{"id": "bare"}]), [{"value": "bare"}])
        self.assertEqual(_parse_models({"data": "nope"}), [])


if __name__ == "__main__":
    unittest.main()
