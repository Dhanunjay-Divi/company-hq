from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_bridge import (
    BridgeError,
    CodexBridge,
    _StdioConnection,
    get_bridge,
    get_codex_bridge,
)


class FakeConnection:
    def __init__(self, codex_path: Path, number: int):
        self.codex_path = codex_path
        self.number = number
        self.sent: list[dict] = []
        self.on_message = None
        self.on_exit = None
        self.is_running = False
        self.turn_number = 0

    def start(self, on_message, on_exit):
        self.on_message = on_message
        self.on_exit = on_exit
        self.is_running = True

    def running(self):
        return self.is_running

    def close(self):
        self.is_running = False

    def emit(self, message: dict):
        assert self.on_message is not None
        self.on_message(message)

    def send(self, message: dict):
        self.sent.append(json.loads(json.dumps(message)))
        if "id" not in message:
            return
        method = message.get("method")
        if method == "initialize":
            result = {"userAgent": "test"}
        elif method == "thread/start":
            result = {"thread": {"id": f"thr-{self.number}"}}
        elif method == "thread/resume":
            result = {"thread": {"id": message["params"]["threadId"]}}
        elif method == "turn/start":
            self.turn_number += 1
            result = {"turn": {"id": f"turn-{self.number}-{self.turn_number}"}}
        elif method == "turn/steer":
            result = {"turnId": message["params"]["expectedTurnId"]}
        elif method == "turn/interrupt":
            result = {}
        else:
            return
        assert self.on_message is not None
        self.on_message({"id": message["id"], "result": result})


class FakeFactory:
    def __init__(self):
        self.connections: list[FakeConnection] = []

    def __call__(self, codex_path: Path):
        connection = FakeConnection(codex_path, len(self.connections) + 1)
        self.connections.append(connection)
        return connection


class CodexBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="codex-bridge-test-")
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.factory = FakeFactory()
        self.bridge = CodexBridge(
            state_dir=self.root / "runtime",
            connection_factory=self.factory,
            request_timeout=0.2,
            max_events=20,
        )

    def tearDown(self):
        self.bridge.shutdown_all()
        self.temporary.cleanup()

    def start(self, team="team-one"):
        return self.bridge.start(
            team,
            self.project,
            "Reply with a short status.",
            "gpt-5.6-luna",
        )

    def test_start_uses_safe_policy_and_persists_exact_binding(self):
        status = self.start()
        connection = self.factory.connections[0]
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["threadId"], "thr-1")
        self.assertEqual(status["turnId"], "turn-1-1")

        methods = [item.get("method") for item in connection.sent]
        self.assertEqual(
            methods, ["initialize", "initialized", "thread/start", "turn/start"]
        )
        thread_params = connection.sent[2]["params"]
        self.assertEqual(thread_params["cwd"], str(self.project.resolve()))
        self.assertEqual(thread_params["approvalPolicy"], "on-request")
        self.assertEqual(thread_params["approvalsReviewer"], "user")
        self.assertEqual(thread_params["sandbox"], "workspace-write")
        self.assertNotIn("config", thread_params)
        self.assertIn("Use registered Ruflo", thread_params["developerInstructions"])

        turn_params = connection.sent[3]["params"]
        self.assertEqual(turn_params["sandboxPolicy"], {
            "type": "workspaceWrite",
            "writableRoots": [str(self.project.resolve())],
            "networkAccess": False,
        })
        binding_files = list((self.root / "runtime" / "bindings").glob("*.json"))
        self.assertEqual(len(binding_files), 1)
        binding = json.loads(binding_files[0].read_text())
        self.assertEqual(binding["projectRoot"], str(self.project.resolve()))
        self.assertEqual(binding["threadId"], "thr-1")

    def test_binding_resumes_thread_and_rejects_project_switch(self):
        self.start()
        self.bridge.shutdown_all()
        second_factory = FakeFactory()
        second = CodexBridge(
            state_dir=self.root / "runtime",
            connection_factory=second_factory,
            request_timeout=0.2,
            max_events=20,
        )
        self.addCleanup(second.shutdown_all)
        status = second.start(
            "team-one", self.project, "Continue.", "gpt-5.6-luna"
        )
        self.assertEqual(status["threadId"], "thr-1")
        methods = [item.get("method") for item in second_factory.connections[0].sent]
        self.assertIn("thread/resume", methods)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaisesRegex(BridgeError, "different project"):
            second.start("team-one", other, "Continue.", "gpt-5.6-luna")

    def test_send_steers_active_turn_and_starts_next_idle_turn(self):
        self.start()
        connection = self.factory.connections[0]
        response = self.bridge.send("team-one", "More detail.")
        self.assertEqual(response["mode"], "turn/steer")
        self.assertEqual(response["turnId"], "turn-1-1")
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "completed"},
            },
        })
        response = self.bridge.send("team-one", "Next task.")
        self.assertEqual(response["mode"], "turn/start")
        self.assertEqual(response["turnId"], "turn-1-2")

    def test_stop_interrupts_only_the_active_team_turn(self):
        self.start()
        response = self.bridge.stop("team-one")
        self.assertTrue(response["accepted"])
        self.assertEqual(self.bridge.status("team-one")["state"], "stopping")
        interrupt = self.factory.connections[0].sent[-1]
        self.assertEqual(interrupt["method"], "turn/interrupt")
        self.assertEqual(interrupt["params"], {
            "threadId": "thr-1", "turnId": "turn-1-1"
        })

    def test_stop_prevents_a_pending_approval_from_running(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 89,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "itemId": "item-stop",
                "command": "echo should-not-run",
                "cwd": str(self.project),
                "startedAtMs": 1,
            },
        })
        request_id = self.bridge.status("team-one")["pendingApprovals"][0]["requestId"]
        self.bridge.stop("team-one")
        with self.assertRaisesRegex(BridgeError, "not awaiting"):
            self.bridge.approve("team-one", request_id, "approve")
        self.assertFalse(any(
            item.get("id") == 89 and item.get("result", {}).get("decision") == "accept"
            for item in connection.sent
        ))

    def test_approval_is_team_and_turn_bound_and_never_autoapproved(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 90,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "itemId": "item-1",
                "reason": "Needs Bearer secret-token-value",
                "command": (
                    "curl -H 'Authorization: Bearer secret-token-value' "
                    "for owner@example.com"
                ),
                "cwd": str(self.project),
                "startedAtMs": 1,
            },
        })
        status = self.bridge.status("team-one")
        self.assertEqual(status["state"], "awaiting_approval")
        self.assertEqual(len(status["pendingApprovals"]), 1)
        approval = status["pendingApprovals"][0]
        self.assertEqual(approval["availableDecisions"], ["approve", "reject"])
        self.assertNotIn("secret-token-value", json.dumps(approval))
        self.assertNotIn("owner@example.com", json.dumps(approval))
        self.assertFalse(any(
            item.get("id") == 90 and item.get("result", {}).get("decision") == "accept"
            for item in connection.sent
        ))

        response = self.bridge.approve(
            "team-one", approval["requestId"], "approve"
        )
        self.assertTrue(response["accepted"])
        self.assertEqual(connection.sent[-1], {"id": 90, "result": {"decision": "accept"}})
        with self.assertRaisesRegex(BridgeError, "not awaiting|unknown"):
            self.bridge.approve("team-one", approval["requestId"], "approve")

        connection.emit({
            "id": 91,
            "method": "item/fileChange/requestApproval",
            "params": {
                "threadId": "other-thread",
                "turnId": "turn-1-1",
                "itemId": "item-2",
                "startedAtMs": 2,
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 91, "result": {"decision": "decline"}
        })

    def test_unknown_and_unsupported_requests_are_denied(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({"id": 100, "method": "account/chatgptAuthTokens/refresh", "params": {}})
        self.assertEqual(connection.sent[-1]["error"]["code"], -32601)
        connection.emit({
            "id": 101,
            "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "itemId": "item-3",
                "permissions": {},
                "cwd": str(self.project),
                "startedAtMs": 1,
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 101,
            "result": {
                "permissions": {},
                "scope": "turn",
                "strictAutoReview": True,
            },
        })

    def test_events_are_bounded_and_map_real_child_and_numeric_usage(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "method": "item/completed",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "completedAtMs": 2,
                "item": {
                    "id": "collab-1",
                    "type": "collabAgentToolCall",
                    "receiverThreadIds": ["child-real-1"],
                    "agentsStates": {
                        "child-real-1": {
                            "status": "running",
                            "message": "private child detail",
                        }
                    },
                    "status": "completed",
                },
            },
        })
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "tokenUsage": {
                    "total": {"inputTokens": 7, "outputTokens": 3},
                    "accountEmail": "must-not-leak@example.com",
                },
            },
        })
        for number in range(25):
            connection.emit({
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1-1",
                    "itemId": "message-1",
                    "delta": str(number),
                },
            })
        status = self.bridge.status("team-one")
        self.assertEqual(status["children"], [{
            "threadId": "child-real-1",
            "state": "running",
            "source": "collabAgentToolCall",
        }])
        events = self.bridge.events("team-one", 0)
        self.assertEqual(len(events["events"]), 20)
        self.assertTrue(events["truncated"])
        self.assertNotIn("accountEmail", json.dumps(events))

    def test_concurrent_second_start_is_rejected(self):
        self.start()
        failures = []

        def attempt():
            try:
                self.start()
            except BridgeError as exc:
                failures.append(str(exc))

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=1)
        self.assertEqual(len(failures), 1)
        self.assertIn("already has", failures[0])

    def test_singleton_factory_is_keyed_by_resolved_state_directory(self):
        one = get_codex_bridge(self.root / "singleton")
        two = get_codex_bridge(self.root / "singleton" / ".")
        self.assertIs(one, two)
        one.shutdown_all()

    def test_http_convenience_factory_places_state_under_runtime(self):
        bridge = get_bridge(self.root / "http-state")
        self.assertEqual(
            bridge.state_dir, (self.root / "http-state" / "runtime").resolve()
        )
        bridge.shutdown_all()


class StdioConnectionTest(unittest.TestCase):
    def test_process_inherits_environment_without_home_or_config_overrides(self):
        class Process:
            stdin = None
            stdout = []

            def poll(self):
                return 0

        with patch("codex_bridge.subprocess.Popen", return_value=Process()) as popen:
            connection = _StdioConnection(Path("/native/codex"))
            with patch.object(Path, "is_file", return_value=True), patch(
                "codex_bridge.os.access", return_value=True
            ):
                connection.start(lambda _message: None, lambda _reason: None)
        args, kwargs = popen.call_args
        self.assertEqual(
            args[0], ["/native/codex", "app-server", "--listen", "stdio://"]
        )
        self.assertIsNone(kwargs["env"])
        self.assertNotIn("-c", args[0])


if __name__ == "__main__":
    unittest.main()
