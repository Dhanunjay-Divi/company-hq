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


if __name__ == "__main__":
    unittest.main()
