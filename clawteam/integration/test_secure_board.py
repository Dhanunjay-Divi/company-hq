from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT.parent / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SERVER = ROOT / "secure_board.py"
CLI = ROOT / "clawteam-meta"
TEAM_UI = ROOT / "team-ui"


class SecureBoardIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="clawteam-fixture-")
        self.state = Path(self.temp.name) / "state"
        self.env = os.environ.copy()
        self.env.update({
            "CLAWTEAM_INTEGRATION_TESTING": "1",
            "CLAWTEAM_INTEGRATION_TEST_DATA_DIR": str(self.state),
            "CLAWTEAM_USER": "local",
            "CLAWTEAM_AGENT_NAME": "head",
        })
        self.run_cli("team", "create", "verification-team", "head", "--leader-id", "fixture-head", "--description", "Verification fixture only")
        self.run_cli("team", "add-member", "verification-team", "worker", "--agent-id", "fixture-worker", "--agent-type", "specialist")
        self.server = subprocess.Popen(
            [str(PYTHON), str(SERVER), "--port", "0"],
            cwd=ROOT,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        line = self.server.stdout.readline().strip()
        self.assertTrue(line.startswith("ClawTeam metadata board: http://127.0.0.1:"), line)
        self.base = line.split(": ", 1)[1]
        self.server.stdout.readline()
        self.server.stdout.readline()

    def tearDown(self):
        self.server.terminate()
        try:
            self.server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.wait(timeout=3)
        if self.server.stdout:
            self.server.stdout.close()
        if self.server.stderr:
            self.server.stderr.close()
        self.temp.cleanup()

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [str(PYTHON), str(CLI), *args], cwd=ROOT, env=self.env,
            capture_output=True, text=True, check=check,
        )

    def request(self, path, *, method="GET", payload=None, headers=None):
        body = None if payload is None else json.dumps(payload).encode()
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=request_headers)
        return urllib.request.urlopen(req, timeout=3)

    def test_real_task_inbox_receive_and_ack_flow(self):
        with self.request("/") as response:
            html = response.read().decode()
            self.assertTrue(html.lower().startswith("<!doctype html>"), "Board must serve an HTML document")
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

        with self.assertRaises(urllib.error.HTTPError) as proxy:
            self.request("/api/proxy?url=https://github.com/example/example")
        self.assertEqual(proxy.exception.code, 404)
        proxy.exception.close()

        with self.assertRaises(urllib.error.HTTPError) as bad_host:
            self.request("/api/overview", headers={"Host": "attacker.invalid"})
        self.assertEqual(bad_host.exception.code, 421)
        bad_host.exception.close()

        with self.assertRaises(urllib.error.HTTPError) as no_origin:
            self.request("/api/team/verification-team/task", method="POST", payload={"subject": "Verification fixture task"})
        self.assertEqual(no_origin.exception.code, 403)
        no_origin.exception.close()

        origin = self.base
        with self.request(
            "/api/team/verification-team/task", method="POST",
            payload={"subject": "Verification fixture task", "owner": "worker"},
            headers={"Origin": origin},
        ) as response:
            task_result = json.load(response)
        self.assertEqual(task_result["status"], "ok")
        self.assertFalse(task_result["starts_agent"])
        for payload in [{"subject": ""}, {"subject": "Fixture", "owner": "missing-owner"}]:
            with self.assertRaises(urllib.error.HTTPError) as invalid_task:
                self.request("/api/team/verification-team/task", method="POST", payload=payload,
                             headers={"Origin": origin})
            self.assertEqual(invalid_task.exception.code, 400)
            invalid_task.exception.close()

        with self.request(
            "/api/team/verification-team/message", method="POST",
            payload={"from": "local_head", "to": "local_worker", "content": "Verification fixture: please acknowledge."},
            headers={"Origin": origin},
        ) as response:
            delivery = json.load(response)
        self.assertEqual(delivery["status"], "delivered_to_inbox")
        self.assertFalse(delivery["wakes_agent"])

        received = self.run_cli("inbox", "receive", "verification-team", "--agent", "worker")
        self.assertIn("Verification fixture: please", received.stdout)
        self.assertIn("acknowledge.", received.stdout)
        reply = self.run_cli("inbox", "send", "verification-team", "head", "Verification fixture ACK", "--from", "worker")
        self.assertIn("Message sent", reply.stdout)

        with self.request("/api/team/verification-team") as response:
            snapshot = json.load(response)
        tasks = sum(snapshot["tasks"].values(), [])
        self.assertTrue(any(t["subject"] == "Verification fixture task" for t in tasks))
        contents = [m.get("content") for m in snapshot["messages"]]
        self.assertIn("Verification fixture: please acknowledge.", contents)
        self.assertIn("Verification fixture ACK", contents)
        worker = next(m for m in snapshot["members"] if m["name"] == "worker")
        self.assertEqual(worker["inboxCount"], 0)

        disabled = self.run_cli("spawn", "anything", check=False)
        self.assertEqual(disabled.returncode, 64)
        self.assertIn("command disabled", disabled.stderr)

    def test_user_message_and_project_hierarchy(self):
        from company_profile import profile_path, validate_profile
        profile = {
            "projectLabel": "Verification project", "goal": "Fixture only",
            "members": {
                "head": {"displayName": "Head", "reportsTo": None},
                "worker": {"displayName": "Researcher", "reportsTo": "head", "model": "fixture-model"},
            },
        }
        path = profile_path(self.state, "verification-team")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(validate_profile(profile, {"head", "worker"})))
        with self.request("/api/company/verification-team") as response:
            actual = json.load(response)
        self.assertEqual(actual["members"]["worker"]["reportsTo"], "head")
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request("/api/company/other-project")
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()
        with self.request(
            "/api/team/verification-team/message", method="POST",
            payload={"from": "user", "to": "local_worker", "content": "User fixture: focus on customers."},
            headers={"Origin": self.base},
        ) as response:
            self.assertFalse(json.load(response)["wakes_agent"])
        received = self.run_cli("inbox", "receive", "verification-team", "--agent", "worker")
        self.assertIn("from=user", received.stdout)
        self.assertIn("focus on customers", received.stdout)
        for payload in [[], {"from": "user", "to": "unknown", "content": "No such owner"}]:
            with self.assertRaises(urllib.error.HTTPError) as invalid:
                self.request("/api/team/verification-team/message", method="POST",
                             payload=payload, headers={"Origin": self.base})
            self.assertEqual(invalid.exception.code, 400)
            invalid.exception.close()
        profile["members"]["head"]["reportsTo"] = "worker"
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_profile(profile, {"head", "worker"})
        profile["members"]["head"]["reportsTo"] = "other-project-member"
        with self.assertRaisesRegex(ValueError, "registered"):
            validate_profile(profile, {"head", "worker"})

    def test_workspace_attachment_and_native_offline_status(self):
        folder = self.state.parent / "attached-project"
        folder.mkdir()
        original = folder / "existing.txt"
        original.write_text("Keep this file unchanged")
        with self.request("/api/workspaces",method="POST",payload={
            "label":"Fixture workspace","project":str(folder),"goal":"Verification only"
        },headers={"Origin":self.base}) as response:
            attached=json.load(response)
        self.assertFalse(attached["started"])
        name=attached["team"]
        with self.request("/api/company/"+name) as response:
            profile=json.load(response)
        self.assertEqual(profile["projectRoot"],str(folder.resolve()))
        with self.request("/api/runtime/"+name+"/status") as response:
            native=json.load(response)
        self.assertEqual(native["state"],"offline")
        self.assertFalse(native["connected"])
        self.assertTrue(native["budget"]["enforced"])
        with self.request("/api/budget/"+name,method="POST",payload={
            "limitTokens":5000,"enforced":True
        },headers={"Origin":self.base}) as response:
            budget=json.load(response)["budget"]
        self.assertEqual(budget["limitTokens"],5000)
        with self.request("/api/runtime/"+name+"/status") as response:
            native=json.load(response)
        self.assertEqual(native["budget"]["limitTokens"],5000)
        with self.request("/api/team/"+name+"/task",method="POST",payload={
            "subject":"Fixture task","owner":"overall-head"
        },headers={"Origin":self.base}) as response:
            task=json.load(response)
        with self.request("/api/task/"+name+"/"+task["task_id"],method="POST",payload={
            "status":"completed"
        },headers={"Origin":self.base}) as response:
            self.assertTrue(json.load(response)["updated"])
        self.assertEqual(original.read_text(),"Keep this file unchanged")
        self.assertEqual(list(folder.iterdir()),[original])
        with self.assertRaises(urllib.error.HTTPError) as invalid:
            self.request("/api/workspaces",method="POST",payload={
                "label":"Invalid root","project":"/","goal":"No"
            },headers={"Origin":self.base})
        self.assertEqual(invalid.exception.code,400)
        invalid.exception.close()


class TeamUILifecycleTest(unittest.TestCase):
    def test_start_reuse_status_and_stop_in_fixture_scope(self):
        with tempfile.TemporaryDirectory(prefix="clawteam-ui-fixture-") as temp:
            env = os.environ.copy()
            env.update({
                "CLAWTEAM_INTEGRATION_TESTING": "1",
                "CLAWTEAM_INTEGRATION_TEST_DATA_DIR": str(Path(temp) / "state"),
            })
            def run(command, check=True):
                return subprocess.run(
                    [str(PYTHON), str(TEAM_UI), command], cwd=ROOT, env=env,
                    capture_output=True, text=True, check=check,
                )
            try:
                started = run("start")
                self.assertIn("started: http://127.0.0.1:", started.stdout)
                reused = run("start")
                self.assertIn("already running:", reused.stdout)
                status = run("status")
                self.assertIn("running http://127.0.0.1:", status.stdout)
            finally:
                stopped = run("stop", check=False)
            self.assertEqual(stopped.returncode, 0)
            self.assertIn("Stopped", stopped.stdout)


if __name__ == "__main__":
    unittest.main()
