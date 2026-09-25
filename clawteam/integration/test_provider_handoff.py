import tempfile
import unittest
from pathlib import Path

from provider_handoff import HandoffError, ProviderHandoff


class FakePolicy:
    def __init__(self): self.blocks = []; self.blocked_before_decision = False
    def decide(self, catalog, role):
        self.blocked_before_decision = bool(self.blocks)
        return {"candidate": catalog[-1], "requiresSafeHandoff": False}
    def record_quota_exhausted(self, provider, account, reset): self.blocks.append((provider, account, reset))


class FakeHub:
    def __init__(self):
        self.status_value = {"provider": "one", "model": "old", "sessionId": "old-session", "state": "idle", "lastEventSeq": 9, "pendingApprovals": [], "unrecoverableRequests": [], "children": [], "usageSummary": {"reportedTokens": 12}, "nativeStatus": {"currentTurnId": None, "activeTurnId": None, "childInventory": {"complete": True}}}
        self.rotated = []; self.starts = []
    def status(self, team): return dict(self.status_value)
    def rotate_idle_binding(self, team, provider, model, handoff_id):
        self.rotated.append((team, provider, model, handoff_id)); return {"rotated": True, "project": "/safe/project", "workMode": "plan", "oldSessionId": "old-session", "bindingSeq": 10}
    def start(self, team, project, prompt, model, **kwargs):
        self.starts.append((team, project, prompt, model, kwargs)); return {"sessionId": "new-session", "provider": kwargs["provider"]}


class ProviderHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.now = [1000.0]
        self.helper = ProviderHandoff(Path(self.temp.name), now=lambda: self.now[0]); self.hub = FakeHub(); self.policy = FakePolicy()
        self.catalog = [{"provider": "one", "model": "old", "accountId": "a"}, {"provider": "two", "model": "new", "accountId": "b"}]
        self.provenance = {"source": "native-provider", "kind": "quota_exhausted", "provider": "one", "accountId": "a", "resetAt": 1100}
    def tearDown(self): self.temp.cleanup()
    def plan(self): return self.helper.plan(self.hub, self.policy, "team", self.catalog, self.provenance)

    def test_plan_checkpoint_execute_keeps_same_team_and_never_journals_prompt(self):
        plan = self.plan(); handoff_id = plan["id"]
        self.assertEqual(self.policy.blocks, [("one", "a", 1100)])
        self.assertTrue(self.policy.blocked_before_decision)
        self.assertTrue(self.helper.checkpoint(self.hub, "team", handoff_id)["ready"])
        result = self.helper.execute(self.hub, "team", handoff_id, "resume only from user checkpoint")
        self.assertTrue(result["started"]); self.assertEqual(self.hub.starts[0][0], "team")
        raw = next((Path(self.temp.name) / "provider-handoffs").glob("*.json")).read_text()
        self.assertNotIn("resume only", raw); self.assertEqual(result["handoff"]["phase"], "started")

    def test_checkpoint_fails_closed_for_active_turn_or_unknown_native_status(self):
        handoff_id = self.plan()["id"]
        self.hub.status_value["nativeStatus"] = {"currentTurnId": "active"}
        blocked = self.helper.checkpoint(self.hub, "team", handoff_id)
        self.assertFalse(blocked["ready"]); self.assertIn("requires stopped checkpoint", blocked["reason"])
        self.hub.status_value.pop("nativeStatus")
        blocked = self.helper.checkpoint(self.hub, "team", handoff_id)
        self.assertFalse(blocked["ready"])

    def test_provenance_must_be_structured_native_and_matching(self):
        self.provenance["source"] = "parsed-error-text"
        with self.assertRaises(HandoffError): self.plan()
        self.assertFalse(self.helper.describe("team")["active"])

    def test_crash_phase_refuses_duplicate_restart(self):
        handoff_id = self.plan()["id"]
        self.helper.checkpoint(self.hub, "team", handoff_id)
        self.hub.start = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("lost"))
        with self.assertRaises(HandoffError): self.helper.execute(self.hub, "team", handoff_id, "resume")
        self.assertEqual(self.helper.describe("team")["phase"], "rotated")
        with self.assertRaises(HandoffError): self.helper.execute(self.hub, "team", handoff_id, "resume")

    def test_pending_or_active_children_block_execution(self):
        handoff_id = self.plan()["id"]
        self.hub.status_value["children"] = [{"state": "running"}]
        self.assertFalse(self.helper.checkpoint(self.hub, "team", handoff_id)["ready"])
        self.assertEqual(self.hub.rotated, [])

    def test_unverified_child_inventory_blocks_execution(self):
        handoff_id = self.plan()["id"]
        self.hub.status_value["nativeStatus"] = {"currentTurnId": None}
        self.assertFalse(self.helper.checkpoint(self.hub, "team", handoff_id)["ready"])
        self.hub.status_value["nativeStatus"] = {"currentTurnId": None, "childInventory": {"complete": True}}
        self.hub.status_value["children"] = [{"state": "idle"}]
        self.assertFalse(self.helper.checkpoint(self.hub, "team", handoff_id)["ready"])

    def test_planned_journal_is_reused_but_started_journal_archives_for_next_handoff(self):
        first = self.plan()
        self.assertEqual(self.plan()["id"], first["id"])
        self.assertEqual(len(self.policy.blocks), 1)
        self.helper.checkpoint(self.hub, "team", first["id"])
        self.helper.execute(self.hub, "team", first["id"], "resume")
        self.hub.status_value.update({"provider": "two", "model": "new", "sessionId": "new-session"})
        self.catalog = [{"provider": "two", "model": "new", "accountId": "b"}, {"provider": "three", "model": "next", "accountId": "c"}]
        self.provenance.update({"provider": "two", "accountId": "b"})
        second = self.plan()
        self.assertNotEqual(second["id"], first["id"])
        self.assertEqual(len(list((Path(self.temp.name) / "provider-handoffs" / "archive").glob("*.json"))), 1)

    def test_changed_source_binding_blocks_checkpoint_and_execute(self):
        handoff_id = self.plan()["id"]
        self.hub.status_value["model"] = "changed"
        blocked = self.helper.checkpoint(self.hub, "team", handoff_id)
        self.assertFalse(blocked["ready"])
        self.assertIn("no longer matches", blocked["reason"])
        self.hub.status_value["model"] = "old"
        self.assertTrue(self.helper.checkpoint(self.hub, "team", handoff_id)["ready"])
        self.hub.status_value["sessionId"] = "other-session"
        result = self.helper.execute(self.hub, "team", handoff_id, "resume")
        self.assertFalse(result["started"])
        self.assertEqual(self.hub.rotated, [])

    def test_active_native_tool_call_blocks_checkpoint(self):
        handoff_id = self.plan()["id"]
        self.hub.status_value["nativeStatus"] = {"currentTurnId": None, "activeToolCalls": ["call-1"]}
        blocked = self.helper.checkpoint(self.hub, "team", handoff_id)
        self.assertFalse(blocked["ready"])
        self.assertIn("active tool calls", blocked["reason"])


if __name__ == "__main__": unittest.main()
