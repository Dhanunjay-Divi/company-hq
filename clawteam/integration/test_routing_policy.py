import tempfile
import unittest
from pathlib import Path

from routing_policy import RoutingPolicy, RoutingPolicyError


def fact(provider, model, account="account", **extra):
    return {"provider": provider, "model": model, "accountId": account, "verified": True, "authenticated": True, "available": True, **extra}


class RoutingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.now = [1_000.0]
        self.policy = RoutingPolicy(Path(self.temporary.name) / "routing-policy.json", now=lambda: self.now[0])

    def tearDown(self):
        self.temporary.cleanup()

    def configure(self, **more):
        return self.policy.update_settings({"autoFallback": True, "models": [
            {"provider": "one", "model": "strong", "enabled": True, "sharePercent": 70},
            {"provider": "two", "model": "backup", "enabled": True, "sharePercent": 30},
        ], **more})

    def test_settings_are_allowlisted_atomic_and_validate_sliders(self):
        saved = self.configure(preferredSupervisor={"provider": "one", "model": "strong"}, tokenPool={"limitTokens": 100})
        self.assertTrue(saved["autoFallback"])
        self.assertEqual(saved["models"][0]["sharePercent"], 70)
        self.assertEqual(RoutingPolicy(self.policy.path).get_settings()["tokenPool"]["limitTokens"], 100)
        with self.assertRaises(RoutingPolicyError):
            self.policy.update_settings({"models": [{"provider": "one", "model": "bad", "sharePercent": 101}]})

    def test_supervisor_uses_explicit_stable_preference_not_catalog_order(self):
        self.configure(preferredSupervisor={"provider": "one", "model": "strong"})
        result = self.policy.decide([fact("two", "backup"), fact("one", "strong")], role="supervisor")
        self.assertEqual(result["candidate"]["model"], "strong")
        self.assertFalse(result["fallback"])

    def test_quota_blocks_account_siblings_then_reuses_after_known_reset(self):
        self.policy.update_settings({"autoFallback": True, "models": [
            {"provider": "one", "model": "a", "enabled": True, "sharePercent": 50},
            {"provider": "one", "model": "b", "enabled": True, "sharePercent": 50},
            {"provider": "two", "model": "backup", "enabled": True, "sharePercent": 50},
        ]})
        exhausted = fact("one", "a", "shared", usageWindows=[{"usedPercent": 100, "resetsAt": 1100}])
        result = self.policy.decide([exhausted, fact("one", "b", "shared"), fact("two", "backup", "other")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.assertTrue(result["requiresSafeHandoff"])
        self.assertTrue(any("account quota cooldown" in item["reason"] for item in result["rejected"]))
        self.now[0] = 1101
        self.policy.refresh_account("one", "shared")
        result = self.policy.decide([fact("one", "a", "shared"), fact("one", "b", "shared"), fact("two", "backup", "other")])
        self.assertEqual(result["candidate"]["model"], "a")

    def test_account_cooldown_waits_for_last_exhausted_window_and_ignores_malformed_facts(self):
        self.configure()
        result = self.policy.decide([fact("one", "strong", usageWindows=[
            {"usedPercent": 100, "resetsAt": 1050}, {"usedPercent": 100, "resetsAt": 1100},
            {"usedPercent": "100", "resetsAt": "bad"}, {"usedPercent": float("nan"), "resetsAt": 1200},
        ]), fact("two", "backup", "other")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.now[0] = 1075
        self.assertEqual(self.policy.decide([fact("one", "strong"), fact("two", "backup", "other")])["candidate"]["model"], "backup")
        self.now[0] = 1101
        self.policy.refresh_account("one", "account")
        self.assertEqual(self.policy.decide([fact("one", "strong")])["candidate"]["model"], "strong")

    def test_rejects_existing_symlink_state_path(self):
        target = Path(self.temporary.name) / "real.json"
        target.write_text("{}", encoding="utf-8")
        link = Path(self.temporary.name) / "link.json"
        link.symlink_to(target)
        with self.assertRaises(RoutingPolicyError):
            RoutingPolicy(link)

    def test_unknown_reset_fails_closed_until_explicit_refresh(self):
        self.configure()
        self.policy.record_quota_exhausted("one", "account", None)
        result = self.policy.decide([fact("one", "strong"), fact("two", "backup", "other")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.policy.refresh_account("one", "account")
        self.assertEqual(self.policy.decide([fact("one", "strong")])["candidate"]["model"], "strong")

    def test_expired_cached_exhaustion_needs_refresh_without_reclassifying_the_block(self):
        self.configure()
        self.policy.record_quota_exhausted("one", "account", 1001)
        self.now[0] = 1002
        result = self.policy.decide([fact("one", "strong", usageWindows=[{"usedPercent": 100, "resetsAt": 1001}]), fact("two", "backup", "other")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.assertIn("one\x1faccount", self.policy._state["accountBlocks"])

    def test_elapsed_reset_remains_ineligible_for_empty_or_stale_facts_until_fresh_refresh(self):
        self.configure()
        self.policy.record_quota_exhausted("one", "account", 1001)
        self.now[0] = 1002
        for windows in ([], [{"usedPercent": 0, "resetsAt": 999}]):
            result = self.policy.decide([fact("one", "strong", usageWindows=windows), fact("two", "backup", "other")])
            self.assertEqual(result["candidate"]["model"], "backup")
            self.assertTrue(any(item["reason"] == "account quota requires provider refresh" for item in result["rejected"]))
        self.policy.refresh_account("one", "account")
        self.assertEqual(self.policy.decide([fact("one", "strong", usageWindows=[{"usedPercent": 0, "resetsAt": 1200}])])["candidate"]["model"], "strong")

    def test_token_pool_uses_only_reported_usage_and_enforces_share(self):
        self.configure(tokenPool={"limitTokens": 100})
        self.policy.record_reported_usage("one", "strong", 70)
        result = self.policy.decide([fact("one", "strong"), fact("two", "backup")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.policy.record_reported_usage("two", "backup", 30)
        result = self.policy.decide([fact("one", "strong"), fact("two", "backup")])
        self.assertIsNone(result["candidate"])

    def test_catalog_requires_actual_verified_authenticated_available_facts(self):
        self.configure()
        result = self.policy.decide([fact("one", "strong", authenticated=False), fact("two", "backup")])
        self.assertEqual(result["candidate"]["model"], "backup")
        self.assertEqual(result["candidate"]["usageWindows"], [])


if __name__ == "__main__":
    unittest.main()
