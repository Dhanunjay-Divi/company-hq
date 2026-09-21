from __future__ import annotations

import unittest
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
        self.assertTrue(any(item["area"] == "Runtime language boundary" for item in result["decisions"]))
        self.assertTrue(any(repo["repo"] == "obra/superpowers" for repo in result["repositories"]))
        self.assertTrue(any("Byte size is not token count" in item for item in result["limitations"]))
        self.assertIsNone(hq_api._read_json(hq_api.REPO_ROOT / "benchmarks" / "evidence" / "selection-2026-09-21.json")["actual_model_tokens"])


if __name__ == "__main__":
    unittest.main()
