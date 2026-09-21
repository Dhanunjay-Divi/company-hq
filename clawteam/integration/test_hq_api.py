from __future__ import annotations

import unittest
import tempfile
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hq_api


class HQAPIDemoTest(unittest.TestCase):
    def test_demo_memory_never_launches_ruflo(self):
        with patch("hq_api.demo_mode", return_value=True), patch(
            "hq_api.memory_call",
            side_effect=AssertionError("Ruflo must not start in model-free demo"),
        ):
            result = hq_api.knowledge("/synthetic/demo/project")
        self.assertEqual(result["source"], "Demo fixture")
        self.assertEqual(result["codeGraph"], "unavailable-in-demo")
        self.assertGreaterEqual(len(result["notes"]), 2)
        self.assertIn("No provider", result["notes"][0]["value"]["content"])

    def test_decisions_account_for_catalog_and_evidence_limits(self):
        result = hq_api.decisions()
        self.assertEqual(result["schema"], 1)
        self.assertEqual(len(result["repositories"]), 40)
        self.assertGreaterEqual(len(result["additionalComponents"]), 7)
        self.assertTrue(any(item["area"] == "Code intelligence" for item in result["decisions"]))
        self.assertTrue(any(item["area"] == "Usage budget enforcement" for item in result["decisions"]))
        self.assertTrue(any(item["area"] == "Runtime language boundary" for item in result["decisions"]))
        self.assertTrue(any(repo["repo"] == "obra/superpowers" for repo in result["repositories"]))
        self.assertTrue(any("Byte size is not token count" in item for item in result["limitations"]))
        self.assertIsNone(hq_api._read_json(hq_api.REPO_ROOT / "benchmarks" / "evidence" / "selection-2026-09-21.json")["actual_model_tokens"])

    def test_auto_start_uses_schema_two_standard_model_for_managed_workspace(self):
        class Handler:
            response = None
            error = None

            def _serve_json(self, value):
                self.response = value

            def _json_error(self, status, message):
                self.error = (status, message)

        class Bridge:
            started = None

            def start(self, *args):
                self.started = args
                return {"accepted": True}

        with tempfile.TemporaryDirectory(prefix="hq-api-managed-") as temporary:
            state = Path(temporary) / "state"
            routing = Path(temporary) / "routing.json"
            routing.write_text(json.dumps({
                "schema": 2,
                "supervisor_tier": "flagship",
                "tiers": {"flagship": {"codex_model": "gpt-6-astra"}},
                "reviewed_codex_models": ["gpt-6-astra"],
            }))
            workspace = state / "managed-workspaces" / "chat-one"
            workspace.mkdir(parents=True)
            hq_api.save_profile(state, "chat-one", {
                "projectLabel": "New conversation",
                "projectRoot": str(workspace.resolve()),
                "workspaceKind": "managed",
                "goal": "Discuss and plan.",
                "members": {"overall-head": {"displayName": "Overall head", "department": "Direction & delivery", "model": "", "reportsTo": None}},
            }, {"overall-head"})
            team = SimpleNamespace(members=[SimpleNamespace(name="overall-head")])
            handler, fake_bridge = Handler(), Bridge()
            with patch.object(hq_api.TeamManager, "get_team", return_value=team), patch("hq_api.bridge", return_value=fake_bridge), patch("hq_api.routing_path", return_value=routing):
                handled = hq_api.handle_post(handler, state, "/api/runtime/chat-one/start", {
                    "prompt": "Help me shape this idea.", "model": "auto",
                })
        self.assertTrue(handled)
        self.assertIsNone(handler.error)
        self.assertEqual(handler.response, {"accepted": True})
        self.assertEqual(fake_bridge.started[0], "chat-one")
        self.assertEqual(fake_bridge.started[1], str(workspace.resolve()))
        self.assertEqual(fake_bridge.started[3], "gpt-6-astra")

    def test_provider_actions_reject_credentials_and_only_dispatch_empty_body(self):
        class Handler:
            response = None
            error = None
            def _serve_json(self, value): self.response = value
            def _json_error(self, status, message): self.error = (status, message)
        from unittest.mock import Mock
        service = Mock()
        service.action.return_value = {'authentication': 'signed_in'}
        for body in ({'apiKey': 'fixture-secret'}, {'path': '/tmp/arbitrary'}, [], None):
            handler = Handler()
            with patch('provider_connections.connections', return_value=service):
                self.assertTrue(hq_api.handle_post(handler, Path('/tmp'), '/api/providers/codex/connect', body))
            self.assertEqual(handler.error[0], 400)
        service.action.assert_not_called()
        handler = Handler()
        with patch('provider_connections.connections', return_value=service):
            hq_api.handle_post(handler, Path('/tmp'), '/api/providers/codex/check', {})
        service.action.assert_called_once_with('codex', 'check')
        self.assertEqual(handler.response, {'authentication': 'signed_in'})

    def test_schema_two_default_supervisor_uses_standard_when_no_explicit_tier_exists(self):
        self.assertEqual(hq_api._default_supervisor_model({
            "schema": 2,
            "escalation": {"start_tier": "standard"},
            "tiers": {"standard": {"codex_model": "gpt-5.6-terra"}},
            "reviewed_codex_models": ["gpt-5.6-terra", "gpt-6-astra"],
        }), "gpt-5.6-terra")

    def test_attach_waits_for_concurrent_start_binding_and_cannot_rewrite_profile(self):
        class Handler:
            response = None
            error = None

            def _serve_json(self, value):
                self.response = value

            def _json_error(self, status, message):
                self.error = (status, message)

        class BlockingBridge:
            def __init__(self, project):
                self.project = project
                self.start_entered = threading.Event()
                self.release_start = threading.Event()
                self.bound = False

            def status(self, team):
                return {"project": str(self.project) if self.bound else None, "threadId": "thread-1" if self.bound else None}

            def start(self, team, project, prompt, model):
                self.asserted_project = project
                self.start_entered.set()
                if not self.release_start.wait(1):
                    raise AssertionError("test did not release start")
                self.bound = True
                return {"accepted": True}

        with tempfile.TemporaryDirectory(prefix="hq-api-attach-race-") as temporary:
            root = Path(temporary)
            state = root / "state"
            managed = state / "managed-workspaces" / "chat-one"
            attached = root / "attached-project"
            managed.mkdir(parents=True)
            attached.mkdir()
            routing = root / "routing.json"
            routing.write_text(json.dumps({"reviewed_codex_models": ["gpt-5.6-luna"]}))
            hq_api.save_profile(state, "chat-one", {
                "projectLabel": "New conversation", "projectRoot": str(managed.resolve()),
                "workspaceKind": "managed", "goal": "Discuss and plan.",
                "members": {"overall-head": {"displayName": "Overall head", "department": "Direction & delivery", "model": "", "reportsTo": None}},
            }, {"overall-head"})
            team = SimpleNamespace(members=[SimpleNamespace(name="overall-head")])
            start_handler, attach_handler = Handler(), Handler()
            fake_bridge = BlockingBridge(managed.resolve())
            with patch.object(hq_api.TeamManager, "get_team", return_value=team), patch("hq_api.bridge", return_value=fake_bridge), patch("hq_api.routing_path", return_value=routing):
                start_thread = threading.Thread(target=hq_api.handle_post, args=(start_handler, state, "/api/runtime/chat-one/start", {"prompt": "Start", "model": "gpt-5.6-luna"}))
                attach_thread = threading.Thread(target=hq_api.handle_post, args=(attach_handler, state, "/api/workspaces/chat-one/attach", {"project": str(attached)}))
                start_thread.start()
                self.assertTrue(fake_bridge.start_entered.wait(1))
                attach_thread.start()
                attach_thread.join(0.05)
                self.assertTrue(attach_thread.is_alive())
                fake_bridge.release_start.set()
                start_thread.join(1)
                attach_thread.join(1)
            self.assertFalse(start_thread.is_alive())
            self.assertFalse(attach_thread.is_alive())
            self.assertEqual(start_handler.response, {"accepted": True})
            self.assertEqual(attach_handler.error[0], 400)
            self.assertIn("already bound", attach_handler.error[1])
            profile = hq_api.load_profile(state, "chat-one", {"overall-head"})
            self.assertEqual(profile["workspaceKind"], "managed")
            self.assertEqual(profile["projectRoot"], str(managed.resolve()))


if __name__ == "__main__":
    unittest.main()
