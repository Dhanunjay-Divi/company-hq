from __future__ import annotations

import unittest

from native_tasks import list_tasks, read_task


class NativeTasksTest(unittest.TestCase):
    def test_list_uses_exact_bounded_state_db_parameters(self):
        calls = []
        def rpc(method, params):
            calls.append((method, params))
            return {"data": [{"id": "task_1", "name": "  Ship it  ", "cwd": "/repo", "updatedAt": 2,
                              "status": {"type": "notLoaded"}, "source": "cli", "token": "secret"}], "nextCursor": "n"}
        value = list_tasks(rpc, cursor="c", search="find", archived=True, include_agents=True)
        self.assertEqual(calls, [("thread/list", {"limit": 30, "sortKey": "updated_at", "sortDirection": "desc",
            "useStateDbOnly": True, "archived": True, "sourceKinds": ["cli", "vscode", "exec", "appServer", "unknown",
            "subAgent", "subAgentReview", "subAgentCompact", "subAgentThreadSpawn", "subAgentOther"], "cursor": "c", "searchTerm": "find"})])
        self.assertEqual(value, {"provider": "codex", "readOnly": True, "tasks": [{"id": "task_1", "title": "Ship it", "project": "/repo", "updatedAt": 2, "status": "notLoaded", "source": "cli"}], "nextCursor": "n"})

    def test_list_omits_empty_optional_parameters_and_projects_safely(self):
        def rpc(method, params):
            self.assertEqual(method, "thread/list")
            self.assertNotIn("cursor", params)
            self.assertNotIn("searchTerm", params)
            return {"data": [{"id": "valid", "name": "x" * 200, "cwd": "x" * 4097, "updatedAt": True,
                              "status": {"type": []}, "source": "x" * 81}, {"id": "bad id"}], "nextCursor": None}
        value = list_tasks(rpc)
        self.assertEqual(value["tasks"], [{"id": "valid", "title": "x" * 180, "project": None, "updatedAt": None, "status": "unknown", "source": "unknown"}])

    def test_list_rejects_invalid_inputs_and_malformed_provider_data(self):
        for kwargs in ({"cursor": "x" * 2049}, {"search": 2}, {"archived": 1}, {"include_agents": "yes"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                list_tasks(lambda *_: None, **kwargs)
        with self.assertRaises(ValueError):
            list_tasks(lambda *_: {"data": [], "nextCursor": "x" * 2049})
        with self.assertRaises(ValueError):
            list_tasks(lambda *_: {"data": "not-a-list"})

    def test_list_caps_malicious_rows_and_redacts_all_extra_fields(self):
        rows = [{"id": f"t{i}", "name": None, "cwd": None, "updatedAt": 1, "status": {"type": "idle"}, "source": "exec", "rolloutPath": "/secret", "auth": "secret"} for i in range(40)]
        value = list_tasks(lambda *_: {"data": rows})
        self.assertEqual(len(value["tasks"]), 30)
        self.assertEqual(set(value["tasks"][0]), {"id", "title", "project", "updatedAt", "status", "source"})
        self.assertNotIn("secret", repr(value))

    def test_read_uses_metadata_only_and_never_resumes(self):
        calls = []
        def rpc(method, params):
            calls.append((method, params))
            return {"thread": {"id": "thread-1", "name": "Name", "cwd": "/p", "updatedAt": 3.5,
                "status": {"type": "active"}, "source": "appServer", "preview": "a" * 2500,
                "turns": [{"private": "secret"}], "rolloutPath": "/private"}}
        value = read_task(rpc, "thread-1")
        self.assertEqual(calls, [("thread/read", {"threadId": "thread-1", "includeTurns": False})])
        self.assertEqual(value["task"]["summary"], "a" * 2000)
        self.assertNotIn("secret", repr(value))

    def test_read_rejects_bad_ids_and_mismatched_or_malformed_responses(self):
        for thread_id in ("", "bad id", "é", "x" * 101):
            with self.subTest(thread_id=thread_id), self.assertRaises(ValueError):
                read_task(lambda *_: None, thread_id)
        with self.assertRaises(ValueError):
            read_task(lambda *_: {"thread": {"id": "other"}}, "wanted")
        with self.assertRaises(ValueError):
            read_task(lambda *_: None, "wanted")


if __name__ == "__main__":
    unittest.main()
