import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import threading
import unittest
import concurrent.futures


ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "ruflo-memory-mcp.mjs"
PROFILE = ROOT / "sandbox.sb"


class MCPProcess:
    def __init__(self, cwd, state):
        state = state.resolve()
        env = os.environ.copy()
        env.update(
            RUFLO_INTEGRATION_STATE_ROOT=str(state),
            RUFLO_INTEGRATION_TESTING="1",
        )
        command = ["/usr/bin/env", "node", str(SERVER)]
        if Path("/usr/bin/sandbox-exec").exists():
            command = [
                "/usr/bin/sandbox-exec", "-D", f"STATE_ROOT={state}",
                "-f", str(PROFILE), *command,
            ]
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.errors = []
        self.drain = threading.Thread(target=self._drain_errors, daemon=True)
        self.drain.start()
        self.next_id = 1

    def _drain_errors(self):
        for line in self.process.stderr:
            if sum(map(len, self.errors)) < 32_768:
                self.errors.append(line)

    def call(self, method, params=None, timeout=30):
        request_id = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        ready, _, _ = select.select([self.process.stdout], [], [], timeout)
        if not ready:
            self.fail(f"timeout waiting for {method}")
        line = self.process.stdout.readline()
        if not line:
            self.fail(f"server exited during {method}: {''.join(self.errors)}")
        response = json.loads(line)
        if response.get("id") != request_id:
            self.fail(f"unexpected response id: {response}")
        return response

    def fail(self, message):
        self.close()
        raise AssertionError(message)

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
            except (subprocess.TimeoutExpired, BrokenPipeError):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        self.drain.join(timeout=1)
        self.process.stdout.close()
        self.process.stderr.close()


class RufloIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "synthetic-project"
        self.project.mkdir()
        self.state = self.base / "ruflo-state"
        self.state.mkdir()

    def start(self):
        # Simulate a global MCP client whose launch cwd is not the selected project.
        server = MCPProcess(self.base, self.state)
        self.addCleanup(server.close)
        initialized = server.call("initialize", {"protocolVersion": "2024-11-05"})
        self.assertEqual(initialized["result"]["serverInfo"]["ruflo"], "3.41.2")
        return server

    @staticmethod
    def tool_result(response):
        if "error" in response:
            raise AssertionError(response["error"])
        return json.loads(response["result"]["content"][0]["text"])

    def test_allowlist_tasks_memory_and_restart_persistence(self):
        server = self.start()
        listed = server.call("tools/list")["result"]["tools"]
        names = {tool["name"] for tool in listed}
        expected = set(json.loads((ROOT / "allowed-tools.json").read_text())["tools"])
        self.assertEqual(names, expected)
        self.assertFalse(any(name.startswith(("agent_", "swarm_", "terminal_", "managed_agent_")) for name in names))
        self.assertNotIn("memory_search", names)

        denied = server.call("tools/call", {"name": "agent_spawn", "arguments": {}})
        self.assertEqual(denied["error"]["code"], -32601)

        created = self.tool_result(server.call("tools/call", {
            "name": "task_create",
            "arguments": {"project_root": str(self.project), "type": "research", "description": "Synthetic bounded review", "priority": "low"},
        }))
        second = self.start()
        status = self.tool_result(server.call("tools/call", {
            "name": "task_status", "arguments": {"project_root": str(self.project), "taskId": created["taskId"]},
        }))
        self.assertEqual(status["description"], "Synthetic bounded review")
        visible_from_second = self.tool_result(second.call("tools/call", {
            "name": "task_status", "arguments": {"project_root": str(self.project), "taskId": created["taskId"]},
        }))
        self.assertEqual(visible_from_second["description"], "Synthetic bounded review")

        stored = self.tool_result(server.call("tools/call", {
            "name": "memory_store",
            "arguments": {
                "project_root": str(self.project),
                "key": "decision-1",
                "value": "Native Codex executes; Ruflo records project memory.",
                "namespace": "decisions",
                "provenance_type": "tool_result",
            },
        }, timeout=60))
        self.assertTrue(stored["stored"], stored)
        recalled_writer = self.tool_result(server.call("tools/call", {
            "name": "memory_retrieve",
            "arguments": {"project_root": str(self.project), "key": "decision-1", "namespace": "decisions"},
        }, timeout=60))
        self.assertTrue(recalled_writer["found"], {"result": recalled_writer, "stderr": "".join(server.errors)})
        recalled_live = self.tool_result(second.call("tools/call", {
            "name": "memory_retrieve",
            "arguments": {"project_root": str(self.project), "key": "decision-1", "namespace": "decisions"},
        }, timeout=60))
        self.assertTrue(recalled_live["found"], {
            "result": recalled_live,
            "writer_stderr": "".join(server.errors),
            "reader_stderr": "".join(second.errors),
            "state_files": [(str(path.relative_to(self.state)), path.stat().st_size)
                            for path in self.state.rglob("*") if path.is_file()],
        })
        server.close()
        second.close()

        restarted = self.start()
        recalled = self.tool_result(restarted.call("tools/call", {
            "name": "memory_retrieve",
            "arguments": {"project_root": str(self.project), "key": "decision-1", "namespace": "decisions"},
        }, timeout=60))
        self.assertTrue(recalled["found"], recalled)
        self.assertIn("Native Codex executes", recalled["value"])
        self.assertFalse((self.project / ".claude-flow").exists())
        self.assertFalse((self.project / ".swarm").exists())
        self.assertTrue(any(self.state.glob("projects/*/runtime/.claude-flow/tasks/store.json")))
        self.assertTrue(any(self.state.glob("projects/*/memory/memory.db")))

        other = self.base / "other-project"
        other.mkdir()
        wrong_scope = restarted.call("tools/call", {
            "name": "task_list", "arguments": {"project_root": str(other)},
        })
        self.assertEqual(wrong_scope["error"]["code"], -32603)
        self.assertIn("different project", wrong_scope["error"]["message"])

    def test_old_lock_with_live_owner_is_not_evicted(self):
        server = self.start()
        initial = self.tool_result(server.call("tools/call", {
            "name": "task_list", "arguments": {"project_root": str(self.project)},
        }))
        self.assertEqual(initial["total"], 0)
        scope = next(self.state.glob("projects/*"))
        lock = scope / ".write.lock"
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "time": 0, "token": "live-test"}))
        old = 1_000_000_000
        os.utime(lock, (old, old))

        blocked = server.call("tools/call", {
            "name": "task_list", "arguments": {"project_root": str(self.project)},
        }, timeout=10)
        self.assertEqual(blocked["error"]["code"], -32603)
        self.assertIn("lock timed out", blocked["error"]["message"])
        self.assertTrue(lock.exists())
        for child in lock.iterdir():
            child.unlink()
        lock.rmdir()

    def test_two_live_servers_preserve_concurrent_task_and_memory_writes(self):
        first = self.start()
        second = self.start()

        def create(server, suffix):
            task = self.tool_result(server.call("tools/call", {
                "name": "task_create",
                "arguments": {
                    "project_root": str(self.project),
                    "type": "research",
                    "description": f"Concurrent task {suffix}",
                },
            }))
            memory = self.tool_result(server.call("tools/call", {
                "name": "memory_store",
                "arguments": {
                    "project_root": str(self.project),
                    "key": f"concurrent-{suffix}",
                    "value": f"Decision {suffix}",
                    "namespace": "decisions",
                    "provenance_type": "tool_result",
                },
            }, timeout=60))
            return task, memory

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda item: create(*item), [(first, "a"), (second, "b")]))
        self.assertTrue(all(memory["stored"] for _, memory in results), results)

        observer = self.start()
        tasks = self.tool_result(observer.call("tools/call", {
            "name": "task_list", "arguments": {"project_root": str(self.project)},
        }))
        self.assertEqual({task["description"] for task in tasks["tasks"]}, {"Concurrent task a", "Concurrent task b"})
        for suffix in ("a", "b"):
            recalled = self.tool_result(observer.call("tools/call", {
                "name": "memory_retrieve",
                "arguments": {
                    "project_root": str(self.project),
                    "key": f"concurrent-{suffix}",
                    "namespace": "decisions",
                },
            }, timeout=60))
            self.assertEqual(recalled["value"], f"Decision {suffix}")


if __name__ == "__main__":
    unittest.main()
