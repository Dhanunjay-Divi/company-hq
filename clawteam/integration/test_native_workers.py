from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from native_workers import WorkerDataError, WorkerStore, descendant_workers, latest_active_turn


def thread(thread_id, parent, session="session-one", status="idle", **extra):
    return {
        "id": thread_id,
        "sessionId": session,
        "parentThreadId": parent,
        "status": {"type": status, "activeFlags": []} if status == "active" else {"type": status},
        "updatedAt": extra.pop("updatedAt", 1),
        **extra,
    }


class NativeWorkersTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native-workers-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_descendants_require_parent_chain_and_same_native_session(self):
        root = thread("root", None)
        rows = [
            thread("lead", "root", status="active", model="gpt-5.6-terra"),
            thread("worker", "lead", model="gpt-5.6-luna"),
            thread("unrelated", None),
            thread("forged-cross-session", "root", session="other"),
            thread("orphan", "missing"),
        ]
        workers = descendant_workers(root, rows)
        self.assertEqual([item["threadId"] for item in workers], ["lead", "worker"])
        self.assertEqual(workers[0]["status"], "active")
        serialized = json.dumps(workers)
        self.assertNotIn("cwd", serialized)
        self.assertNotIn("preview", serialized)

    def test_invalid_root_metadata_fails_closed(self):
        with self.assertRaisesRegex(WorkerDataError, "root"):
            descendant_workers({"id": "root"}, [])

    def test_latest_active_turn_uses_only_in_progress_identifier(self):
        self.assertEqual(latest_active_turn({"data": [
            {"id": "active-turn", "status": "inProgress", "items": []},
            {"id": "old-turn", "status": "completed", "items": []},
        ]}), "active-turn")
        self.assertIsNone(latest_active_turn({"data": [
            {"id": "old-turn", "status": "completed"},
        ]}))

    def test_private_store_is_team_bound_and_drops_no_content_into_snapshot(self):
        store = WorkerStore(self.root)
        workers = descendant_workers(thread("root", None), [
            thread("lead", "root", model="gpt-5.6-terra", agentRole="lead"),
        ])
        store.save("team-one", "root", workers)
        loaded = store.load("team-one")
        self.assertEqual(loaded["rootThreadId"], "root")
        self.assertEqual(loaded["workers"][0]["threadId"], "lead")
        self.assertIsNone(store.load("team-two"))
        files = list((self.root / "workers").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(os.stat(files[0]).st_mode & 0o777, 0o600)
        raw = files[0].read_text()
        self.assertNotIn("prompt", raw)
        self.assertNotIn("preview", raw)
        self.assertNotIn("cwd", raw)

    def test_tampered_snapshot_with_unknown_content_is_rejected(self):
        store = WorkerStore(self.root)
        store.save("team-one", "root", descendant_workers(
            thread("root", None), [thread("lead", "root")],
        ))
        path = next((self.root / "workers").glob("*.json"))
        value = json.loads(path.read_text())
        value["workers"][0]["preview"] = "private transcript"
        path.write_text(json.dumps(value))
        self.assertIsNone(store.load("team-one"))


if __name__ == "__main__":
    unittest.main()
