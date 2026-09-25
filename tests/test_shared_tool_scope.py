"""Project-isolation fixtures for the codebase-memory MCP wrapper and guard."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "clawteam" / "integration"
sys.path.insert(0, str(INTEGRATION))
project_context = types.ModuleType("project_context")
project_context.validate_team = lambda team: team
with patch.dict(sys.modules, {"project_context": project_context}):
    import shared_tools  # noqa: E402


def load_guard():
    spec = importlib.util.spec_from_file_location(
        "codebase_memory_guard", ROOT / "codebase-memory-mcp-0.10.8" / "bin" / "mcp_guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SharedToolScopeTest(unittest.TestCase):
    def test_codebase_memory_state_is_private_per_canonical_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project_a = base / "project-a"
            project_b = base / "project-b"
            project_a.mkdir()
            project_b.mkdir()
            launcher = base / "codebase-memory-mcp-mcp"
            launcher.write_text("#!/bin/sh\n")
            launcher.chmod(0o700)
            with patch.object(shared_tools, "ruflo_launcher", return_value=base / "missing-ruflo"), \
                 patch.object(shared_tools, "codebase_memory_launcher", return_value=launcher), \
                 patch.object(shared_tools, "component_state_root", return_value=base / "cbm-state"), \
                 patch.object(shared_tools, "state_root", return_value=base / "hq-state"), \
                 patch.object(shared_tools, "node_executable", return_value=None):
                first = shared_tools.servers(project_a)
                second = shared_tools.servers(project_b)
            def env(server):
                return {item["name"]: item["value"] for item in server["env"]}
            first_env = env(first[0])
            second_env = env(second[0])
            self.assertEqual(first_env["COMPANY_HQ_CONTEXT_PROJECT"], str(project_a.resolve()))
            self.assertEqual(second_env["COMPANY_HQ_CONTEXT_PROJECT"], str(project_b.resolve()))
            self.assertNotEqual(first_env["COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT"], second_env["COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT"])
            self.assertTrue(first_env["COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT"].startswith(str(base / "cbm-state" / "projects")))

    def test_bound_index_rejects_another_project_and_binds_missing_repo(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            project_a = Path(tmp) / "project-a"
            project_b = Path(tmp) / "project-b"
            project_a.mkdir()
            project_b.mkdir()
            with patch.dict(os.environ, {"COMPANY_HQ_CONTEXT_PROJECT": str(project_a)}, clear=False):
                request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "index_repository", "arguments": {"repo_path": str(project_b)}}}
                forwarded, response = guard.guard_request(request)
                self.assertIsNone(forwarded)
                self.assertTrue(response["result"]["isError"])
                self.assertIn("launch project", response["result"]["content"][0]["text"])

                request = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "index_repository", "arguments": {}}}
                forwarded, response = guard.guard_request(request)
                self.assertIsNone(response)
                self.assertEqual(forwarded["params"]["arguments"]["repo_path"], str(project_a.resolve()))
                self.assertFalse(forwarded["params"]["arguments"]["persistence"])

                request = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_code", "arguments": {"path": str(project_b)}}}
                forwarded, response = guard.guard_request(request)
                self.assertIsNone(forwarded)
                self.assertTrue(response["result"]["isError"])

    def test_long_mac_socket_path_uses_private_scoped_directory(self):
        guard=load_guard()
        with tempfile.TemporaryDirectory() as tmp, patch.object(guard.sys, 'platform', 'darwin'), patch.object(guard, 'Path', side_effect=lambda value: Path(tmp) if value=='/private/tmp' else Path(value)), patch.dict(os.environ, {'CBM_RUNTIME_DIR':'/long-state/'+'a'*90}):
            guard.prepare_runtime_dir()
            first=Path(os.environ['CBM_RUNTIME_DIR'])
            self.assertEqual(first.stat().st_mode & 0o777,0o700)
            os.environ['CBM_RUNTIME_DIR']='/long-state/'+'b'*90
            guard.prepare_runtime_dir()
            self.assertNotEqual(str(first),os.environ['CBM_RUNTIME_DIR'])
            first.parent.chmod(0o755)
            os.environ['CBM_RUNTIME_DIR']='/long-state/'+'c'*90
            with self.assertRaisesRegex(ValueError,'not private'):guard.prepare_runtime_dir()

    def test_unbound_index_keeps_the_external_guard_behavior(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            project = Path(tmp) / "external-project"
            project.mkdir()
            request = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "index_repository", "arguments": {"repo_path": str(project)}}}
            forwarded, response = guard.guard_request(request)
            self.assertIsNone(response)
            self.assertEqual(forwarded["params"]["arguments"]["repo_path"], str(project))
            self.assertFalse(forwarded["params"]["arguments"]["persistence"])
