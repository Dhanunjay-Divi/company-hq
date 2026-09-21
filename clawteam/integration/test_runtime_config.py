from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_config as config


class RuntimeConfigTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
