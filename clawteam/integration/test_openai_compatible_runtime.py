"""Fixture-only OpenAI-compatible runtime checks; no network or live keys."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from openai_compatible_connection import OpenAICompatibleConnection, TransportError
from openai_compatible_runtime import (
    MAX_ASSISTANT_CHARS,
    MAX_HISTORY_MESSAGES,
    OpenAICompatibleRuntime,
)
from provider_runtime import ProviderRuntimeError

BASE = "https://api.example.com/v1"
REPLY = {"choices": [{"message": {"role": "assistant", "content": "fixture reply"}, "finish_reason": "stop"}]}


class FakeTransport:
    """Scripted chat-completion double; records every outbound request."""

    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])
        self.holding = False
        self.hold = threading.Event()

    def __call__(self, url, payload, headers, timeout):
        self.calls.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        if self.holding:
            self.hold.wait(5)
        value = self.results.pop(0) if self.results else REPLY
        if isinstance(value, Exception):
            raise value
        return value


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
            raise TransportError("fixture: no scripted response")
        value = self.rows.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def wait_for(predicate, timeout=5.0, message="fixture condition not met"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(message)


def find_event(runtime, type_):
    matches = [event for event in runtime.events()["events"] if event["type"] == type_]
    return matches[-1] if matches else None


def count_events(runtime, type_):
    return sum(1 for event in runtime.events()["events"] if event["type"] == type_)


class OpenAICompatibleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        self.addCleanup(self.temp.cleanup)

    def make(self, **kwargs):
        transport = kwargs.pop("transport", FakeTransport())
        return OpenAICompatibleRuntime(post=transport, **kwargs), transport

    def completed(self, runtime):
        wait_for(lambda: find_event(runtime, "message.completed") is not None)
        return find_event(runtime, "message.completed")

    def test_turn_lifecycle_and_bounded_request_shape(self):
        runtime, transport = self.make(model="fixture-model", base_url=BASE, api_key="fixture-secret", temperature=0.5, max_output_tokens=512, timeout=7.5)
        result = runtime.start("Hello", project=self.project)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["provider"], "openai-compatible")
        self.assertTrue(result["turnId"] and result["itemId"] and result["sessionId"])
        completed = self.completed(runtime)
        self.assertEqual(completed["data"]["text"], "fixture reply")
        self.assertEqual(completed["data"]["turnId"], result["turnId"])
        self.assertEqual(completed["data"]["itemId"], result["itemId"])
        self.assertEqual(completed["data"]["sessionId"], result["sessionId"])
        started = find_event(runtime, "runtime.started")
        self.assertEqual(started["data"], {"project": str(self.project.resolve()), "sessionId": result["sessionId"], "model": "fixture-model"})
        call = transport.calls[0]
        self.assertEqual(call["url"], BASE + "/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer fixture-secret")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertEqual(call["timeout"], 7.5)
        self.assertEqual(call["payload"]["model"], "fixture-model")
        self.assertEqual(call["payload"]["max_tokens"], 512)
        self.assertEqual(call["payload"]["temperature"], 0.5)
        self.assertEqual(call["payload"]["messages"], [{"role": "user", "content": "Hello"}])
        self.assertNotIn("tools", call["payload"])
        status = runtime.status()
        self.assertEqual(status["state"], "idle")
        self.assertEqual(status["transport"], "openai-chat-completions-v1")
        self.assertEqual(status["turns"], 1)
        self.assertEqual(status["endpoint"], "https://api.example.com")
        self.assertEqual(status["project"], str(self.project.resolve()))
        self.assertNotIn("fixture-secret", json.dumps(status))
        runtime.send("Again")
        wait_for(lambda: count_events(runtime, "message.completed") == 2)
        second = transport.calls[1]
        self.assertEqual([message["role"] for message in second["payload"]["messages"]], ["user", "assistant", "user"])
        self.assertEqual(runtime.status()["turns"], 2)

    def test_usage_and_finish_reason_reported_only_when_native(self):
        runtime, _ = self.make(model="m", base_url=BASE, transport=FakeTransport([
            {"choices": [{"message": {"content": "counted"}, "finish_reason": "length"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}},
        ]))
        runtime.start("hi", project=self.project)
        completed = self.completed(runtime)
        self.assertEqual(completed["data"]["usage"], {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5})
        self.assertEqual(completed["data"]["finishReason"], "length")
        runtime, _ = self.make(model="m", base_url=BASE, transport=FakeTransport([
            {"choices": [{"message": {"content": "no usage"}}], "usage": {"prompt_tokens": "many"}},
        ]))
        runtime.start("hi", project=self.project)
        completed = self.completed(runtime)
        self.assertNotIn("usage", completed["data"])
        self.assertNotIn("finishReason", completed["data"])

    def test_stop_cancels_the_running_turn_and_rebinds_fresh(self):
        runtime, transport = self.make(model="m", base_url=BASE)
        transport.holding = True
        result = runtime.start("long work", project=self.project)
        wait_for(lambda: transport.calls)
        self.assertEqual(runtime.status()["state"], "running")
        stopped = runtime.stop()
        self.assertEqual(stopped, {"accepted": True, "sessionId": result["sessionId"]})
        self.assertEqual(runtime.status()["state"], "offline")
        transport.hold.set()
        if runtime._worker:
            runtime._worker.join(2)
        self.assertIsNone(find_event(runtime, "message.completed"))
        self.assertIsNotNone(find_event(runtime, "runtime.stopped"))
        status = runtime.status()
        self.assertIsNone(status["project"])
        self.assertIsNone(status["sessionId"])
        self.assertEqual(status["turns"], 0)
        with self.assertRaisesRegex(ProviderRuntimeError, "not started"):
            runtime.send("late")
        transport.holding = False
        other = Path(self.temp.name) / "other"
        other.mkdir()
        second = runtime.start("fresh", project=other)
        self.assertNotEqual(second["sessionId"], result["sessionId"])
        self.completed(runtime)
        self.assertEqual(transport.calls[-1]["payload"]["messages"], [{"role": "user", "content": "fresh"}])

    def test_project_binding_is_validated_and_scoped(self):
        runtime, _ = self.make(model="m", base_url=BASE)
        with self.assertRaisesRegex(ProviderRuntimeError, "unavailable"):
            runtime.start("hi", project=Path(self.temp.name) / "missing")
        with patch.object(Path, "home", return_value=Path(self.temp.name).resolve()):
            with self.assertRaisesRegex(ProviderRuntimeError, "non-home"):
                runtime.start("hi", project=self.temp.name)
        other = Path(self.temp.name) / "other"
        other.mkdir()
        runtime.start("one", project=self.project)
        self.completed(runtime)
        with self.assertRaisesRegex(ProviderRuntimeError, "another project"):
            runtime.start("two", project=other)
        runtime.stop()
        runtime.start("two", project=other)
        self.completed(runtime)
        self.assertEqual(runtime.status()["project"], str(other.resolve()))

    def test_text_only_rejects_images_and_tools_everywhere(self):
        runtime, transport = self.make(model="m", base_url=BASE)
        image = {"mimeType": "image/png", "data": "AAAA"}
        with self.assertRaisesRegex(ProviderRuntimeError, "text-only"):
            runtime.start("look", project=self.project, images=[image])
        with self.assertRaisesRegex(ProviderRuntimeError, "text-only"):
            runtime.start("look", project=self.project, tools=[{"name": "browser"}])
        runtime.start("hi", project=self.project)
        self.completed(runtime)
        with self.assertRaisesRegex(ProviderRuntimeError, "text-only"):
            runtime.send("look", images=[image])
        with self.assertRaisesRegex(ProviderRuntimeError, "text-only"):
            runtime.send("look", tools=[{"name": "browser"}])
        with self.assertRaisesRegex(ProviderRuntimeError, "non-empty"):
            runtime.send("   ")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(runtime.status()["state"], "idle")
        # A tool-call answer from the endpoint is refused, never executed.
        runtime, transport = self.make(model="m", base_url=BASE, transport=FakeTransport([
            {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]}}]},
        ]))
        runtime.start("do something", project=self.project)
        wait_for(lambda: find_event(runtime, "runtime.error") is not None)
        self.assertIn("text-only", find_event(runtime, "runtime.error")["data"]["message"])
        self.assertEqual(runtime.status()["state"], "error")
        for call in transport.calls:
            self.assertNotIn("tools", call["payload"])

    def test_key_is_redacted_from_events_and_errors(self):
        runtime, _ = self.make(model="m", base_url=BASE, api_key="fixture-secret", transport=FakeTransport([
            RuntimeError("Bearer fixture-secret exploded"),
        ]))
        runtime.start("hi", project=self.project)
        wait_for(lambda: find_event(runtime, "runtime.error") is not None)
        self.assertEqual(find_event(runtime, "runtime.error")["data"]["message"], "The OpenAI-compatible endpoint request failed")
        self.assertNotIn("fixture-secret", repr(runtime.events()))
        # Trusted transport messages are still scrubbed as defense in depth.
        runtime, _ = self.make(model="m", base_url=BASE, api_key="fixture-secret", transport=FakeTransport([
            TransportError("The endpoint returned HTTP 500 fixture-secret"),
        ]))
        runtime.start("hi", project=self.project)
        wait_for(lambda: find_event(runtime, "runtime.error") is not None)
        self.assertEqual(find_event(runtime, "runtime.error")["data"]["message"], "The endpoint returned HTTP 500 [redacted]")
        runtime._event("provider.event", nested={"message": "fixture-secret must not leak"})
        self.assertNotIn("fixture-secret", repr(runtime.events()))
        self.assertNotIn("fixture-secret", json.dumps(runtime.status()))

    def test_history_is_bounded_by_the_context_hint_estimate(self):
        runtime, transport = self.make(model="m", base_url=BASE, context_hint=1024, transport=FakeTransport([
            {"choices": [{"message": {"content": "r" * 3000}}]},
        ] * 4))
        for index in range(4):
            if index == 0:
                runtime.start("turn 0", project=self.project)
            else:
                runtime.send(f"turn {index}")
            wait_for(lambda count=index: count_events(runtime, "message.completed") == count + 1)
        last = transport.calls[-1]["payload"]["messages"]
        self.assertEqual([message["role"] for message in last], ["user", "assistant", "user"])
        self.assertEqual(last[0]["content"], "turn 2")
        self.assertLessEqual(len(last), 3)
        with runtime._lock:
            trimmed = runtime._bounded([{"role": "user" if index % 2 == 0 else "assistant", "content": "x"} for index in range(MAX_HISTORY_MESSAGES * 2 + 6)])
        self.assertLessEqual(len(trimmed), MAX_HISTORY_MESSAGES)
        self.assertEqual(trimmed[0]["role"], "user")
        # Assistant text is capped before it is stored or evented.
        runtime, _ = self.make(model="m", base_url=BASE, transport=FakeTransport([
            {"choices": [{"message": {"content": "y" * (MAX_ASSISTANT_CHARS + 500)}}]},
        ]))
        runtime.start("big", project=self.project)
        completed = self.completed(runtime)
        self.assertEqual(len(completed["data"]["text"]), MAX_ASSISTANT_CHARS)

    def test_configuration_is_validated_and_required(self):
        with self.assertRaisesRegex(ProviderRuntimeError, "loopback"):
            OpenAICompatibleRuntime(model="m", base_url="http://api.example.com/v1")
        for kwargs in ({"model": "x" * 201}, {"temperature": 9}, {"max_output_tokens": 0}, {"timeout": 0}, {"api_key": "bad\nkey"}):
            with self.assertRaisesRegex(ProviderRuntimeError, ".", msg=repr(kwargs)):
                OpenAICompatibleRuntime(base_url=BASE, **kwargs)
        with self.assertRaisesRegex(ProviderRuntimeError, "does not resume"):
            OpenAICompatibleRuntime(session_id="old")
        runtime, _ = self.make()
        with self.assertRaisesRegex(ProviderRuntimeError, "base URL"):
            runtime.start("hi", project=self.project)
        runtime, _ = self.make(base_url=BASE)
        with self.assertRaisesRegex(ProviderRuntimeError, "model"):
            runtime.start("hi", project=self.project)
        runtime, _ = self.make(model="m", base_url=BASE)
        with self.assertRaisesRegex(ProviderRuntimeError, "not started"):
            runtime.send("hi")
        runtime, transport = self.make(model="m", base_url=BASE)
        runtime.start("hi", project=self.project)
        self.completed(runtime)
        self.assertNotIn("temperature", transport.calls[0]["payload"])
        self.assertEqual(transport.calls[0]["payload"]["max_tokens"], 4096)
        self.assertEqual(transport.calls[0]["timeout"], 120.0)

    def test_model_override_and_concurrency_guards(self):
        runtime, transport = self.make(model="m", base_url=BASE)
        transport.holding = True
        runtime.start("hi", project=self.project)
        with self.assertRaisesRegex(ProviderRuntimeError, "current turn"):
            runtime.send("more")
        with self.assertRaisesRegex(ProviderRuntimeError, "current turn"):
            runtime.start("more", project=self.project)
        transport.hold.set()
        self.completed(runtime)
        with self.assertRaisesRegex(ProviderRuntimeError, "Model ID"):
            runtime.start("again", project=self.project, model="bad model")
        runtime.start("again", project=self.project, model="other-model")
        self.completed(runtime)
        self.assertEqual(transport.calls[-1]["payload"]["model"], "other-model")

    def test_real_transport_refuses_cross_host_redirects(self):
        body = json.dumps(REPLY).encode()
        redirected = Opener([Response(body, "https://elsewhere.example/v1/chat/completions")])
        runtime = OpenAICompatibleRuntime(model="m", base_url=BASE, api_key="fixture-secret", opener=redirected)
        runtime.start("hi", project=self.project)
        wait_for(lambda: find_event(runtime, "runtime.error") is not None)
        self.assertIn("redirect", find_event(runtime, "runtime.error")["data"]["message"])
        self.assertEqual(redirected.requests[0].get_header("Authorization"), "Bearer fixture-secret")
        self.assertNotIn("fixture-secret", repr(runtime.events()))
        honest = Opener([Response(body, BASE + "/chat/completions")])
        runtime = OpenAICompatibleRuntime(model="m", base_url=BASE, opener=honest)
        runtime.start("hi", project=self.project)
        self.completed(runtime)
        self.assertEqual(find_event(runtime, "message.completed")["data"]["text"], "fixture reply")

    def test_from_connection_binds_verified_configuration(self):
        conn = OpenAICompatibleConnection(opener=Opener([Response(b'{"data":[{"id":"fixture-model"}]}', BASE + "/models")]))
        conn.connect(base_url=BASE, model="fixture-model", api_key="fixture-secret")
        transport = FakeTransport()
        runtime = OpenAICompatibleRuntime.from_connection(conn, post=transport)
        runtime.start("hi", project=self.project)
        self.completed(runtime)
        call = transport.calls[0]
        self.assertEqual(call["url"], BASE + "/chat/completions")
        self.assertEqual(call["payload"]["model"], "fixture-model")
        self.assertEqual(call["headers"]["Authorization"], "Bearer fixture-secret")
        with self.assertRaisesRegex(ProviderRuntimeError, "Configure"):
            OpenAICompatibleRuntime.from_connection(OpenAICompatibleConnection(opener=Opener()))


if __name__ == "__main__":
    unittest.main()
