import base64
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

from acp_runtime import AcpRuntime
from claude_runtime import ClaudeCodeRuntime, claude_binary, probe
from provider_runtime import OllamaRuntime, ProviderRuntimeError, UnavailableRuntime, create_runtime


CLAUDE_FIXTURE = r'''#!/usr/bin/env python3
import json, sys

SESSION = "fixture-session"
waiting = {}

def send(value):
    print(json.dumps(value, separators=(",", ":")), flush=True)

def completed(text):
    send({"type":"assistant","session_id":SESSION,"message":{"id":"assistant-item","content":[{"type":"text","text":text}]}})
    send({"type":"result","subtype":"success","session_id":SESSION,"result":"done: "+text,"duration_ms":2,"num_turns":1,"usage":{"input_tokens":3,"output_tokens":2}})

send({"type":"system","subtype":"init","session_id":SESSION,"tools":["Read","AskUserQuestion"],"capabilities":["interrupt_receipt_v1"]})
for line in sys.stdin:
    item = json.loads(line)
    if item.get("type") == "control_request":
        request = item.get("request", {})
        response = {}
        if request.get("subtype") == "initialize":
            response = {"models":[{"value":"sonnet","resolvedModel":"claude-sonnet-fixture","displayName":"Sonnet Fixture","description":"fixture","supportsEffort":True,"supportedEffortLevels":["low","high"]}],"pending_permission_requests":[]}
        elif request.get("subtype") == "set_permission_mode":
            response = {"mode": request.get("mode")}
        elif request.get("subtype") == "interrupt":
            response = {"still_queued":[],"cancelled":[]}
        send({"type":"control_response","response":{"subtype":"success","request_id":item["request_id"],"response":response}})
        continue
    if item.get("type") == "control_response":
        response = item.get("response", {})
        request_id = response.get("request_id")
        original = waiting.pop(request_id, None)
        if original:
            decision = response.get("response", {})
            completed("decision:"+str(decision.get("behavior"))+":"+json.dumps(decision.get("updatedInput", {}), sort_keys=True))
        continue
    if item.get("type") != "user":
        continue
    blocks = item["message"]["content"]
    text = next(block["text"] for block in blocks if block.get("type") == "text")
    images = [block for block in blocks if block.get("type") == "image"]
    if text in {"approve", "question"}:
        request_id = "permission-" + text
        tool = "AskUserQuestion" if text == "question" else "Bash"
        tool_input = {"questions":[{"question":"Choose?","options":[{"label":"A"},{"label":"B"}]}]} if text == "question" else {"command":"echo fixture"}
        waiting[request_id] = text
        send({"type":"control_request","request_id":request_id,"request":{"subtype":"can_use_tool","tool_name":tool,"input":tool_input,"tool_use_id":"tool-1","decision_reason":"fixture approval"}})
    else:
        completed(text + ":images=" + str(len(images)))
'''


ACP_FIXTURE = r'''#!/usr/bin/env python3
import json, sys
for line in sys.stdin:
    item=json.loads(line)
    method=item.get("method")
    ident=item.get("id")
    if method == "initialize": result={"protocolVersion":1}
    elif method == "session/new": result={"sessionId":"acp-fixture"}
    elif method == "session/prompt":
        print(json.dumps({"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk","content":{"text":"fixture reply"}}}}), flush=True)
        result={}
    elif method == "session/cancel": result={}
    else: result={}
    if ident is not None: print(json.dumps({"jsonrpc":"2.0","id":ident,"result":result}), flush=True)
'''

CLAUDE_RECOVERED_FIXTURE = r'''#!/usr/bin/env python3
import json, sys
SESSION = "resumed-session"
def send(value): print(json.dumps(value, separators=(",", ":")), flush=True)
send({"type":"system","subtype":"init","session_id":SESSION,"tools":["Bash"]})
for line in sys.stdin:
    item=json.loads(line)
    if item.get("type") == "control_request":
        request=item.get("request", {})
        pending=[]
        if request.get("subtype") == "initialize":
            pending=[{"request_id":"recovered-1","request":{"subtype":"can_use_tool","tool_name":"Bash","input":{"command":"echo recovered"},"tool_use_id":"tool-recovered"}}]
            response={"models":[{"value":"sonnet","resolvedModel":"claude-sonnet-fixture","displayName":"Sonnet"}],"pending_permission_requests":pending}
        else: response={}
        send({"type":"control_response","response":{"subtype":"success","request_id":item["request_id"],"response":response}})
'''


def wait_for(runtime, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = runtime.events()["events"]
        if predicate(events):
            return events
        time.sleep(.01)
    raise AssertionError("timed out waiting for runtime event")


class ProviderRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, name, content):
        path = Path(self.temp.name) / name
        path.write_text(content)
        path.chmod(0o755)
        return str(path)

    def test_ollama_is_async_and_preserves_chat_history(self):
        calls = []

        def post(url, payload):
            calls.append((url, payload))
            return {"message": {"content": "local result " + str(len(calls))}, "usage": {"eval_count": 2}}

        runtime = OllamaRuntime(model="qwen-local", post=post)
        first = runtime.start("Hello", project=self.project)
        self.assertTrue(first["accepted"])
        wait_for(runtime, lambda rows: sum(row["type"] == "message.completed" for row in rows) == 1)
        runtime.send("Again")
        events = wait_for(runtime, lambda rows: sum(row["type"] == "message.completed" for row in rows) == 2)
        self.assertEqual(calls[0][0], "http://127.0.0.1:11434/api/chat")
        self.assertTrue(calls[0][1]["stream"])
        self.assertEqual([row["role"] for row in calls[1][1]["messages"]], ["user", "assistant", "user"])
        completed = [row for row in events if row["type"] == "message.completed"]
        self.assertTrue(all(row["data"].get("turnId") and row["data"].get("itemId") for row in completed))
        self.assertEqual(runtime.status()["turns"], 2)

    def test_ollama_stop_cancels_late_completion(self):
        release = threading.Event()

        def post(*_):
            release.wait(2)
            return {"response": "too late"}

        runtime = OllamaRuntime(model="local", post=post)
        runtime.start("wait", project=self.project)
        runtime.stop()
        release.set()
        time.sleep(.05)
        self.assertFalse(any(row["type"] == "message.completed" for row in runtime.events()["events"]))
        self.assertEqual(runtime.status()["state"], "offline")

    def test_event_cursors_are_monotonic_and_detect_truncation(self):
        runtime = OllamaRuntime(model="fixture", post=lambda *_: {"response": "ok"})
        runtime.max_events = 2
        runtime.start("first", project=self.project)
        wait_for(runtime, lambda rows: any(row["type"] == "message.completed" for row in rows))
        page = runtime.events(0)
        self.assertTrue(page["truncated"])
        self.assertEqual([event["seq"] for event in page["events"]], sorted(event["seq"] for event in page["events"]))

    def test_claude_wire_initialize_models_multiturn_images_and_ids(self):
        launches = []

        def factory(args, **kwargs):
            launches.append(list(args))
            return subprocess.Popen(args, **kwargs)

        image = self.project / "sample.png"
        image.write_bytes(b"fixture-png")
        runtime = ClaudeCodeRuntime(
            binary=self.fixture("claude-fixture", CLAUDE_FIXTURE),
            permission_mode="plan", process_factory=factory,
        )
        initialized = runtime.initialize(project=self.project, model="sonnet")
        self.assertEqual(initialized["models"][0]["value"], "sonnet")
        self.assertFalse(any(row["type"] == "message.user" for row in runtime.events()["events"]))
        accepted = runtime.start("first", project=self.project, model="sonnet", images=[{"id":"img", "name":"sample.png", "mimeType":"image/png", "path":str(image)}])
        self.assertTrue(accepted["turnId"])
        events = wait_for(runtime, lambda rows: any(row["type"] == "message.completed" for row in rows))
        self.assertEqual(runtime.session_id, "fixture-session")
        self.assertEqual(runtime.status()["models"][0]["value"], "sonnet")
        completed = next(row for row in events if row["type"] == "message.completed")
        self.assertEqual(completed["data"]["turnId"], accepted["turnId"])
        self.assertEqual(completed["data"]["itemId"], "assistant-item")
        self.assertIn("images=1", completed["data"]["text"])
        self.assertIn("--permission-prompt-tool", launches[0])
        runtime.send("second")
        wait_for(runtime, lambda rows: sum(row["type"] == "message.completed" for row in rows) == 2)
        runtime.stop()

    def test_claude_permission_and_question_control_responses_end_to_end(self):
        runtime = ClaudeCodeRuntime(binary=self.fixture("claude-control", CLAUDE_FIXTURE))
        runtime.start("approve", project=self.project)
        events = wait_for(runtime, lambda rows: any(row["type"] == "approval.requested" for row in rows))
        approval = next(row for row in events if row["type"] == "approval.requested")
        self.assertEqual(approval["data"]["tool"], "Bash")
        runtime.respond(approval["data"]["requestId"], {"decision":"allow"})
        wait_for(runtime, lambda rows: any(row["type"] == "message.completed" for row in rows))
        runtime.send("question")
        events = wait_for(runtime, lambda rows: any(row["type"] == "question.requested" for row in rows))
        question = next(row for row in events if row["type"] == "question.requested")
        runtime.respond(question["data"]["requestId"], {"allow":True, "answers":{"Choose?":"A"}})
        events = wait_for(runtime, lambda rows: sum(row["type"] == "message.completed" for row in rows) == 2)
        self.assertTrue(any("Choose?" in row["data"].get("text", "") for row in events if row["type"] == "message.completed"))
        with self.assertRaisesRegex(ProviderRuntimeError, "stale or unknown"):
            runtime.respond(question["data"]["requestId"], {"allow":False})
        runtime.stop()

    def test_claude_resume_and_access_are_explicit(self):
        launches = []

        def factory(args, **kwargs):
            launches.append(list(args))
            return subprocess.Popen(args, **kwargs)

        runtime = ClaudeCodeRuntime(binary=self.fixture("claude-resume", CLAUDE_FIXTURE), process_factory=factory)
        runtime.start("first", project=self.project)
        wait_for(runtime, lambda rows: any(row["type"] == "message.completed" for row in rows))
        runtime.stop()
        runtime.start("resumed", project=self.project)
        self.assertIn("--resume", launches[1])
        self.assertIn("fixture-session", launches[1])
        with self.assertRaisesRegex(ProviderRuntimeError, "Restart"):
            runtime.set_access("full")
        runtime.stop()
        runtime.set_access("full")
        runtime.start("full", project=self.project)
        self.assertIn("--allow-dangerously-skip-permissions", launches[2])
        self.assertIn("bypassPermissions", launches[2])
        runtime.stop()
        runtime.set_access("workspace")
        runtime.start("workspace again", project=self.project)
        self.assertNotIn("--allow-dangerously-skip-permissions", launches[3])
        self.assertNotIn("bypassPermissions", launches[3])
        runtime.stop()

    def test_claude_recovered_initialize_permission_has_bound_turn_and_can_resolve(self):
        runtime = ClaudeCodeRuntime(
            binary=self.fixture("claude-recovered", CLAUDE_RECOVERED_FIXTURE),
            session_id="resumed-session",
        )
        runtime.initialize(project=self.project, model="sonnet")
        events = wait_for(runtime, lambda rows: any(row["type"] == "approval.requested" for row in rows))
        approval = next(row for row in events if row["type"] == "approval.requested")
        self.assertTrue(approval["data"]["recovered"])
        self.assertTrue(approval["data"]["turnId"])
        runtime.respond(approval["data"]["requestId"], {"allow": False})
        events = wait_for(runtime, lambda rows: any(row["type"] == "request.resolved" for row in rows))
        resolved = next(row for row in events if row["type"] == "request.resolved")
        self.assertEqual(resolved["data"]["turnId"], approval["data"]["turnId"])
        runtime.stop()

    def test_claude_permission_response_is_claimed_once(self):
        runtime = ClaudeCodeRuntime(binary=self.fixture("claude-atomic", CLAUDE_FIXTURE))
        runtime.start("approve", project=self.project)
        events = wait_for(runtime, lambda rows: any(row["type"] == "approval.requested" for row in rows))
        request_id = next(row for row in events if row["type"] == "approval.requested")["data"]["requestId"]
        entered, release = threading.Event(), threading.Event()
        original_write = runtime._write
        writes = []
        def blocked(value):
            if isinstance(value, dict) and value.get("type") == "control_response":
                writes.append(value)
                entered.set()
                release.wait(2)
            return original_write(value)
        runtime._write = blocked
        first = threading.Thread(target=runtime.respond, args=(request_id, {"allow": True}))
        first.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(ProviderRuntimeError, "stale or unknown"):
            runtime.respond(request_id, {"allow": False})
        release.set()
        first.join(2)
        self.assertEqual(len(writes), 1)
        runtime.stop()

    def test_claude_validates_images_before_launch_and_missing_cli(self):
        runtime = ClaudeCodeRuntime(binary="")
        with self.assertRaisesRegex(ProviderRuntimeError, "CLI is unavailable"):
            runtime.start("hello", project=self.project)
        self.assertFalse(runtime.status()["connected"])
        available = ClaudeCodeRuntime(binary=self.fixture("claude-images", CLAUDE_FIXTURE))
        with self.assertRaisesRegex(ProviderRuntimeError, "valid base64"):
            available.start("hello", project=self.project, images=[{"mimeType":"image/png", "dataBase64":"%%%"}])
        self.assertEqual(available.status()["state"], "offline")

    def test_acp_fixture_is_testable_but_provider_registry_stays_unavailable(self):
        fixture = self.fixture("acp-fixture", ACP_FIXTURE)
        runtime = AcpRuntime("cursor", [fixture])
        result = runtime.start("hello", project=self.project)
        self.assertTrue(result["accepted"])
        wait_for(runtime, lambda rows: any(row["type"] == "message.delta" for row in rows))
        runtime.stop()
        unavailable = create_runtime("cursor", command=[fixture])
        self.assertIsInstance(unavailable, UnavailableRuntime)

    def test_pinned_official_cli_version_and_help_when_installed(self):
        binary = claude_binary()
        if not binary:
            self.skipTest("pinned ignored Claude CLI is not installed")
        version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5, check=True)
        help_result = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=5, check=True)
        self.assertIn("Claude Code", version.stdout)
        self.assertIn("--input-format", help_result.stdout)
        self.assertIn("--permission-prompts", help_result.stdout)
        metadata = probe(binary)
        self.assertTrue(metadata["installed"])
        self.assertEqual(metadata["models"], [])  # Models come from initialize, never guesses.

    def test_unavailable_runtime_fails_closed(self):
        runtime = UnavailableRuntime("cursor", "ACP CLI not found")
        with self.assertRaisesRegex(ProviderRuntimeError, "ACP CLI not found"):
            runtime.start("Hello", project=self.project)


if __name__ == "__main__":
    unittest.main()
