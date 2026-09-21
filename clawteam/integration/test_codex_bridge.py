from __future__ import annotations

import json
import hashlib
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
        elif method == "thread/goal/set":
            result = {"goal": {"tokenBudget": message["params"]["tokenBudget"]}}
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


class ImmediateTurnNotificationsConnection(FakeConnection):
    def __init__(self, codex_path: Path, number: int, *, on_method: str):
        super().__init__(codex_path, number)
        self.on_method = on_method

    def send(self, message: dict):
        super().send(message)
        if message.get("method") != self.on_method:
            return
        if self.on_method == "turn/start":
            turn_id = f"turn-{self.number}-{self.turn_number}"
        else:
            turn_id = message["params"]["expectedTurnId"]
        thread_id = message["params"]["threadId"]
        self.emit({
            "method": "item/completed",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "item": {"id": f"message-{turn_id}", "type": "agentMessage", "text": "Instant reply"},
            },
        })
        self.emit({
            "method": "turn/completed",
            "params": {
                "threadId": thread_id,
                "turn": {"id": turn_id, "status": "completed"},
            },
        })


class ImmediateTurnNotificationsFactory:
    def __init__(self, on_method: str):
        self.connections: list[ImmediateTurnNotificationsConnection] = []
        self.on_method = on_method

    def __call__(self, codex_path: Path):
        connection = ImmediateTurnNotificationsConnection(
            codex_path, len(self.connections) + 1, on_method=self.on_method,
        )
        self.connections.append(connection)
        return connection


class ImmediateApprovalConnection(FakeConnection):
    def send(self, message: dict):
        super().send(message)
        if message.get("method") != "turn/start":
            return
        self.emit({
            "id": 100 + self.turn_number,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": message["params"]["threadId"],
                "turnId": f"turn-{self.number}-{self.turn_number}",
                "itemId": f"approval-{self.turn_number}",
                "command": "touch requested-file",
                "cwd": message["params"]["cwd"],
                "reason": "Immediate approval request",
            },
        })


class ImmediateApprovalFactory:
    def __init__(self):
        self.connections: list[ImmediateApprovalConnection] = []

    def __call__(self, codex_path: Path):
        connection = ImmediateApprovalConnection(codex_path, len(self.connections) + 1)
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

    def finish_plan_and_begin_execution(self, team="team-one"):
        connection = self.factory.connections[0]
        turn_id = self.bridge.status(team)["turnId"]
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": self.bridge.status(team)["threadId"],
                "turn": {"id": turn_id, "status": "completed"},
            },
        })
        self.bridge.begin_execution(team)
        return connection

    def test_start_uses_safe_policy_and_persists_exact_binding(self):
        status = self.start()
        connection = self.factory.connections[0]
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["threadId"], "thr-1")
        self.assertEqual(status["turnId"], "turn-1-1")
        self.assertEqual(status["mode"], "plan")
        self.assertFalse(status["planReady"])

        methods = [item.get("method") for item in connection.sent]
        self.assertEqual(
            methods, ["initialize", "initialized", "thread/start", "thread/goal/set", "turn/start"]
        )
        thread_params = connection.sent[2]["params"]
        self.assertEqual(thread_params["cwd"], str(self.project.resolve()))
        self.assertEqual(thread_params["approvalPolicy"], "on-request")
        self.assertEqual(thread_params["approvalsReviewer"], "user")
        self.assertEqual(thread_params["sandbox"], "read-only")
        self.assertNotIn("config", thread_params)
        self.assertIn("Use registered Ruflo", thread_params["developerInstructions"])
        self.assertIn("read-only planning mode", thread_params["developerInstructions"])
        self.assertIn("gpt-6-astra", thread_params["developerInstructions"])
        self.assertIn("gpt-5.6-terra or gpt-5.6-sol", thread_params["developerInstructions"])
        self.assertIn("small bounded leaf tasks", thread_params["developerInstructions"])

        goal_params = connection.sent[3]["params"]
        self.assertEqual(goal_params["tokenBudget"], 200000)
        turn_params = connection.sent[4]["params"]
        self.assertEqual(turn_params["sandboxPolicy"], {"type": "readOnly"})
        binding_files = list((self.root / "runtime" / "bindings").glob("*.json"))
        self.assertEqual(len(binding_files), 1)
        binding = json.loads(binding_files[0].read_text())
        self.assertEqual(binding["projectRoot"], str(self.project.resolve()))
        self.assertEqual(binding["threadId"], "thr-1")
        self.assertEqual(binding["mode"], "plan")
        self.assertFalse(binding["planReady"])

    def test_automatic_new_chat_starts_in_workspace_without_plan_gate(self):
        status = self.bridge.start('auto-chat', self.project, 'Implement the fix.', 'gpt-5.6-terra', work_mode='auto')
        self.assertEqual(status['mode'], 'execute')
        self.assertFalse(status['planReady'])
        sent = self.factory.connections[0].sent
        thread = next(m['params'] for m in sent if m.get('method') == 'thread/start')
        turn = next(m['params'] for m in sent if m.get('method') == 'turn/start')
        self.assertEqual(thread['sandbox'], 'workspace-write')
        self.assertEqual(turn['sandboxPolicy'], {'type': 'workspaceWrite', 'writableRoots': [str(self.project.resolve())], 'networkAccess': False})
        self.assertEqual(turn['approvalPolicy'], 'on-request')
        self.assertEqual(turn['approvalsReviewer'], 'user')
        self.assertIn('do not wait for a separate plan approval', thread['developerInstructions'])

    def test_new_preference_cannot_upgrade_existing_readonly_chat(self):
        self.start()
        self.bridge.shutdown_all()
        status = self.bridge.start('team-one', self.project, 'Continue', 'gpt-5.6-luna', work_mode='auto')
        self.assertEqual(status['mode'], 'plan')
        turn = next(m['params'] for m in self.factory.connections[-1].sent if m.get('method') == 'turn/start')
        self.assertEqual(turn['sandboxPolicy'], {'type': 'readOnly'})

    def test_invalid_work_mode_does_not_start_runtime(self):
        with self.assertRaisesRegex(BridgeError, 'work mode'):
            self.bridge.start('team-one', self.project, 'Continue', 'gpt-5.6-luna', work_mode='unrestricted')
        self.assertEqual(self.factory.connections, [])

    def test_full_access_is_explicit_and_resumes_without_global_config_changes(self):
        status = self.bridge.start('full-chat', self.project, 'Implement.', 'gpt-5.6-terra', work_mode='full')
        self.assertEqual(status['mode'], 'execute')
        self.assertEqual(status['accessMode'], 'full')
        connection = self.factory.connections[-1]
        turn = next(m['params'] for m in connection.sent if m.get('method') == 'turn/start')
        thread = next(m['params'] for m in connection.sent if m.get('method') == 'thread/start')
        self.assertEqual(thread['sandbox'], 'danger-full-access')
        self.assertEqual(turn['sandboxPolicy'], {'type': 'dangerFullAccess'})
        self.assertEqual(turn['approvalPolicy'], 'never')
        self.assertNotIn('config', thread)
        with self.assertRaisesRegex(BridgeError, 'current turn'):
            self.bridge.set_access('full-chat', 'workspace')
        connection.emit({'method':'turn/completed','params':{'threadId':status['threadId'],'turn':{'id':status['turnId'],'status':'completed'}}})
        self.assertEqual(self.bridge.set_access('full-chat', 'workspace')['accessMode'], 'workspace')
        self.bridge.shutdown_all()
        restored = self.bridge.start('full-chat', self.project, 'Continue', 'gpt-5.6-terra', work_mode='full')
        self.assertEqual(restored['accessMode'], 'workspace')

    def test_images_reach_native_start_and_steer_but_events_only_keep_references(self):
        image = self.root / 'test.png'
        image.write_bytes(b'fixture image')
        attachment = {'id':'a'*32, 'name':'test.png', 'path':str(image), 'url':'/api/attachments/team-one/'+('a'*32)}
        self.bridge.start('team-one', self.project, 'Inspect image', 'gpt-5.6-terra', attachments=[attachment])
        connection = self.factory.connections[-1]
        start = next(m['params'] for m in connection.sent if m.get('method') == 'turn/start')
        self.assertEqual(start['input'][1], {'type':'localImage', 'path':str(image)})
        self.bridge.send('team-one', 'Also this', attachments=[attachment])
        steer = next(m['params'] for m in connection.sent if m.get('method') == 'turn/steer')
        self.assertEqual(steer['input'][1], start['input'][1])
        messages = [e for e in self.bridge.events('team-one')['events'] if e['type']=='message.user']
        self.assertEqual(len(messages), 2)
        self.assertNotIn(str(image), json.dumps(messages))
        self.assertEqual(messages[0]['data']['attachments'][0]['name'], 'test.png')

    def test_plan_must_finish_before_execution_and_then_enables_workspace_write(self):
        self.start()
        connection = self.factory.connections[0]
        with self.assertRaisesRegex(BridgeError, "planning turn"):
            self.bridge.begin_execution("team-one")

        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "completed"},
            },
        })
        self.assertTrue(self.bridge.status("team-one")["planReady"])
        response = self.bridge.begin_execution("team-one")
        self.assertTrue(response["accepted"])
        self.assertEqual(response["mode"], "execute")
        self.assertEqual(self.bridge.status("team-one")["mode"], "execute")
        self.assertFalse(self.bridge.status("team-one")["planReady"])
        turn_start = next(
            item for item in reversed(connection.sent)
            if item.get("method") == "turn/start"
        )
        self.assertEqual(turn_start["params"]["sandboxPolicy"], {
            "type": "workspaceWrite",
            "writableRoots": [str(self.project.resolve())],
            "networkAccess": False,
        })
        binding_files = list((self.root / "runtime" / "bindings").glob("*.json"))
        binding = json.loads(binding_files[0].read_text())
        self.assertEqual(binding["mode"], "execute")
        self.assertFalse(binding["planReady"])

        # Native children retain their original sandbox. The handoff must not
        # instruct a read-only planning worker to escalate or write.
        execution_prompt = turn_start['params']['input'][0]['text']
        self.assertIn('Existing workers created in read-only planning retain read-only permissions', execution_prompt)
        self.assertIn('fresh execution worker', execution_prompt)

    def test_interrupted_plan_does_not_unlock_execution(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "interrupted"},
            },
        })
        self.assertEqual(self.bridge.status("team-one")["state"], "idle")
        self.assertFalse(self.bridge.status("team-one")["planReady"])
        with self.assertRaisesRegex(BridgeError, "complete successfully"):
            self.bridge.begin_execution("team-one")
        self.assertEqual(self.bridge.status("team-one")["mode"], "plan")

    def test_execution_transition_is_atomic_when_binding_write_fails(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "completed"},
            },
        })
        with patch.object(self.bridge, "_write_binding", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.bridge.begin_execution("team-one")
        self.assertEqual(self.bridge.status("team-one")["mode"], "plan")

    def test_approval_requests_are_rejected_during_planning(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 88,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "itemId": "planning-write",
                "command": "touch must-not-run",
                "cwd": str(self.project),
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 88, "result": {"decision": "decline"}
        })
        self.assertEqual(self.bridge.status("team-one")["pendingApprovals"], [])
        self.assertEqual(self.bridge.status("team-one")["state"], "running")

    def test_binding_resumes_thread_and_rejects_project_switch(self):
        self.start()
        self.finish_plan_and_begin_execution()
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
        self.assertEqual(status["mode"], "execute")
        self.assertFalse(status["planReady"])
        methods = [item.get("method") for item in second_factory.connections[0].sent]
        self.assertIn("thread/resume", methods)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaisesRegex(BridgeError, "different project"):
            second.start("team-one", other, "Continue.", "gpt-5.6-luna")

    def test_send_steers_active_turn_and_starts_next_idle_turn(self):
        self.start()
        connection = self.factory.connections[0]
        initial_events = self.bridge.events("team-one")["events"]
        self.assertEqual(
            [(event["type"], event["data"].get("text")) for event in initial_events if event["type"] == "message.user"],
            [("message.user", "Reply with a short status.")],
        )
        response = self.bridge.send("team-one", "More detail.")
        self.assertEqual(response["mode"], "turn/steer")
        self.assertEqual(response["turnId"], "turn-1-1")
        user_events = [event for event in self.bridge.events("team-one")["events"] if event["type"] == "message.user"]
        self.assertEqual(
            [(event["turnId"], event["data"]["text"]) for event in user_events],
            [("turn-1-1", "Reply with a short status."), ("turn-1-1", "More detail.")],
        )
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "completed"},
            },
        })
        self.assertTrue(self.bridge.status("team-one")["planReady"])
        response = self.bridge.send("team-one", "Next task.")
        self.assertFalse(self.bridge.status("team-one")["planReady"])
        self.assertEqual(response["mode"], "turn/start")
        self.assertEqual(response["turnId"], "turn-1-2")
        user_events = [event for event in self.bridge.events("team-one")["events"] if event["type"] == "message.user"]
        self.assertEqual(
            [(event["turnId"], event["data"]["text"]) for event in user_events],
            [("turn-1-1", "Reply with a short status."), ("turn-1-1", "More detail."), ("turn-1-2", "Next task.")],
        )

    def test_rejected_steer_does_not_emit_a_user_message(self):
        self.start()
        with patch.object(self.bridge, "_rpc", return_value={"turnId": "wrong-turn"}):
            with self.assertRaisesRegex(BridgeError, "different turn"):
                self.bridge.send("team-one", "Must not appear.")
        user_events = [event for event in self.bridge.events("team-one")["events"] if event["type"] == "message.user"]
        self.assertEqual([event["data"]["text"] for event in user_events], ["Reply with a short status."])

    def test_immediate_start_notifications_follow_accepted_user_message_and_unlock_plan(self):
        factory = ImmediateTurnNotificationsFactory("turn/start")
        bridge = CodexBridge(
            state_dir=self.root / "instant-start-runtime",
            connection_factory=factory,
            request_timeout=0.2,
            max_events=20,
        )
        self.addCleanup(bridge.shutdown_all)
        status = bridge.start("instant-start", self.project, "hello", "gpt-5.6-luna")
        events = bridge.events("instant-start")["events"]
        conversation = [
            (event["type"], event["data"].get("text"))
            for event in events
            if event["type"] in {"message.user", "message.completed", "turn.completed"}
        ]
        self.assertEqual(conversation, [
            ("message.user", "hello"),
            ("message.completed", "Instant reply"),
            ("turn.completed", "Supervisor turn completed"),
        ])
        self.assertEqual(status["state"], "idle")
        self.assertTrue(status["planReady"])
        self.assertTrue(bridge.begin_execution("instant-start")["accepted"])

    def test_immediate_steer_notifications_follow_accepted_user_message(self):
        factory = ImmediateTurnNotificationsFactory("turn/steer")
        bridge = CodexBridge(
            state_dir=self.root / "instant-steer-runtime",
            connection_factory=factory,
            request_timeout=0.2,
            max_events=20,
        )
        self.addCleanup(bridge.shutdown_all)
        bridge.start("instant-steer", self.project, "first", "gpt-5.6-luna")
        bridge.send("instant-steer", "second")
        events = bridge.events("instant-steer")["events"]
        conversation = [
            (event["type"], event["data"].get("text"))
            for event in events
            if event["type"] in {"message.user", "message.completed", "turn.completed"}
        ]
        self.assertEqual(conversation, [
            ("message.user", "first"),
            ("message.user", "second"),
            ("message.completed", "Instant reply"),
            ("turn.completed", "Supervisor turn completed"),
        ])
        self.assertTrue(bridge.status("instant-steer")["planReady"])

    def test_immediate_execution_approval_is_buffered_until_the_new_turn_is_registered(self):
        factory = ImmediateApprovalFactory()
        bridge = CodexBridge(
            state_dir=self.root / "instant-approval-runtime",
            connection_factory=factory,
            request_timeout=0.2,
            max_events=20,
        )
        self.addCleanup(bridge.shutdown_all)
        bridge.start("instant-approval", self.project, "plan", "gpt-5.6-luna")
        connection = factory.connections[0]
        # The planning turn's immediate request remains denied.
        self.assertTrue(any(item.get("id") == 101 and item.get("result", {}).get("decision") == "decline" for item in connection.sent))
        self.assertEqual(bridge.status("instant-approval")["pendingApprovals"], [])
        connection.emit({
            "method": "turn/completed",
            "params": {"threadId": "thr-1", "turn": {"id": "turn-1-1", "status": "completed"}},
        })
        started = bridge.begin_execution("instant-approval")
        self.assertEqual(started["turnId"], "turn-1-2")
        pending = bridge.status("instant-approval")["pendingApprovals"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["command"], "touch requested-file")
        bridge.approve("instant-approval", pending[0]["requestId"], "approve")
        self.assertTrue(any(item.get("id") == 102 and item.get("result", {}).get("decision") == "accept" for item in connection.sent))

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
        connection = self.finish_plan_and_begin_execution()
        active_turn = self.bridge.status("team-one")["turnId"]
        connection.emit({
            "id": 89,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": active_turn,
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
        connection = self.finish_plan_and_begin_execution()
        active_turn = self.bridge.status("team-one")["turnId"]
        connection.emit({
            "id": 90,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": active_turn,
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
                "turnId": active_turn,
                "itemId": "item-2",
                "startedAtMs": 2,
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 91, "result": {"decision": "decline"}
        })

    def test_native_questions_are_turn_bound_and_secret_answers_are_not_persisted(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 120,
            "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1", "itemId": "q-1",
                "questions": [{
                    "id": "password", "header": "Credential",
                    "question": "Enter the temporary credential", "options": [],
                    "isOther": False, "isSecret": True,
                }],
            },
        })
        pending = self.bridge.status("team-one")["pendingApprovals"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kind"], "questions")
        self.assertTrue(pending[0]["questions"][0]["isSecret"])
        secret = "do-not-store-this-answer"
        result = self.bridge.respond("team-one", pending[0]["requestId"], {
            "answers": {"password": {"answers": [secret]}},
        })
        self.assertEqual(result["action"], "respond")
        self.assertEqual(connection.sent[-1], {
            "id": 120,
            "result": {"answers": {"password": {"answers": [secret]}}},
        })
        self.assertNotIn(secret, json.dumps(self.bridge.events("team-one")["events"]))
        with self.assertRaisesRegex(BridgeError, "not awaiting|already resolved"):
            self.bridge.respond("team-one", pending[0]["requestId"], {"answers": {}})

    def test_question_rejects_non_string_answers_without_type_error(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 121, "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "questions": [{
                    "id": "choice", "header": "Choose", "question": "Pick one",
                    "options": [{"label": "A", "description": "first"}],
                }],
            },
        })
        request_id = self.bridge.status("team-one")["pendingApprovals"][0]["requestId"]
        with self.assertRaisesRegex(BridgeError, "unique strings"):
            self.bridge.respond("team-one", request_id, {
                "answers": {"choice": {"answers": [["A"]]}},
            })

    def test_permissions_allow_whole_category_only_and_preserve_denies(self):
        self.bridge.start(
            "permission-team", self.project, "work", "gpt-5.6-terra", work_mode="auto",
        )
        connection = self.factory.connections[0]
        requested = {
            "network": {"enabled": True},
            "fileSystem": {
                "entries": [
                    {"access": "write", "path": {"type": "path", "path": str(self.project)}},
                    {"access": "deny", "path": {"type": "glob_pattern", "pattern": "**/.env"}},
                ],
                "globScanMaxDepth": 10,
            },
        }
        connection.emit({
            "id": 130, "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1", "itemId": "p-1",
                "cwd": str(self.project), "startedAtMs": 1, "permissions": requested,
            },
        })
        pending = self.bridge.status("permission-team")["pendingApprovals"][0]
        self.assertEqual(pending["kind"], "permissions")
        broadened = {
            "network": requested["network"],
            "fileSystem": {"entries": requested["fileSystem"]["entries"][:1]},
        }
        with self.assertRaisesRegex(BridgeError, "subset"):
            self.bridge.respond("permission-team", pending["requestId"], {
                "permissions": broadened, "scope": "turn",
            })
        self.bridge.respond("permission-team", pending["requestId"], {
            "permissions": {"network": requested["network"]}, "scope": "turn",
        })
        self.assertEqual(connection.sent[-1], {
            "id": 130,
            "result": {"permissions": {"network": {"enabled": True}}, "scope": "turn"},
        })

    def test_plan_permissions_are_denied_but_questions_remain_available(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 131, "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1", "itemId": "p-plan",
                "cwd": str(self.project), "startedAtMs": 1,
                "permissions": {"network": {"enabled": True}},
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 131,
            "result": {"permissions": {}, "scope": "turn", "strictAutoReview": True},
        })
        self.assertEqual(self.bridge.status("team-one")["pendingApprovals"], [])

    def test_primitive_elicitation_accepts_values_and_url_mode_fails_closed(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": 140, "method": "mcpServer/elicitation/request",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "serverName": "calendar", "message": "Choose a count", "mode": "form",
                "requestedSchema": {
                    "type": "object", "required": ["count"],
                    "properties": {
                        "count": {"type": "integer", "minimum": 1, "maximum": 5},
                        "notify": {"type": "boolean"},
                    },
                },
            },
        })
        pending = self.bridge.status("team-one")["pendingApprovals"][0]
        self.assertEqual(pending["kind"], "elicitation")
        self.bridge.respond("team-one", pending["requestId"], {
            "action": "accept", "content": {"count": 3, "notify": True},
        })
        self.assertEqual(connection.sent[-1], {
            "id": 140,
            "result": {"action": "accept", "content": {"count": 3, "notify": True}},
        })
        connection.emit({
            "id": 141, "method": "mcpServer/elicitation/request",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "serverName": "calendar", "message": "Open this", "mode": "url",
                "url": "https://example.test/authorize",
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 141, "result": {"action": "decline", "content": None},
        })

    def test_native_resolution_removes_pending_request(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "id": "native-q", "method": "item/tool/requestUserInput",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "questions": [{"id": "q", "header": "Q", "question": "Continue?"}],
            },
        })
        request_id = self.bridge.status("team-one")["pendingApprovals"][0]["requestId"]
        connection.emit({
            "method": "serverRequest/resolved", "params": {"requestId": "native-q"},
        })
        self.assertEqual(self.bridge.status("team-one")["pendingApprovals"], [])
        with self.assertRaisesRegex(BridgeError, "not awaiting|already resolved"):
            self.bridge.respond("team-one", request_id, {"answers": {}})

    def test_new_native_requests_require_schema_ids_and_an_active_turn(self):
        self.start()
        connection = self.factory.connections[0]
        question = {
            "isBlocking": True, "itemId": "q-id",
            "questions": [{"id": "q", "header": "Q", "question": "Continue?"}],
            "threadId": "thr-1",
        }
        connection.emit({
            "id": 160, "method": "item/tool/requestUserInput", "params": question,
        })
        self.assertEqual(connection.sent[-1], {"id": 160, "result": {"answers": {}}})
        self.assertEqual(self.bridge.status("team-one")["pendingApprovals"], [])

        # MCP elicitation alone permits a nullable turn ID, but still requires
        # an explicit matching thread ID and an active local turn.
        form = {
            "threadId": "thr-1", "turnId": None, "serverName": "browser",
            "message": "Allow access?", "mode": "form",
            "requestedSchema": {"type": "object", "properties": {}},
        }
        connection.emit({
            "id": 161, "method": "mcpServer/elicitation/request",
            "params": {key: value for key, value in form.items() if key != "threadId"},
        })
        self.assertEqual(connection.sent[-1], {
            "id": 161, "result": {"action": "decline", "content": None},
        })
        connection.emit({
            "id": 162, "method": "mcpServer/elicitation/request", "params": form,
        })
        pending = self.bridge.status("team-one")["pendingApprovals"][0]
        self.bridge.respond("team-one", pending["requestId"], {
            "action": "decline", "content": None,
        })
        connection.emit({
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": {"id": "turn-1-1", "status": "completed"},
            },
        })
        connection.emit({
            "id": 163, "method": "item/tool/requestUserInput",
            "params": {**question, "turnId": "turn-1-1"},
        })
        self.assertEqual(connection.sent[-1], {"id": 163, "result": {"answers": {}}})
        self.assertEqual(self.bridge.status("team-one")["pendingApprovals"], [])

    def test_permission_request_rejects_wrong_type_thread_id(self):
        self.bridge.start(
            "permission-ids", self.project, "work", "gpt-5.6-terra", work_mode="auto",
        )
        connection = self.factory.connections[0]
        connection.emit({
            "id": 164, "method": "item/permissions/requestApproval",
            "params": {
                "threadId": 1, "turnId": "turn-1-1", "itemId": "p-id",
                "cwd": str(self.project), "startedAtMs": 1,
                "permissions": {"network": {"enabled": True}},
            },
        })
        self.assertEqual(connection.sent[-1], {
            "id": 164,
            "result": {"permissions": {}, "scope": "turn", "strictAutoReview": True},
        })
        self.assertEqual(self.bridge.status("permission-ids")["pendingApprovals"], [])

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
                    "total": {
                        "inputTokens": 7,
                        "cachedInputTokens": 2,
                        "outputTokens": 3,
                        "totalTokens": 10,
                    },
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
        self.assertEqual(status["usageSummary"]["inputTokens"], 7)
        self.assertEqual(status["usageSummary"]["cachedInputTokens"], 2)
        self.assertEqual(status["usageSummary"]["outputTokens"], 3)
        self.assertEqual(status["usageSummary"]["totalTokens"], 10)
        self.assertEqual(status["usageSummary"]["eventCount"], 1)
        events = self.bridge.events("team-one", 0)
        self.assertEqual(len(events["events"]), 20)
        self.assertTrue(events["truncated"])
        self.assertNotIn("accountEmail", json.dumps(events))

    def test_budget_gate_blocks_later_runtime_actions(self):
        self.bridge.set_budget("team-one", 10, True)
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1-1",
                "tokenUsage": {
                    "total": {"totalTokens": 12, "inputTokens": 8, "outputTokens": 4},
                },
            },
        })
        status = self.bridge.status("team-one")
        self.assertTrue(status["budget"]["blocked"])
        self.assertEqual(status["budget"]["usedTokens"], 12)
        work_calls_before = sum(
            item.get("method") in {"turn/start", "turn/steer"}
            for item in connection.sent
        )
        with self.assertRaisesRegex(BridgeError, "budget exhausted"):
            self.bridge.send("team-one", "More work.")
        self.assertEqual(sum(
            item.get("method") in {"turn/start", "turn/steer"}
            for item in connection.sent
        ), work_calls_before)
        for _ in range(20):
            if any(item.get("method") == "turn/interrupt" for item in connection.sent):
                break
            threading.Event().wait(0.01)
        self.assertEqual(
            sum(item.get("method") == "turn/interrupt" for item in connection.sent), 1,
        )
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "tokenUsage": {"total": {"totalTokens": 20}},
            },
        })
        self.assertEqual(
            sum(item.get("method") == "turn/interrupt" for item in connection.sent), 1,
        )
        events = self.bridge.events("team-one", 0)["events"]
        self.assertTrue(any(event["type"] == "budget.exhausted" for event in events))
        self.assertTrue(any(
            event["type"] == "budget.stop_requested"
            and event["data"]["childrenMayContinue"] is True
            for event in events
        ))
        self.assertEqual(self.bridge.status("team-one")["state"], "stopping")

    def test_budget_stop_still_allows_rejecting_pending_permission(self):
        self.bridge.set_budget("budget-permission", 10, True)
        self.bridge.start(
            "budget-permission", self.project, "work", "gpt-5.6-terra", work_mode="auto",
        )
        connection = self.factory.connections[0]
        connection.emit({
            "id": 150, "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1", "itemId": "p-budget",
                "cwd": str(self.project), "startedAtMs": 1,
                "permissions": {"network": {"enabled": True}},
            },
        })
        request_id = self.bridge.status("budget-permission")["pendingApprovals"][0]["requestId"]
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "tokenUsage": {"total": {"totalTokens": 12}},
            },
        })
        self.assertEqual(self.bridge.status("budget-permission")["state"], "stopping")
        result = self.bridge.respond("budget-permission", request_id, {
            "permissions": {}, "scope": "turn",
        })
        self.assertEqual(result["action"], "reject")
        self.assertIn({
            "id": 150, "result": {"permissions": {}, "scope": "turn"},
        }, connection.sent)

    def test_failed_budget_interrupt_restores_active_state_for_manual_retry(self):
        self.bridge.set_budget("interrupt-failure", 10, True)
        self.bridge.start(
            "interrupt-failure", self.project, "work", "gpt-5.6-terra", work_mode="auto",
        )
        connection = self.factory.connections[0]
        original_send = connection.send

        def fail_interrupt(message):
            if message.get("method") == "turn/interrupt":
                connection.sent.append(json.loads(json.dumps(message)))
                raise BridgeError("temporary interrupt failure")
            original_send(message)

        connection.send = fail_interrupt
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "tokenUsage": {"total": {"totalTokens": 12}},
            },
        })
        for _ in range(20):
            if any(
                event["type"] == "budget.stop_failed"
                for event in self.bridge.events("interrupt-failure")["events"]
            ):
                break
            threading.Event().wait(0.01)
        self.assertEqual(self.bridge.status("interrupt-failure")["state"], "running")
        connection.send = original_send
        self.assertTrue(self.bridge.stop("interrupt-failure")["accepted"])

    def test_failed_budget_interrupt_does_not_overwrite_completed_turn(self):
        self.bridge.set_budget("interrupt-complete-race", 10, True)
        self.bridge.start(
            "interrupt-complete-race", self.project, "work", "gpt-5.6-terra", work_mode="auto",
        )
        connection = self.factory.connections[0]
        original_send = connection.send

        def complete_then_fail(message):
            if message.get("method") == "turn/interrupt":
                connection.sent.append(json.loads(json.dumps(message)))
                connection.emit({
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turn": {"id": "turn-1-1", "status": "interrupted"},
                    },
                })
                raise BridgeError("interrupt raced with completion")
            original_send(message)

        connection.send = complete_then_fail
        connection.emit({
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "tokenUsage": {"total": {"totalTokens": 12}},
            },
        })
        for _ in range(20):
            if any(
                event["type"] == "budget.stop_failed"
                for event in self.bridge.events("interrupt-complete-race")["events"]
            ):
                break
            threading.Event().wait(0.01)
        self.assertEqual(self.bridge.status("interrupt-complete-race")["state"], "idle")

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

    def test_sanitized_event_replay_survives_restart_and_continues_sequence(self):
        self.start()
        connection = self.factory.connections[0]
        connection.emit({
            "method": "item/completed",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "item": {"id": "reply-one", "type": "agentMessage", "text": "Done with api_key=secret-value"},
            },
        })
        before = self.bridge.events("team-one", 0)["events"]
        self.bridge.shutdown_all()
        restarted = CodexBridge(
            state_dir=self.root / "runtime", connection_factory=FakeFactory(),
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(restarted.shutdown_all)
        offline = restarted.events("team-one", 0)
        self.assertEqual(restarted.events("team-two", 0)["events"], [])
        self.assertEqual([event["seq"] for event in offline["events"]], [event["seq"] for event in before])
        self.assertEqual(sum(event["type"] == "message.user" for event in offline["events"]), 1)
        self.assertEqual(sum(event["type"] == "message.completed" for event in offline["events"]), 1)
        self.assertIn("api_key=[redacted]", next(event for event in offline["events"] if event["type"] == "message.completed")["data"]["text"])
        resumed = restarted.start("team-one", self.project, "Continue.", "gpt-5.6-luna")
        self.assertGreater(resumed["lastEventSeq"], before[-1]["seq"])
        events = restarted.events("team-one", 0)["events"]
        self.assertEqual([event["seq"] for event in events], sorted({event["seq"] for event in events}))
        self.assertEqual(sum(event["data"].get("text") == "Done with api_key=[redacted]" for event in events), 1)

    def test_event_snapshot_is_capped_and_never_follows_corrupt_or_symlinked_files(self):
        self.start()
        with self.bridge._sessions_lock:
            session = self.bridge._sessions["team-one"]
        for number in range(30):
            self.bridge._event(session, "message.completed", {"text": f"reply-{number}"})
        self.bridge.shutdown_all()
        replay = CodexBridge(
            state_dir=self.root / "runtime", connection_factory=FakeFactory(),
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(replay.shutdown_all)
        events = replay.events("team-one", 0)["events"]
        self.assertLessEqual(len(events), 20)
        self.assertEqual([event["seq"] for event in events], sorted(event["seq"] for event in events))
        path = self.root / "runtime" / "events" / (hashlib.sha256(b"team-one").hexdigest() + ".json")
        self.assertLessEqual(path.stat().st_size, 4 * 1024 * 1024)
        self.assertEqual((path.parent.stat().st_mode & 0o777), 0o700)
        self.assertEqual((path.stat().st_mode & 0o777), 0o600)
        outside = self.root / "outside-events.json"
        outside.write_text('{"team":"team-one","events":[]}')
        path.unlink()
        path.symlink_to(outside)
        unsafe = CodexBridge(
            state_dir=self.root / "runtime", connection_factory=FakeFactory(),
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(unsafe.shutdown_all)
        self.assertEqual(unsafe.events("team-one", 0)["events"], [])
        self.assertEqual(outside.read_text(), '{"team":"team-one","events":[]}')
        path.unlink()
        path.write_text("not json")
        corrupt = CodexBridge(
            state_dir=self.root / "runtime", connection_factory=FakeFactory(),
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(corrupt.shutdown_all)
        self.assertEqual(corrupt.events("team-one", 0)["events"], [])

    def test_delta_tail_cursor_never_reuses_sequence_after_restart(self):
        self.start()
        connection = self.factory.connections[0]
        for text in ("partial one", "partial two", "partial three"):
            connection.emit({
                "method": "item/agentMessage/delta",
                "params": {"threadId": "thr-1", "turnId": "turn-1-1", "delta": text},
            })
        tail_seq = self.bridge.events("team-one", 0)["nextSeq"]
        self.bridge.shutdown_all()
        restarted_factory = FakeFactory()
        restarted = CodexBridge(
            state_dir=self.root / "runtime", connection_factory=restarted_factory,
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(restarted.shutdown_all)
        offline = restarted.events("team-one", tail_seq)
        self.assertEqual(offline["events"], [])
        self.assertGreaterEqual(offline["nextSeq"], tail_seq)
        restarted.start("team-one", self.project, "Continue after restart.", "gpt-5.6-luna")
        continued = restarted.events("team-one", tail_seq)
        self.assertTrue(continued["events"])
        self.assertTrue(all(event["seq"] > tail_seq for event in continued["events"]))

    def test_streaming_delta_flood_retains_user_and_final_reply_in_live_and_restarted_replay(self):
        factory = FakeFactory()
        bridge = CodexBridge(
            state_dir=self.root / "long-stream-runtime", connection_factory=factory,
            request_timeout=0.2, max_events=500,
        )
        self.addCleanup(bridge.shutdown_all)
        bridge.start("long-stream", self.project, "Keep this user message", "gpt-5.6-luna")
        connection = factory.connections[0]
        for number in range(600):
            connection.emit({
                "method": "item/agentMessage/delta",
                "params": {"threadId": "thr-1", "turnId": "turn-1-1", "delta": f"chunk-{number}"},
            })
        connection.emit({
            "method": "item/completed",
            "params": {
                "threadId": "thr-1", "turnId": "turn-1-1",
                "item": {"id": "long-final", "type": "agentMessage", "text": "Final answer survives."},
            },
        })
        live = bridge.events("long-stream", 0)["events"]
        self.assertLessEqual(len(live), 500)
        self.assertIn(("message.user", "Keep this user message"), [(event["type"], event["data"].get("text")) for event in live])
        self.assertIn(("message.completed", "Final answer survives."), [(event["type"], event["data"].get("text")) for event in live])
        bridge.shutdown_all()
        restarted = CodexBridge(
            state_dir=self.root / "long-stream-runtime", connection_factory=FakeFactory(),
            request_timeout=0.2, max_events=500,
        )
        self.addCleanup(restarted.shutdown_all)
        replay = restarted.events("long-stream", 0)["events"]
        self.assertIn(("message.user", "Keep this user message"), [(event["type"], event["data"].get("text")) for event in replay])
        self.assertIn(("message.completed", "Final answer survives."), [(event["type"], event["data"].get("text")) for event in replay])

    def test_full_durable_history_does_not_append_live_delta_tail_past_event_cap(self):
        factory = FakeFactory()
        bridge = CodexBridge(
            state_dir=self.root / "full-durable-runtime", connection_factory=factory,
            request_timeout=0.2, max_events=20,
        )
        self.addCleanup(bridge.shutdown_all)
        bridge.start("full-durable", self.project, "start", "gpt-5.6-luna")
        with bridge._sessions_lock:
            session = bridge._sessions["full-durable"]
        for number in range(25):
            bridge._event(session, "message.completed", {"text": f"durable-{number}"})
        for number in range(30):
            bridge._event(session, "message.delta", {"text": f"delta-{number}"})
        visible = bridge.events("full-durable", 0)["events"]
        self.assertEqual(len(session.replay_events), 20)
        self.assertLessEqual(len(visible), 20)
        self.assertTrue(all(event["type"] != "message.delta" for event in visible))

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
