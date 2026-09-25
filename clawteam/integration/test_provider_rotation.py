"""Same-team quota rotation integration checks using the real ProviderHub."""
import tempfile
import time
import unittest
from pathlib import Path

from provider_handoff import ProviderHandoff
from routing_policy import RoutingPolicy
from test_routing_service import Factory
from test_provider_hub import FakeCodex
from provider_hub import ProviderHub


def catalog():
    future = time.time() + 3600
    return [
        {"provider": "claude", "model": "sonnet", "accountId": "account-a", "verified": True, "authenticated": True, "available": True, "usageWindows": [{"usedPercent": 100, "resetsAt": future}]},
        {"provider": "codex", "model": "gpt-fixture", "accountId": "account-b", "verified": True, "authenticated": True, "available": True, "usageWindows": []},
    ]


class RotationCodex(FakeCodex):
    """Only the private binding hooks touched by real rotation are emulated."""
    def __init__(self, state_dir):
        super().__init__(); self._rotation_dir = Path(state_dir) / "codex-fixture"; self._rotation_dir.mkdir(parents=True)
        self._worker_store = type("Workers", (), {"_path": lambda _self, team: self._rotation_dir / f"{team}.workers"})()
    def _binding_path(self, team): return self._rotation_dir / f"{team}.binding"
    def _read_binding(self, team): return None


class ProviderRotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); self.project = self.root / "project"; self.project.mkdir()
        self.codex = RotationCodex(self.root / "state"); self.factory = Factory(); self.hub = ProviderHub(self.root / "state", codex=self.codex, runtime_factory=self.factory, max_events=50, poll_interval=.005)
        self.hub.start("same-team", self.project, "hello", "sonnet", provider="claude", work_mode="auto")
        self.runtime = self.hub._sessions["same-team"].runtime; self.runtime.quota = True
        self.runtime.native["childInventory"] = {"complete": True}
        original_status = self.runtime.status
        self.runtime.status = lambda: {**original_status(), "children": []}
        self.policy = RoutingPolicy(self.hub.state_dir / "policy.json")
        self.policy.update_settings({"autoFallback": True, "models": [
            {"provider": "claude", "model": "sonnet", "enabled": True, "sharePercent": 100},
            {"provider": "codex", "model": "gpt-fixture", "enabled": True, "sharePercent": 100},
        ], "preferredSupervisor": {"provider": "codex", "model": "gpt-fixture"}})
        self.manager = ProviderHandoff(self.hub.state_dir / "handoffs")
        self.provenance = {"source": "native-provider", "kind": "quota_exhausted", "provider": "claude", "accountId": "account-a", "resetAt": time.time() + 3600}

    def tearDown(self): self.hub.shutdown_all(); self.temp.cleanup()
    def plan(self): return self.manager.plan(self.hub, self.policy, "same-team", catalog(), self.provenance)

    def test_quota_handoff_preserves_team_history_and_sequence_with_private_backup(self):
        old_events = self.hub.events("same-team")["events"]; old_seq = old_events[-1]["seq"]
        record = self.plan(); self.assertTrue(self.manager.checkpoint(self.hub, "same-team", record["id"])["ready"])
        result = self.manager.execute(self.hub, "same-team", record["id"], "continue from the stopped checkpoint")
        self.assertTrue(result["started"]); self.assertEqual(self.codex.calls[-1][1][0], "same-team")
        epoch = self.hub.state_dir / "handoff-epochs" / f"{record['id']}.json"
        self.assertTrue(epoch.exists()); self.assertGreaterEqual(self.hub._event_store.load("same-team")[-1]["seq"], old_seq)
        self.assertEqual(__import__('json').loads(epoch.read_text())["lastEventSeq"], old_seq)

    def test_pending_active_or_failed_stop_never_starts_replacement(self):
        record = self.plan()
        self.runtime.native["currentTurnId"] = "running"
        self.assertFalse(self.manager.checkpoint(self.hub, "same-team", record["id"])["ready"])
        self.assertFalse(any(call[0] == "start" for call in self.codex.calls))
        self.runtime.native["currentTurnId"] = None
        self.hub._sessions["same-team"].pending["approval"] = {"kind": "approval"}
        self.assertFalse(self.manager.checkpoint(self.hub, "same-team", record["id"])["ready"])
        self.assertFalse(any(call[0] == "start" for call in self.codex.calls))

    def test_failed_runtime_stop_never_starts_replacement(self):
        record = self.plan()
        self.assertTrue(self.manager.checkpoint(self.hub, "same-team", record["id"])["ready"])
        self.runtime.stop = lambda: {"accepted": False}
        with self.assertRaisesRegex(Exception, "handoff did not start"):
            self.manager.execute(self.hub, "same-team", record["id"], "continue")
        self.assertFalse(any(call[0] == "start" for call in self.codex.calls))

    def test_image_handoff_is_blocked_by_service_before_rotation(self):
        # The service guard looks at the transcript attachment records before it
        # calls ProviderHandoff; an image-bearing event must leave this binding.
        self.hub._transcripts.record("same-team", {"seq": 999, "type": "message.user", "threadId": "old", "turnId": "old", "itemId": "old", "data": {"attachments": [{"id": "image-1"}]}})
        from routing_service import RoutingService
        service = RoutingService(self.hub, lambda: {"providers": [
            {"id": "claude", "models": ["sonnet"], "runtimeReady": True, "authentication": "signed_in", "usageWindows": catalog()[0]["usageWindows"]},
            {"id": "codex", "models": ["gpt-fixture"], "runtimeReady": True, "authentication": "signed_in", "usageWindows": []},
        ]}, "gpt-fixture", watch=False)
        try:
            service.policy.update_settings(self.policy.get_settings())
            service.register("same-team")
            self.assertIsNone(service.consider("same-team"))
            self.assertEqual(self.hub.status("same-team")["provider"], "claude")
            self.assertFalse(any(call[0] == "start" for call in self.codex.calls))
        finally: service.close()


if __name__ == "__main__": unittest.main()
