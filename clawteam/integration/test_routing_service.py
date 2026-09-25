"""Routing service integration checks with real ProviderHub fixture state."""
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from routing_service import RoutingService
from test_provider_hub import FakeCodex, FakeClaude
from provider_hub import ProviderHub


class NativeFixture(FakeClaude):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.quota = False
        self.native = {"currentTurnId": None, "activeTurnId": None, "activeToolCalls": []}
    def status(self):
        value = super().status(); value.update({"nativeStatus": dict(self.native)})
        if self.quota: value["quotaFailure"] = {"source": "native-provider", "kind": "quota_exhausted"}
        return value


class Factory:
    def __init__(self): self.runtimes = []
    def __call__(self, provider, **kwargs):
        runtime = NativeFixture(**kwargs); runtime.provider = provider; self.runtimes.append(runtime); return runtime


class RoutingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); self.project = self.root / "project"; self.project.mkdir()
        self.codex = FakeCodex(); self.factory = Factory()
        self.hub = ProviderHub(self.root / "state", codex=self.codex, runtime_factory=self.factory, max_events=50, poll_interval=.005)
        self.windows = [{"usedPercent": 12, "resetsAt": time.time() + 3600}]
        self.service = RoutingService(self.hub, self.providers, "gpt-fixture", watch=False)

    def tearDown(self): self.service.close(); self.hub.shutdown_all(); self.temp.cleanup()
    def providers(self):
        checked = time.time()
        return {"providers": [
            {"id": "codex", "label": "Codex", "models": ["gpt-fixture"], "runtimeReady": True, "authentication": "signed_in", "checkedAt": checked, "usageWindows": list(self.windows)},
            {"id": "claude", "label": "Claude", "models": ["sonnet"], "runtimeReady": True, "authentication": "signed_in", "checkedAt": checked, "usageWindows": list(self.windows)},
        ]}
    def start_claude(self, team):
        self.hub.start(team, self.project, "hello", "sonnet", provider="claude", work_mode="auto")
        return self.hub._sessions[team]

    def test_usage_sums_two_same_model_sessions_and_never_fabricates_unreported_zero(self):
        initial = self.service.snapshot()
        self.assertNotIn("claude\x1fsonnet", initial["settings"]["reportedUsage"])
        one, two = self.start_claude("one"), self.start_claude("two")
        one.usage_details = {"totalTokens": 31}; two.usage_details = {"totalTokens": 19}
        self.service._usage()
        self.assertEqual(self.service.policy.get_settings()["reportedUsage"]["claude\x1fsonnet"], 50)

    def test_initial_supervisor_stays_codex_when_another_provider_is_signed_in(self):
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot["settings"]["preferredSupervisor"], {"provider": "codex", "model": "gpt-fixture"})
        self.assertEqual(snapshot["selection"]["candidate"]["provider"], "codex")

    def test_disabled_and_zero_share_models_are_enforced_without_auto_adjusting_ceiling(self):
        self.service.snapshot()
        self.service.update({"autoFallback": True, "models": [
            {"provider": "codex", "model": "gpt-fixture", "enabled": True, "sharePercent": 25},
            {"provider": "claude", "model": "sonnet", "enabled": False, "sharePercent": 0},
        ], "preferredSupervisor": {"provider": "codex", "model": "gpt-fixture"}, "tokenPool": {"limitTokens": 100}})
        self.assertEqual(self.service.policy.get_settings()["models"][0]["sharePercent"], 25)
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.service.authorize("claude", "sonnet")
        self.service.policy.record_reported_usage("codex", "gpt-fixture", 25)
        with self.assertRaisesRegex(ValueError, "share is exhausted"):
            self.service.authorize("codex", "gpt-fixture")
        self.service.authorize("unknown", "model")
        self.service.policy.record_reported_usage("codex", "gpt-fixture", 100)
        with self.assertRaisesRegex(ValueError, "token pool is exhausted"):
            self.service.authorize("unknown", "model")

    def test_public_update_rejects_partial_wrapped_and_typo_payloads_without_resetting_state(self):
        saved = {"autoFallback": False, "models": [{"provider": "codex", "model": "gpt-fixture", "enabled": True, "sharePercent": 37}], "preferredSupervisor": {"provider": "codex", "model": "gpt-fixture"}}
        self.service.update(saved)
        before = self.service.policy.get_settings()
        invalid = [{}, {"settings": saved}, {**saved, "extra": True}, {"autoFallback": False, "models": [{"provider": "codex", "model": "gpt-fixture", "enabled": True, "sharePercnt": 37}]}]
        for payload in invalid:
            with self.assertRaises(ValueError): self.service.update(payload)
            self.assertEqual(self.service.policy.get_settings(), before)

    def test_compacted_handoff_prompt_keeps_safety_prefix(self):
        rows = [{"type": "message.user", "data": {"text": "x" * 2200}} for _ in range(20)]
        prompt = self.service._handoff_prompt(rows, limit=700)
        self.assertTrue(prompt.startswith("Continue the unfinished user task after a provider quota failure."))
        self.assertLessEqual(len(prompt), 700)

    def test_old_image_outside_compact_page_prevents_automatic_handoff(self):
        self.service.snapshot()
        self.service.register('image-task')
        archive = self.hub._transcripts
        archive.record('image-task', {'seq': 1, 'type': 'message.user', 'data': {'text': 'Use the image', 'attachments': [{'id':'fixture-image'}]}})
        for seq in range(2, 20):
            archive.record('image-task', {'seq':seq,'type':'message.user','data':{'text':'follow-up'}})
        self.assertTrue(archive.contains_attachments('image-task'))
        status = {'provider':'codex','model':'gpt-fixture','state':'error','quotaFailure':{'kind':'quota_exhausted'}}
        with patch.object(self.hub, 'status', return_value=status), patch('provider_handoff.ProviderHandoff.plan') as plan:
            self.assertIsNone(self.service.consider('image-task'))
        plan.assert_not_called()
        self.assertIn('images', self.service.notes['image-task']['message'])

    def test_expired_reset_refreshes_once_and_only_clears_on_fresh_reported_allowance(self):
        calls = []
        self.windows = [{"usedPercent": 100, "resetsAt": time.time() - 1}]
        def refresh(provider):
            calls.append(provider)
            self.windows = [{"usedPercent": 15, "resetsAt": time.time() + 3600}]
        service = RoutingService(self.hub, self.providers, "gpt-fixture", provider_refresh=refresh, refresh_backoff=5, watch=False)
        try:
            self.assertTrue(service._refresh_expired_account("claude", "native-account"))
            self.assertFalse(service._refresh_expired_account("claude", "native-account"))
            self.assertEqual(calls, ["claude"])
        finally: service.close()

    def test_refresh_accepts_the_connected_provider_iso_checked_at_contract(self):
        self.windows = [{"usedPercent": 12, "resetsAt": time.time() + 3600}]
        def snapshot():
            return {"providers": [{"id": "claude", "models": [], "runtimeReady": True, "authentication": "signed_in", "checkedAt": datetime.now(timezone.utc).isoformat(), "usageWindows": list(self.windows)}]}
        service = RoutingService(self.hub, snapshot, "gpt-fixture", provider_refresh=lambda provider: None, watch=False)
        try:
            self.assertTrue(service.refresh_account("claude", "native-account"))
        finally: service.close()

    def test_snapshot_refreshes_an_elapsed_enrolled_account_block_before_selecting(self):
        self.service.snapshot()
        self.service.policy.record_quota_exhausted("codex", "native-account", time.time() + .01)
        time.sleep(.02)
        calls = []
        service = RoutingService(self.hub, self.providers, "gpt-fixture", provider_refresh=lambda provider: calls.append(provider), watch=False)
        try:
            snapshot = service.snapshot()
            self.assertEqual(calls, ["codex"])
            self.assertEqual(snapshot["selection"]["candidate"]["provider"], "codex")
            self.assertNotIn("codex\x1fnative-account", service.policy._state["accountBlocks"])
        finally: service.close()

    def test_provider_reset_makes_same_account_eligible_only_after_all_exhausted_windows_reset(self):
        self.service.snapshot()
        policy = self.service.policy
        policy.update_settings({"autoFallback": True, "models": [{"provider": "claude", "model": "sonnet", "enabled": True, "sharePercent": 100}]})
        self.windows = [{"usedPercent": 100, "resetsAt": time.time() + .01}, {"usedPercent": 100, "resetsAt": time.time() + .02}]
        policy.record_quota_exhausted("claude", "native-account", self.windows[-1]["resetsAt"])
        self.assertIsNone(policy.decide(self.service.catalog())["candidate"])
        time.sleep(.03)
        self.windows = [{"usedPercent": 10, "resetsAt": time.time() + 100}]
        policy.refresh_account("claude", "native-account")
        self.assertEqual(policy.decide(self.service.catalog())["candidate"]["provider"], "claude")


if __name__ == "__main__": unittest.main()
