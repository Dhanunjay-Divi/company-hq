from __future__ import annotations

import unittest
import tempfile
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
            with patch.object(hq_api.TeamManager, "get_team", return_value=team), patch("hq_api.bridge", return_value=fake_bridge):
                handled = hq_api.handle_post(handler, state, "/api/runtime/chat-one/start", {
                    "prompt": "Help me shape this idea.", "model": "auto",
                })
        self.assertTrue(handled)
        self.assertIsNone(handler.error)
        self.assertEqual(handler.response, {"accepted": True})
        self.assertEqual(fake_bridge.started[0], "chat-one")
        self.assertEqual(fake_bridge.started[1], str(workspace.resolve()))
        self.assertEqual(fake_bridge.started[3], "gpt-5.6-terra")


if __name__ == "__main__":
    unittest.main()
