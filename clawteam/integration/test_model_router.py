from __future__ import annotations

import unittest
from unittest.mock import patch

import model_router as router


POLICY = {
    "reviewed_codex_models": [
        "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"
    ],
    "economy": {
        "tiers": {
            "small": ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"],
            "standard": ["gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"],
            "complex": ["gpt-5.6-sol", "gpt-6-astra"],
        }
    },
}

CATALOG = {
    "verified": True,
    "reason": None,
    "models": [
        {"model": "gpt-5.6-luna", "defaultReasoningEffort": "low", "supportedReasoningEfforts": [{"reasoningEffort": "low"}, {"reasoningEffort": "medium"}]},
        {"model": "gpt-5.6-terra", "defaultReasoningEffort": "medium", "supportedReasoningEfforts": [{"reasoningEffort": "low"}, {"reasoningEffort": "medium"}, {"reasoningEffort": "high"}]},
        {"model": "gpt-5.6-sol", "defaultReasoningEffort": "medium", "supportedReasoningEfforts": [{"reasoningEffort": "medium"}, {"reasoningEffort": "high"}]},
        {"model": "gpt-6-astra", "defaultReasoningEffort": "high", "supportedReasoningEfforts": [{"reasoningEffort": "high"}, {"reasoningEffort": "xhigh"}]},
    ],
}


class ModelRouterTest(unittest.TestCase):
    def route(self, prompt: str, mode: str = "execute", requested: str = "auto"):
        with patch.object(router, "_policy", return_value=POLICY), patch.object(
            router, "reviewed_catalog", return_value=CATALOG
        ):
            return router.choose_model(prompt, mode, requested)

    def test_simple_bounded_work_uses_smallest_reviewed_tier(self):
        result = self.route("Fix a typo in README documentation.", "plan")
        self.assertEqual(result["model"], "gpt-5.6-luna")
        self.assertEqual(result["tier"], "small")
        self.assertEqual(result["effort"], "low")

    def test_normal_implementation_uses_standard_not_flagship(self):
        result = self.route("Implement the API endpoint and tests for the existing feature.")
        self.assertEqual(result["model"], "gpt-5.6-terra")
        self.assertEqual(result["tier"], "standard")
        self.assertEqual(result["effort"], "medium")

    def test_complex_security_migration_uses_complex_tier_before_flagship(self):
        result = self.route(
            "Design the authentication architecture and data migration with concurrency and security constraints."
        )
        self.assertEqual(result["model"], "gpt-5.6-sol")
        self.assertEqual(result["tier"], "complex")
        self.assertEqual(result["effort"], "high")

    def test_flagship_is_fallback_when_smaller_complex_model_is_unavailable(self):
        catalog = {
            "verified": True,
            "reason": None,
            "models": [{"model": "gpt-6-astra"}],
        }
        with patch.object(router, "_policy", return_value=POLICY), patch.object(
            router, "reviewed_catalog", return_value=catalog
        ):
            result = router.choose_model("Security critical distributed transaction migration.")
        self.assertEqual(result["model"], "gpt-6-astra")

    def test_explicit_reviewed_model_stays_user_choice(self):
        result = self.route("Anything", requested="gpt-6-astra")
        self.assertEqual(result["model"], "gpt-6-astra")
        self.assertEqual(result["tier"], "manual")

    def test_auto_fails_closed_without_verified_catalog(self):
        unavailable = {"verified": False, "models": [], "reason": "catalog unavailable"}
        with patch.object(router, "_policy", return_value=POLICY), patch.object(
            router, "reviewed_catalog", return_value=unavailable
        ):
            with self.assertRaisesRegex(router.RoutingError, "requires the current native model catalog"):
                router.choose_model("Implement the feature.")


if __name__ == "__main__":
    unittest.main()
