from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hq_api


class FakeHandler:
    def __init__(self):
        self.payload = None
        self.error = None

    def _serve_json(self, payload):
        self.payload = payload

    def _json_error(self, status, message):
        self.error = (status, message)


class FakeBridge:
    def __init__(self):
        self.started = None
        self.events = []

    def start(self, team, project, prompt, model):
        self.started = (team, project, prompt, model)
        return {"state": "running", "team": team, "model": model}

    def record_event(self, team, event_type, data):
        self.events.append((team, event_type, data))


def sample_plan():
    return {
        "schema": 1, "goal": "Build endpoint", "buildRequest": True,
        "facets": ["backend"], "facetEvidence": {}, "projectSignals": {},
        "risk": {"level": "medium", "reasons": ["api"]},
        "supervisor": {"tier": "expert", "codexModel": "gpt-5.6-sol", "reason": "complex"},
        "agents": [{"id": "backend-engineer", "covers": ["backend"], "source": [], "packet": "Implement."}],
        "skills": [{"id": "bounded-plan", "source": "superpowers", "packet": "Plan.", "load": "on-demand"}],
        "tools": [], "unavailableToolCandidates": ["codegraph"],
        "preflightReview": {"required": True, "crossFamily": "required-when-available", "tier": "expert"},
        "constraints": ["Spawn only useful agents."],
    }


class HQAPIRoutingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hq-api-route-")
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.routing = self.root / "routing.json"
        self.routing.write_text(json.dumps({"reviewed_codex_models": ["gpt-5.6-sol", "gpt-6-astra"]}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_route_preview_is_deterministic_and_model_free(self):
        handler = FakeHandler()
        plan = sample_plan()
        with patch("hq_api.project_for", return_value=str(self.project)), \
             patch("hq_api.route_task", return_value=plan) as route, \
             patch("hq_api.health_snapshot", return_value={"capabilities": {"codeGraph": {"available": False}}}), \
             patch("hq_api.review_plan", side_effect=AssertionError("preview must not call a model")):
            handled = hq_api.handle_post(handler, self.root, "/api/runtime/team-one/route", {"prompt": "Build endpoint"})
        self.assertTrue(handled)
        self.assertEqual(handler.payload, plan)
        self.assertIsNone(handler.error)
        route.assert_called_once()

    def test_start_reviews_then_uses_risk_selected_model_and_packet(self):
        handler = FakeHandler(); client = FakeBridge(); plan = sample_plan()
        review = {"verdict": "approve", "confidence": 0.9, "addAgents": [], "removeAgents": [],
                  "riskNotes": [], "reason": "Plan is appropriately scoped.",
                  "providerFamily": "anthropic", "model": "opus", "crossFamily": True, "backend": "claude-code"}
        with patch("hq_api.project_for", return_value=str(self.project)), \
             patch("hq_api.route_task", return_value=plan), \
             patch("hq_api.review_plan", return_value=review), \
             patch("hq_api.review_is_sufficient", return_value=True), \
             patch("hq_api.health_snapshot", return_value={"capabilities": {}}), \
             patch("hq_api.routing_path", return_value=self.routing), \
             patch("hq_api.bridge", return_value=client), \
             patch("hq_api.demo_mode", return_value=False):
            handled = hq_api.handle_post(handler, self.root, "/api/runtime/team-one/start",
                                         {"prompt": "Build endpoint", "model": "auto"})
        self.assertTrue(handled)
        self.assertIsNone(handler.error)
        self.assertEqual(client.started[3], "gpt-5.6-sol")
        self.assertIn("[COMPANY_HQ_REVIEWED_ROUTING_PACKET]", client.started[2])
        self.assertIn("backend-engineer", client.started[2])
        self.assertEqual(client.events[0][1], "preflight.reviewed")
        self.assertEqual(client.events[0][2]["reviewerFamily"], "anthropic")
        self.assertEqual(handler.payload["routingPlan"]["review"]["verdict"], "approve")

    def test_blocked_preflight_never_starts_executor(self):
        handler = FakeHandler(); client = FakeBridge(); plan = sample_plan()
        review = {"verdict": "block", "reason": "Missing a required safety boundary",
                  "providerFamily": "anthropic", "model": "opus", "crossFamily": True}
        with patch("hq_api.project_for", return_value=str(self.project)), \
             patch("hq_api.route_task", return_value=plan), \
             patch("hq_api.review_plan", return_value=review), \
             patch("hq_api.review_is_sufficient", return_value=False), \
             patch("hq_api.health_snapshot", return_value={"capabilities": {}}), \
             patch("hq_api.bridge", return_value=client), \
             patch("hq_api.demo_mode", return_value=False):
            hq_api.handle_post(handler, self.root, "/api/runtime/team-one/start",
                               {"prompt": "Build endpoint", "model": "auto"})
        self.assertIsNone(client.started)
        self.assertEqual(handler.error[0], 400)
        self.assertIn("Preflight review blocked execution", handler.error[1])


if __name__ == "__main__":
    unittest.main()