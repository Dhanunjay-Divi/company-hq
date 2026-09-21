from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from capability_router import apply_review, compact_packet, route_task


class CapabilityRouterTest(unittest.TestCase):
    def test_high_risk_build_uses_apex_and_minimum_specialists(self):
        plan = route_task("Build an OAuth billing API and React dashboard with tests.")
        self.assertTrue(plan["buildRequest"])
        self.assertEqual(plan["risk"]["level"], "high")
        self.assertEqual(plan["supervisor"]["tier"], "apex")
        self.assertEqual(plan["supervisor"]["codexModel"], "gpt-6-astra")
        ids = {item["id"] for item in plan["agents"]}
        self.assertIn("security-reviewer", ids)
        self.assertIn("frontend-engineer", ids)
        self.assertIn("backend-engineer", ids)
        self.assertIn("qa-engineer", ids)
        self.assertLessEqual(len(ids), 5)
        self.assertTrue(plan["preflightReview"]["required"])

    def test_refactor_prefers_codegraph_and_serena_without_full_catalog(self):
        with tempfile.TemporaryDirectory(prefix="hq-router-java-") as temp:
            root = Path(temp)
            (root / "pom.xml").write_text("<project/>", encoding="utf-8")
            (root / "Service.java").write_text("class Service {}", encoding="utf-8")
            plan = route_task("Refactor and rename the payment service across this Java monorepo.", root)
        self.assertEqual(plan["risk"]["level"], "medium")
        self.assertEqual(plan["supervisor"]["codexModel"], "gpt-5.6-sol")
        tools = [item["id"] for item in plan["tools"]]
        self.assertIn("codegraph", tools)
        self.assertIn("serena", tools)
        self.assertNotIn("graft", tools)
        self.assertLessEqual(len(plan["skills"]), 6)

    def test_specialized_media_and_research_skills_are_lazy(self):
        video = route_task("Create a product launch demo video and marketing trailer.")
        self.assertIn("video-specialist", {a["id"] for a in video["agents"]})
        self.assertIn("video-workflow", {s["id"] for s in video["skills"]})
        research = route_task("Research scientific papers and benchmark the proposed method.")
        self.assertIn("research-specialist", {a["id"] for a in research["agents"]})
        self.assertIn("scientific-research", {s["id"] for s in research["skills"]})
        self.assertFalse(research["preflightReview"]["required"])

    def test_reviewer_cannot_invent_agents(self):
        plan = route_task("Build a small FastAPI endpoint and tests.")
        reviewed = apply_review(plan, {
            "verdict": "revise", "confidence": 0.9,
            "addAgents": ["security-reviewer", "made-up-super-agent"],
            "removeAgents": [], "riskNotes": [], "reason": "Add security review.",
            "providerFamily": "anthropic", "model": "opus", "crossFamily": True,
        })
        ids = {item["id"] for item in reviewed["agents"]}
        self.assertNotIn("made-up-super-agent", ids)
        self.assertLessEqual(len(ids), 5)
        packet = compact_packet(reviewed)
        self.assertNotIn("facetEvidence", packet)
        self.assertLess(len(packet), 9000)


if __name__ == "__main__":
    unittest.main()