import contextlib
import concurrent.futures
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tomllib
import unittest
from unittest import mock

import configure_codex as c


class ConfigureCodexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex = self.root / "codex"
        self.tool = self.root / "teamboard"
        self.codex.mkdir()
        self.globals = mock.patch.multiple(c, CODEX_DIR=self.codex, BASE=self.tool)
        self.globals.start()
        self.addCleanup(self.globals.stop)

    def apply(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            c.apply()
        return json.loads(output.getvalue())

    def test_preserves_unrelated_settings_and_second_apply_is_idempotent(self):
        config = self.codex / "config.toml"
        config.write_text(
            '# owner comment\n'
            'model = "old-model"\n'
            'approval_policy = "never"\n\n'
            '[agents]\n'
            'custom_setting = "keep-me"\n\n'
            '[features]\n'
            'experimental = true\n'
        )
        os.chmod(config, 0o640)

        first = self.apply()
        installed = config.read_bytes()
        parsed = tomllib.loads(installed.decode())
        self.assertEqual(parsed["approval_policy"], "never")
        self.assertEqual(parsed["agents"]["custom_setting"], "keep-me")
        self.assertTrue(parsed["features"]["experimental"])
        self.assertIn(b"# owner comment", installed)
        self.assertEqual(config.stat().st_mode & 0o777, 0o640)
        self.assertIsNotNone(first["config_backup"])

        second = self.apply()
        self.assertEqual(config.read_bytes(), installed)
        self.assertIsNone(second["config_backup"])
        self.assertEqual(len(list((self.tool / "backups").glob("*/config.toml"))), 1)

    def test_refuses_config_symlink_without_changing_target(self):
        target = self.root / "shared-config.toml"
        original = b'model = "externally-managed"\n'
        target.write_bytes(original)
        config = self.codex / "config.toml"
        config.symlink_to(target)

        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.apply()

        self.assertTrue(config.is_symlink())
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.codex / "agents").exists())

    def test_conflicting_existing_role_aborts_before_config_write(self):
        config = self.codex / "config.toml"
        original = b'model = "original"\n'
        config.write_bytes(original)
        roles = self.codex / "agents"
        roles.mkdir()
        (roles / "team-scout.toml").write_text('name = "owner-role"\n')

        with self.assertRaisesRegex(RuntimeError, "Existing custom role differs"):
            self.apply()

        self.assertEqual(config.read_bytes(), original)
        self.assertEqual((roles / "team-scout.toml").read_text(), 'name = "owner-role"\n')
        self.assertFalse((self.tool / "backups").exists())

    def test_concurrent_installer_calls_serialize_on_advisory_lock(self):
        config = self.codex / "config.toml"
        config.write_text('model = "original"\n')
        original_apply_locked = c.apply_locked
        guard = threading.Lock()
        active = 0
        maximum_active = 0

        def tracked_apply_locked():
            nonlocal active, maximum_active
            with guard:
                active += 1
                maximum_active = max(maximum_active, active)
            try:
                time.sleep(0.03)
                return original_apply_locked()
            finally:
                with guard:
                    active -= 1

        with mock.patch.object(c, "apply_locked", tracked_apply_locked), \
                mock.patch("builtins.print"):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(c.apply) for _ in range(2)]
                for future in futures:
                    future.result()

        self.assertEqual(maximum_active, 1)
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed["model"], "gpt-6-astra")
        self.assertEqual(parsed["model_reasoning_effort"], "high")
        self.assertEqual(parsed["agents"]["default_subagent_model"], "gpt-5.6-terra")
        self.assertEqual(len(list((self.tool / "backups").glob("*/config.toml"))), 1)
        self.assertEqual(len(list((self.codex / "agents").glob("team-*.toml"))), 3)


if __name__ == "__main__":
    unittest.main()
