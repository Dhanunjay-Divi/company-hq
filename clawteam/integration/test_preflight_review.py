from __future__ import annotations

import unittest

from capability_router import route_task
from preflight_review import ReviewError, parse_review, review_plan, review_prompt


class PreflightReviewTest(unittest.TestCase):
    def test_parses_strict_json_and_fenced_json(self):
        direct = parse_review('{"verdict":"approve","confidence":0.8,"addAgents":[],"removeAgents":[],"riskNotes":[],"reason":"good"}')
        self.assertEqual(direct["verdict"], "approve")
        fenced = parse_review('text before ```json\\n{"verdict":"revise","confidence":0.6,"addAgents":["qa-engineer"],"removeAgents":[],"riskNotes":[],"reason":"verify"}\\n``` text after')
        self.assertEqual(fenced["addAgents"], ["qa-engineer"])

    def test_rejects_non_review_output(self):
        with self.assertRaises(ReviewError):
            parse_review("I think this looks fine.")

    def test_model_free_validation_never_calls_a_provider(self):
        plan = route_task("Build a secure API endpoint.")
        review = review_plan(plan, allow_model_calls=False)
        self.assertEqual(review["backend"], "policy")
        self.assertEqual(review["model"], "none")
        self.assertEqual(review["verdict"], "approve")

    def test_review_prompt_contains_compact_plan_and_allowlist(self):
        plan = route_task("Build an OAuth API.")
        prompt = review_prompt(plan)
        self.assertIn("software team", prompt)
        self.assertIn("security-reviewer", prompt)
        self.assertIn('"facets"', prompt)
        self.assertNotIn("facetEvidence", prompt)
        self.assertLess(len(prompt), 10000)


if __name__ == "__main__":
    unittest.main()