from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid

from codex_bridge import BridgeError
from provider_hub import ProviderHub
from provider_runtime import ProviderRuntime, ProviderRuntimeError
from openai_compatible_runtime import OpenAICompatibleRuntime


class FakeBudget:
    def __init__(self):
        self.values = {}

    def set_policy(self, team, limit, enforced):
        self.values[team] = {"limitTokens": int(limit), "enforced": bool(enforced), "usedTokens": 0}
        return self.status(team)

    def status(self, team):
        value = self.values.get(team, {"limitTokens": 200000, "enforced": True, "usedTokens": 0})
        blocked = value["enforced"] and value["usedTokens"] >= value["limitTokens"]
        return {**value, "remainingTokens": max(0, value["limitTokens"] - value["usedTokens"]), "usedPercent": 0, "remainingPercent": 100, "blocked": blocked, "reason": "blocked" if blocked else None, "enforcement": "fixture", "coverage": "fixture"}

    def authorize(self, team):
        value = self.status(team)
        if value["blocked"]:
            raise BridgeError(value["reason"])
        return value

    def record_usage(self, team, thread_id, total):
        value = self.values.setdefault(team, {"limitTokens": 200000, "enforced": True, "usedTokens": 0})
        value["usedTokens"] = total
        return self.status(team), False


class FakeCodex:
    def __init__(self):
        self.calls = []
        self._budget = FakeBudget()
        self._status = {"team": "", "state": "offline", "connected": False, "project": None, "threadId": None, "mode": "plan", "accessMode": "workspace", "planReady": False, "pendingApprovals": [], "children": [], "budget": self._budget.status("x")}

    def start(self, *args, **kwargs):
        self.calls.append(("start", args, kwargs))
        self._status = {**self._status, "team": args[0], "state": "running", "connected": True, "project": str(args[1]), "threadId": "codex-thread", "turnId": "codex-turn", "mode": "plan", "accessMode": "workspace"}
        return dict(self._status)

    def status(self, team):
        return {**self._status, "team": team, "budget": self._budget.status(team)}

    def events(self, team, after=0):
        self.calls.append(("events", (team, after), {}))
        return {"team": team, "afterSeq": after, "nextSeq": after, "truncated": False, "events": []}

    def set_budget(self, team, limit, enforced=True):
        return self._budget.set_policy(team, limit, enforced)

    def __getattr__(self, name):
        if name == "shutdown_all":
            return lambda: None
        def forwarded(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {"accepted": True, "forwarded": name}
        return forwarded


class FakeClaude(ProviderRuntime):
    provider = "claude"

    def __init__(self, *, session_id=None, access="workspace", recover_pending=False, **_):
        super().__init__()
        self.session_id = session_id or "claude-session"
        self.access = access
        self.models = [{"value": "sonnet", "resolvedModel": "claude-sonnet-fixture", "displayName": "Sonnet", "description": "fixture"}]
        self.turn = 0
        self.pending = {}
        self.project = None
        self.initialize_access = []
        self.recover_pending = bool(recover_pending and session_id)
        self.recovered_emitted = False

    def initialize(self, *, project, model=None):
        self.initialize_access.append(self.access)
        self.project = str(project)
        self.model = model or self.model
        self._state = "idle"
        self._event("session.ready", sessionId=self.session_id)
        self._event("runtime.models", models=self.models)
        if self.recover_pending and not self.recovered_emitted:
            self.recovered_emitted = True
            self.pending["question-1"] = {"turnId": "recovered-turn", "recovered": True}
            self._event(
                "approval.requested", requestId="question-1", tool="Bash",
                toolInput={"command":"echo recovered"}, recovered=True,
                sessionId=self.session_id, turnId="recovered-turn", itemId=None,
            )
        return {"accepted": True, "sessionId": self.session_id, "models": list(self.models)}

    def start(self, prompt, *, project, model=None, images=None, **_):
        self.initialize(project=project, model=model)
        self._event("runtime.started", sessionId=self.session_id, project=str(project))
        return self.send(prompt, images=images)

    def send(self, prompt, *, images=None, **_):
        self.turn += 1
        turn_id, item_id = f"turn-{self.turn}", f"item-{self.turn}"
        self._state = "running"
        self._event("message.user", text=prompt, sessionId=self.session_id, turnId=turn_id, itemId=item_id, attachments=images or [])
        if prompt == "question":
            request_id = "question-1"
            self.pending[request_id] = True
            self._event("question.requested", requestId=request_id, tool="AskUserQuestion", toolInput={"questions":[{"header":"Choice","question":"Choose?","options":[{"label":"A","description":"first"}]}]}, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
        elif prompt == "approval":
            request_id = "approval-1"
            self.pending[request_id] = True
            self._event("approval.requested", requestId=request_id, tool="Write", toolInput={"file_path":"/tmp/example.txt","content":"TOP SECRET"}, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
        elif prompt == "failure":
            self._event("runtime.error", message="failed result", sessionId=self.session_id, turnId=turn_id, itemId=item_id)
            self._state = "error"
        elif prompt == "stream-failure":
            self._event("runtime.error", message="stream closed", sessionId=self.session_id)
            self._state = "error"
        else:
            self._event("message.delta", text="reply ", sessionId=self.session_id, turnId=turn_id, itemId=item_id)
            self._event("message.completed", text="reply " + prompt, usage={"input_tokens":2,"output_tokens":3}, sessionId=self.session_id, turnId=turn_id, itemId=item_id)
            self._state = "idle"
        return {"accepted": True, "sessionId": self.session_id, "turnId": turn_id, "itemId": item_id}

    def respond(self, request_id, response):
        if request_id not in self.pending:
            raise ProviderRuntimeError("stale")
        metadata = self.pending.pop(request_id)
        metadata = metadata if isinstance(metadata, dict) else {}
        self._event("request.resolved", requestId=request_id, allowed=response.get("allow"), sessionId=self.session_id, **metadata)
        self._event("message.completed", text="answered", usage={"input_tokens":1,"output_tokens":1}, sessionId=self.session_id, turnId=f"turn-{self.turn}", itemId=f"item-{self.turn}")
        self._state = "idle"
        return {"accepted": True, "requestId": request_id}

    def set_access(self, access):
        self.access = access
        self._event("runtime.access", access=access, sessionId=self.session_id)
        return {"accepted": True, "access": access}

    def stop(self):
        self._state = "offline"
        self._event("runtime.stopped", sessionId=self.session_id)
        return {"accepted": True, "sessionId": self.session_id}

    def stream_error(self):
        self._state = "error"
        self._event("runtime.error", message="stream closed", sessionId=self.session_id)

    def status(self):
        value = super().status()
        value.update({"sessionId": self.session_id, "models": list(self.models), "access": self.access})
        return value


class Factory:
    def __init__(self, *, recover_pending=False):
        self.runtimes = []
        self.recover_pending = recover_pending

    def __call__(self, provider, **kwargs):
        self.assert_provider = provider
        runtime = FakeClaude(recover_pending=self.recover_pending, **kwargs)
        runtime.provider = provider
        self.runtimes.append(runtime)
        return runtime


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError("timed out")


class ProviderHubTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.codex = FakeCodex()
        self.factory = Factory()
        self.hub = ProviderHub(self.root / "runtime", codex=self.codex, runtime_factory=self.factory, max_events=20, poll_interval=.01)

    def tearDown(self):
        self.hub.shutdown_all()
        self.temp.cleanup()

    def test_codex_contract_is_forwarded_and_default(self):
        self.assertFalse(self.hub.status("codex-team")["providerBound"])
        result = self.hub.start("codex-team", self.project, "hello", "gpt-5.6-luna")
        self.assertEqual(result["provider"], "codex")
        self.assertTrue(self.hub.status("codex-team")["providerBound"])
        self.assertEqual(self.codex.calls[0][0], "start")
        self.assertEqual(self.hub.send("codex-team", "again")["forwarded"], "send")
        self.hub.events("codex-team", 4)
        self.assertEqual(self.codex.calls[-1][0], "events")

    def test_custom_text_endpoint_reports_usage_and_no_tool_capabilities(self):
        def factory(provider, **kwargs):
            self.assertEqual(provider, 'openai-compatible')
            kwargs.update(model='fixture-model',model_catalog=['fixture-model'],base_url='https://fixture.example/v1',
                post=lambda *_: {'choices':[{'message':{'content':'ready'}}],
                                 'usage':{'prompt_tokens':3,'completion_tokens':2,'total_tokens':5}})
            return OpenAICompatibleRuntime(**kwargs)
        hub=ProviderHub(self.root/'custom-runtime',codex=FakeCodex(),runtime_factory=factory,max_events=20,poll_interval=.01)
        try:
            with self.assertRaisesRegex(BridgeError,'text-only'):
                hub.start('custom-full',self.project,'hello','fixture-model',provider='openai-compatible',work_mode='full')
            with self.assertRaisesRegex(BridgeError,'text-only'):
                hub.start('custom-image',self.project,'hello','fixture-model',provider='openai-compatible',work_mode='auto',attachments=[{'id':'image'}])
            status=hub.start('custom-chat',self.project,'hello','fixture-model',provider='openai-compatible',work_mode='auto')
            self.assertEqual(status['provider'],'openai-compatible')
            done=wait_for(lambda: hub.status('custom-chat') if hub.status('custom-chat')['state']=='idle' else None)
            self.assertEqual(done['usageSummary']['reportedTokens'],5)
            self.assertEqual(done['capabilities']['images'],False)
            self.assertEqual(done['capabilities']['workers'],False)
            self.assertEqual(done['capabilities']['nativePermissions'],False)
            self.assertEqual(next(row for row in hub.events('custom-chat')['events'] if row['type']=='message.completed')['data']['text'],'ready')
        finally:
            hub.shutdown_all()

    def test_claude_start_captures_events_without_ui_poll_and_persists_restart(self):
        status = self.hub.start("claude-team", self.project, "hello", "sonnet", provider="claude")
        self.assertEqual(status["provider"], "claude")
        self.assertTrue(status["providerBound"])
        self.assertEqual(status["threadId"], "claude-session")
        events = wait_for(lambda: self.hub.events("claude-team")["events"] if any(row["type"] == "message.completed" for row in self.hub.events("claude-team")["events"]) else None)
        completed = next(row for row in events if row["type"] == "message.completed")
        self.assertEqual(completed["threadId"], "claude-session")
        self.assertEqual(completed["turnId"], "turn-1")
        self.assertEqual(completed["itemId"], "item-1")
        last_seq = events[-1]["seq"]
        self.hub.shutdown_all()
        restarted = ProviderHub(self.root / "runtime", codex=FakeCodex(), runtime_factory=Factory(), max_events=20, poll_interval=.01)
        try:
            restored = restarted.events("claude-team")
            self.assertGreaterEqual(restored["events"][-1]["seq"], last_seq)
            self.assertGreaterEqual(restored["nextSeq"], last_seq)
            self.assertTrue(any(row["type"] == "message.completed" for row in restored["events"]))
            self.assertEqual(restarted.status("claude-team")["provider"], "claude")
            self.assertFalse(restarted.status("claude-team")["connected"])
        finally:
            restarted.shutdown_all()

    def test_kimi_and_zai_keep_provider_model_and_event_identity(self):
        for provider in ("kimi", "zai"):
            team = f"{provider}-team"
            status = self.hub.start(team, self.project, "hello", "sonnet", provider=provider)
            self.assertEqual(status["provider"], provider)
            self.assertEqual(self.factory.assert_provider, provider)
            event = wait_for(lambda: next((row for row in self.hub.events(team)["events"] if row["type"] == "message.completed"), None))
            self.assertEqual(event["threadId"], "claude-session")
            self.assertEqual(event["turnId"], "turn-1")
            self.assertEqual(self.hub._read_binding(team)["provider"], provider)
            self.assertEqual(self.factory.runtimes[-1].model, "sonnet")

    def test_provider_and_project_bindings_cannot_switch(self):
        self.hub.start("fixed-team", self.project, "hello", "sonnet", provider="claude")
        with self.assertRaisesRegex(BridgeError, "already bound to claude"):
            self.hub.start("fixed-team", self.project, "hello", "gpt-5.6-luna", provider="codex")
        other = self.root / "other"
        other.mkdir()
        with self.assertRaisesRegex(BridgeError, "different project"):
            self.hub.start("fixed-team", other, "hello", "sonnet", provider="claude")

    def test_plan_execution_full_access_and_question_response(self):
        self.hub.start("plan-team", self.project, "plan", "sonnet", provider="claude")
        wait_for(lambda: self.hub.status("plan-team")["planReady"])
        execution = self.hub.begin_execution("plan-team")
        self.assertEqual(execution["mode"], "execute")
        wait_for(lambda: self.hub.status("plan-team")["state"] == "idle")
        status = self.hub.set_access("plan-team", "full")
        self.assertEqual(status["accessMode"], "full")
        runtime = self.factory.runtimes[-1]
        self.assertEqual(runtime.initialize_access[-1], "full")
        status = self.hub.set_access("plan-team", "workspace")
        self.assertEqual(status["accessMode"], "workspace")
        self.assertEqual(runtime.initialize_access[-1], "workspace")
        self.hub.send("plan-team", "question")
        pending = wait_for(lambda: self.hub.status("plan-team")["pendingApprovals"])
        self.assertEqual(pending[0]["kind"], "questions")
        self.assertEqual(pending[0]["questions"][0]["question"], "Choose?")
        self.hub.respond("plan-team", pending[0]["requestId"], {"answers":{"question-0":{"answers":["A"]}}})
        wait_for(lambda: not self.hub.status("plan-team")["pendingApprovals"])

    def test_explicit_zcode_full_access_keeps_pending_tool_separate(self):
        self.hub.start("full-zai", self.project, "approval", "sonnet", provider="zai", work_mode="auto")
        pending=wait_for(lambda: self.hub.status("full-zai")["pendingApprovals"])
        self.hub.set_access("full-zai", "full")
        self.assertEqual(self.hub._read_binding("full-zai")["accessMode"], "full")
        self.assertTrue(self.hub.status("full-zai")["pendingApprovals"])
        self.hub.approve("full-zai", pending[0]["requestId"], "approve")
        wait_for(lambda: not self.hub.status("full-zai")["pendingApprovals"])

    def test_concurrent_drains_map_one_native_event_once(self):
        self.hub.start("race-team", self.project, "hello", "sonnet", provider="claude")
        session = self.hub._sessions["race-team"]
        session.stop_event.set()
        if session.watcher:
            session.watcher.join(1)
        before = self.hub.events("race-team")["nextSeq"]
        runtime = self.factory.runtimes[-1]
        runtime._event("provider.fixture", marker="once", sessionId=runtime.session_id)
        threads = [threading.Thread(target=self.hub._drain, args=(session,)) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        rows = [row for row in self.hub.events("race-team", before)["events"] if row["type"] == "provider.fixture"]
        self.assertEqual(len(rows), 1)

    def test_event_and_archive_failures_are_nonfatal_and_retry_without_duplicates(self):
        original_save = self.hub._event_store.save
        original_record = self.hub._transcripts.record
        save_calls = 0
        archive_calls = 0

        def flaky_save(*args):
            nonlocal save_calls
            save_calls += 1
            if save_calls == 1:
                raise OSError("disk busy")
            return original_save(*args)

        def flaky_record(*args):
            nonlocal archive_calls
            archive_calls += 1
            if archive_calls == 1:
                raise sqlite3.OperationalError("archive busy")
            return original_record(*args)

        self.hub._event_store.save = flaky_save
        self.hub._transcripts.record = flaky_record
        result = self.hub.start("durable-team", self.project, "hello", "sonnet", provider="claude")
        self.assertEqual(result["provider"], "claude")
        session = self.hub._sessions["durable-team"]
        self.assertGreater(session.runtime_cursor, 0)
        self.hub.status("durable-team")
        users = [row for row in self.hub.events("durable-team")["events"] if row["type"] == "message.user"]
        self.assertEqual(len(users), 1)
        self.assertIsNone(self.hub.status("durable-team")["historyWarning"])

    def test_cumulative_native_usage_is_not_added_twice(self):
        self.hub.start("native-usage",self.project,"hello","sonnet",provider="claude")
        session=self.hub._sessions["native-usage"]
        for total in (120,120,150):
            self.hub._record_runtime_event(session,{"type":"message.completed","data":{"nativeUsage":{"totalTokens":total,"cacheReadTokens":100},"turnId":"native-turn"}})
        self.assertEqual(session.reported_tokens,150)
        self.assertEqual(self.hub.status("native-usage")["usageSummary"]["reportedTokens"],150)

    def test_usage_failure_is_nonfatal_and_retried(self):
        original = self.codex._budget.record_usage
        calls = 0
        def flaky(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("budget busy")
            return original(*args)
        self.codex._budget.record_usage = flaky
        result = self.hub.start("usage-team", self.project, "hello", "sonnet", provider="claude")
        self.assertEqual(result["provider"], "claude")
        session = self.hub._sessions["usage-team"]
        self.hub._drain(session)
        self.assertFalse(session.usage_pending)
        self.assertTrue(session.watcher and session.watcher.is_alive())
        completed = [row for row in self.hub.events("usage-team")["events"] if row["type"] == "message.completed"]
        self.assertEqual(len(completed), 1)

    def test_approval_projection_hides_payload_and_errors_clear_authority(self):
        self.hub.start("approval-team", self.project, "hello", "sonnet", provider="claude", work_mode="auto")
        self.hub.send("approval-team", "approval")
        pending = wait_for(lambda: self.hub.status("approval-team")["pendingApprovals"])
        self.assertNotIn("toolInput", pending[0])
        self.assertNotIn("TOP SECRET", str(pending[0]))
        runtime = self.factory.runtimes[-1]
        runtime.stream_error()
        wait_for(lambda: self.hub.status("approval-team")["state"] == "error")
        self.assertEqual(self.hub.status("approval-team")["pendingApprovals"], [])
        self.assertEqual(self.hub._sessions["approval-team"].active_turns, set())

    def test_failed_result_clears_its_turn(self):
        self.hub.start("failure-team", self.project, "hello", "sonnet", provider="claude", work_mode="auto")
        self.hub.send("failure-team", "failure")
        wait_for(lambda: self.hub.status("failure-team")["state"] == "error")
        self.assertEqual(self.hub._sessions["failure-team"].active_turns, set())

    def test_restart_recovered_permission_is_session_bound_and_resolvable(self):
        self.hub.start("recover-team", self.project, "question", "sonnet", provider="claude", work_mode="auto")
        wait_for(lambda: self.hub.status("recover-team")["pendingApprovals"])
        self.hub.shutdown_all()
        recovered = ProviderHub(
            self.root / "runtime", codex=FakeCodex(), runtime_factory=Factory(recover_pending=True),
            max_events=20, poll_interval=.01,
        )
        try:
            with self.assertRaisesRegex(BridgeError, "pending native request"):
                recovered.send("recover-team", "must wait")
            pending = recovered.status("recover-team")["pendingApprovals"]
            self.assertEqual(pending[0]["turnId"], "recovered-turn")
            recovered.approve("recover-team", pending[0]["requestId"], "reject")
            self.assertEqual(recovered.status("recover-team")["pendingApprovals"], [])
            self.assertNotIn("recovered-turn", recovered._sessions["recover-team"].active_turns)
        finally:
            recovered.shutdown_all()

    def test_model_must_come_from_initialize_and_unverified_provider_is_not_routed(self):
        with self.assertRaisesRegex(BridgeError, "initialized provider model catalog"):
            self.hub.start("bad-model", self.project, "hello", "invented", provider="claude")
        with self.assertRaisesRegex(BridgeError, "verified Company HQ runtime"):
            self.hub.start("acp-team", self.project, "hello", "model", provider="cursor")

    def test_claude_unsupported_worker_and_tool_capabilities_are_explicit(self):
        self.hub.start("cap-team", self.project, "hello", "sonnet", provider="claude")
        self.assertFalse(self.hub.tools("cap-team")["available"])
        self.assertFalse(self.hub.workers("cap-team")["authoritative"])
        with self.assertRaisesRegex(BridgeError, "not supported"):
            self.hub.send_worker("cap-team", str(uuid.uuid4()), "hello")


if __name__ == "__main__":
    unittest.main()
