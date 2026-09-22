from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DesktopPackageTest(unittest.TestCase):
    def test_bundle_config_includes_only_the_frozen_loopback_sidecar(self):
        config = json.loads((ROOT / 'company-hq/src-tauri/tauri.conf.json').read_text())
        self.assertTrue(config['bundle']['active'])
        self.assertIn('resources/backend/company-hq-backend-aarch64-apple-darwin', config['bundle']['resources'])

    def test_launcher_uses_bundled_backend_and_confined_project_paths(self):
        source = (ROOT / 'company-hq/src-tauri/src/lib.rs').read_text()
        self.assertIn('resource_dir()', source)
        self.assertIn('127.0.0.1', source)
        self.assertNotIn('validate_project_file', source)
        self.assertNotIn('open_project_file', source)
        self.assertIn('child.wait()', source)
        self.assertIn('child.stderr.take()', source)
        self.assertIn('Duration::from_secs(45)', source)
        self.assertIn('Command::new("/bin/kill")', source)
        self.assertIn('try_wait()', source)
        self.assertIn('process_group(0)', source)
        self.assertIn('["-KILL", "--", &format!("-{}", child.id())]', source)
        self.assertIn('for _ in 0..300', source)
        self.assertIn('stop_child(&mut process)', source)
        self.assertIn('pick_project_folder', source)
        self.assertNotIn('scripts/hq.py', source)

    def test_build_script_pins_pyinstaller_and_keeps_build_venv_ignored(self):
        source = (ROOT / 'scripts/build_desktop.py').read_text()
        self.assertIn('PyInstaller==6.16.0', source)
        self.assertIn('--onefile', source)
        self.assertIn('company-hq/dist', source)
        ignored = (ROOT / '.gitignore').read_text()
        self.assertIn('.desktop-build-venv/', ignored)


if __name__ == '__main__':
    unittest.main()
