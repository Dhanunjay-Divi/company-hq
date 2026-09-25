from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_config as config


class RuntimeConfigTest(unittest.TestCase):
    def test_home_based_app_state_keeps_code_memory_external_on_mac(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config.sys,'platform','darwin'), patch.object(Path,'home',return_value=Path(temp)), patch.dict(os.environ,{'COMPANY_HQ_STATE_ROOT':str(Path(temp)/'.local/state/hq-fixture')},clear=True):
            value=config.component_state_root('codebase-memory')
            self.assertTrue(value.is_relative_to(Path('/Users/Shared')))
            self.assertFalse(value.is_relative_to(Path(temp)))
            with patch.dict(os.environ,{'COMPANY_HQ_CODEBASE_MEMORY_STATE_ROOT':str(Path(temp)/'unsafe')}):
                with self.assertRaises(config.ConfigurationError):config.component_state_root('codebase-memory')

    def _make_executable(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        path.chmod(0o700)
        return path

    def _make_ruflo_install(self, root: Path) -> Path:
        launcher = self._make_executable(root / "ruflo-integration" / "ruflo-mcp")
        handler = root / "ruflo-3.41.2" / "node_modules" / "@claude-flow" / "cli" / "dist" / "src" / "mcp-tools" / "memory-tools.js"
        handler.parent.mkdir(parents=True, exist_ok=True)
        handler.touch()
        return launcher

    def _ruflo_health(self, state: Path) -> dict[str, object]:
        with patch.object(config, "node_executable", return_value=self._make_executable(state / "bin" / "node")), patch.object(config, "sandbox_executable", return_value=self._make_executable(state / "bin" / "sandbox-exec")), patch.object(config, "_graft_availability", return_value={"available": False, "path": "", "reason": "test fixture"}):
            return config.health_snapshot(state / "board")["capabilities"]["rufloMemory"]

    def test_explicit_state_root_is_external_and_project_state_is_nested(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-config-") as temp:
            root = Path(temp) / "state"
            with patch.dict(os.environ, {"COMPANY_HQ_STATE_ROOT": str(root)}, clear=False):
                self.assertEqual(config.state_root(), root.resolve())
                self.assertEqual(config.clawteam_data_dir(), root.resolve() / "clawteam")
                self.assertEqual(config.graft_state_root(), root.resolve() / "graft")

    def test_source_checkout_cannot_be_runtime_state(self):
        with patch.dict(os.environ, {"COMPANY_HQ_STATE_ROOT": str(config.REPO_ROOT / "state")}, clear=False):
            with self.assertRaises(config.ConfigurationError):
                config.state_root()

    def test_global_state_root_inside_git_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-git-state-") as temp:
            checkout = Path(temp) / "product"
            (checkout / ".git").mkdir(parents=True)
            requested = checkout / ".company-hq-state"
            with patch.dict(os.environ, {"COMPANY_HQ_STATE_ROOT": str(requested)}, clear=False):
                with self.assertRaises(config.ConfigurationError):
                    config.state_root()

    def test_derived_clawteam_state_rejects_symlink_into_git_checkout(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-clawteam-symlink-") as temp:
            root = Path(temp) / "state"
            product = Path(temp) / "product"
            root.mkdir()
            (product / ".git").mkdir(parents=True)
            (root / "clawteam").symlink_to(product, target_is_directory=True)
            with patch.dict(os.environ, {"COMPANY_HQ_STATE_ROOT": str(root)}, clear=False):
                with self.assertRaises(config.ConfigurationError):
                    config.clawteam_data_dir()

    def test_capabilities_override_rejects_product_checkout(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-capabilities-") as temp:
            product = Path(temp) / "product"
            (product / ".git").mkdir(parents=True)
            target = product / "capabilities.json"
            with patch.dict(os.environ, {"COMPANY_HQ_CAPABILITIES_PATH": str(target)}, clear=False):
                with self.assertRaises(config.ConfigurationError):
                    config.capabilities_path()

    def test_filesystem_root_detection_is_generic(self):
        self.assertTrue(config._is_filesystem_root(Path(Path("/").anchor).resolve()))

    def test_invalid_component_state_is_reported_unavailable(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-health-state-") as temp:
            state = Path(temp) / "state"
            product = Path(temp) / "product"
            state.mkdir()
            (product / ".git").mkdir(parents=True)
            env = {
                "COMPANY_HQ_STATE_ROOT": str(state),
                "COMPANY_HQ_RUFLO_STATE_ROOT": str(product / "ruflo-state"),
            }
            with patch.dict(os.environ, env, clear=False):
                health = config.health_snapshot(Path(temp) / "board")
            self.assertFalse(health["capabilities"]["rufloMemory"]["available"])
            self.assertIn("Git working tree", health["capabilities"]["rufloMemory"]["reason"])

    def test_fixture_override_remains_test_only_and_isolated(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-fixture-") as temp:
            env = {
                "CLAWTEAM_INTEGRATION_TESTING": "1",
                "CLAWTEAM_INTEGRATION_TEST_DATA_DIR": str(Path(temp) / "fixture-state"),
            }
            with patch.dict(os.environ, env, clear=False):
                self.assertEqual(
                    config.clawteam_data_dir(),
                    (Path(temp) / "fixture-state").resolve(),
                )

    def test_demo_disables_model_execution_in_health_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-demo-") as temp:
            env = {"COMPANY_HQ_STATE_ROOT": str(Path(temp) / "state"), "COMPANY_HQ_DEMO": "1"}
            with patch.dict(os.environ, env, clear=False):
                health = config.health_snapshot(Path(temp) / "board")
            self.assertEqual(health["mode"], "demo")
            self.assertFalse(health["modelExecutionEnabled"])
            self.assertTrue(health["accountHomePreserved"])

    def test_health_uses_bundled_ruflo_wrapper_dependency_root(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-ruflo-bundled-") as temp:
            root = Path(temp)
            bundle = root / "bundle"
            launcher = self._make_ruflo_install(bundle)
            with patch.object(config, "REPO_ROOT", bundle), patch.dict(os.environ, {"COMPANY_HQ_STATE_ROOT": str(root / "state")}, clear=True):
                health = self._ruflo_health(root)
            self.assertTrue(health["available"])
            self.assertEqual(Path(health["path"]).resolve(), launcher.resolve())

    def test_health_uses_shared_ruflo_wrapper_dependency_root_when_frozen(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-ruflo-shared-") as temp:
            root = Path(temp)
            shared_root = root / "shared" / "agent-toolkit"
            launcher = self._make_ruflo_install(shared_root)
            env = {
                "COMPANY_HQ_STATE_ROOT": str(root / "state"),
                "XDG_DATA_HOME": str(root / "shared"),
            }
            with patch.object(config, "REPO_ROOT", root / "bundle"), patch.object(config.sys, "frozen", True, create=True), patch.dict(os.environ, env, clear=True):
                health = self._ruflo_health(root)
            self.assertTrue(health["available"])
            self.assertEqual(Path(health["path"]).resolve(), launcher.resolve())

    def test_health_reports_missing_selected_ruflo_dependency(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-ruflo-missing-") as temp:
            root = Path(temp)
            repository = root / "repository"
            self._make_ruflo_install(repository)
            launcher = self._make_executable(root / "selected" / "ruflo-integration" / "ruflo-mcp")
            env = {
                "COMPANY_HQ_STATE_ROOT": str(root / "state"),
                "COMPANY_HQ_RUFLO_LAUNCHER": str(launcher),
            }
            with patch.object(config, "REPO_ROOT", repository), patch.dict(os.environ, env, clear=True):
                health = self._ruflo_health(root)
            self.assertFalse(health["available"])
            self.assertIn(str(root / "selected" / "ruflo-3.41.2"), health["reason"])

    def test_health_honors_explicit_ruflo_and_dependency_overrides(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-ruflo-override-") as temp:
            root = Path(temp)
            launcher = self._make_ruflo_install(root / "override")
            node = self._make_executable(root / "override-node")
            sandbox = self._make_executable(root / "override-sandbox")
            env = {
                "COMPANY_HQ_STATE_ROOT": str(root / "state"),
                "COMPANY_HQ_RUFLO_LAUNCHER": str(launcher),
                "COMPANY_HQ_NODE": str(node),
                "COMPANY_HQ_SANDBOX_EXEC": str(sandbox),
            }
            with patch.object(config, "_graft_availability", return_value={"available": False, "path": "", "reason": "test fixture"}), patch.dict(os.environ, env, clear=True):
                health = config.health_snapshot(root / "board")["capabilities"]["rufloMemory"]
            self.assertTrue(health["available"])
            self.assertEqual(Path(health["path"]).resolve(), launcher.resolve())

    def test_health_rejects_unavailable_ruflo_executables(self):
        with tempfile.TemporaryDirectory(prefix="company-hq-ruflo-executables-") as temp:
            root = Path(temp)
            launcher = self._make_ruflo_install(root)
            node = self._make_executable(root / "node")
            sandbox = self._make_executable(root / "sandbox-exec")
            cases = {
                "launcher": (launcher, node, sandbox),
                "node": (launcher, root / "node-missing", sandbox),
                "sandbox": (launcher, node, root / "sandbox-missing"),
                "node-not-executable": (launcher, root / "node-not-executable", sandbox),
                "sandbox-not-executable": (launcher, node, root / "sandbox-not-executable"),
            }
            for name, (selected, selected_node, selected_sandbox) in cases.items():
                with self.subTest(name=name):
                    if name == "launcher":
                        launcher.chmod(0o600)
                    elif name == "node-not-executable":
                        selected_node.parent.mkdir(parents=True, exist_ok=True)
                        selected_node.touch()
                        selected_node.chmod(0o600)
                    elif name == "sandbox-not-executable":
                        selected_sandbox.parent.mkdir(parents=True, exist_ok=True)
                        selected_sandbox.touch()
                        selected_sandbox.chmod(0o600)
                    env = {
                        "COMPANY_HQ_STATE_ROOT": str(root / "state"),
                        "COMPANY_HQ_RUFLO_LAUNCHER": str(selected),
                        "COMPANY_HQ_NODE": str(selected_node),
                        "COMPANY_HQ_SANDBOX_EXEC": str(selected_sandbox),
                    }
                    with patch.object(config, "_graft_availability", return_value={"available": False, "path": "", "reason": "test fixture"}), patch.dict(os.environ, env, clear=True):
                        health = config.health_snapshot(root / "board")["capabilities"]["rufloMemory"]
                    self.assertFalse(health["available"])
                    if name == "launcher":
                        launcher.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
