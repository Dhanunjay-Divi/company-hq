from __future__ import annotations

import plistlib
from pathlib import Path
import tempfile
import unittest

import provider_registry as registry


class ProviderRegistryTests(unittest.TestCase):
    def test_inventory_detects_cli_override_and_exact_verified_desktop_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = root / 'codex'; cli.write_text('fixture'); cli.chmod(0o700)
            app = root / 'Claude.app' / 'Contents'; app.mkdir(parents=True)
            with (app / 'Info.plist').open('wb') as output:
                plistlib.dump({'CFBundleIdentifier': 'com.anthropic.claudefordesktop'}, output)
            value = registry.inventory(
                environ={'COMPANY_HQ_CODEX_PATH': str(cli)}, app_roots=(root,),
                which=lambda _name: None,
            )
        by_id = {provider['id']: provider for provider in value['providers']}
        self.assertEqual(list(by_id), ['codex', 'claude', 'kimi', 'zai', 'cursor', 'grok', 'ollama'])
        self.assertEqual(by_id['codex']['cliPath'], str(cli))
        self.assertTrue(by_id['codex']['runtimeReady'])
        self.assertEqual(by_id['claude']['desktopPath'], str(root / 'Claude.app'))
        self.assertFalse(by_id['claude']['runtimeReady'])
        self.assertEqual(by_id['claude']['authentication'], 'not_checked')

    def test_wrong_bundle_or_non_executable_override_is_not_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / 'Kimi Code.app' / 'Contents'; app.mkdir(parents=True)
            with (app / 'Info.plist').open('wb') as output:
                plistlib.dump({'CFBundleIdentifier': 'wrong.bundle'}, output)
            non_executable = root / 'kimi'; non_executable.write_text('fixture')
            value = registry.inventory(
                environ={'COMPANY_HQ_KIMI_PATH': str(non_executable)}, app_roots=(root,),
                which=lambda _name: None,
            )
        kimi = next(provider for provider in value['providers'] if provider['id'] == 'kimi')
        self.assertFalse(kimi['installed'])
        self.assertIsNone(kimi['cliPath'])
        self.assertIsNone(kimi['desktopPath'])

    def test_glm_cli_is_only_the_zai_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            glm = Path(temporary) / 'glm'; glm.write_text('fixture'); glm.chmod(0o700)
            value = registry.inventory(environ={}, app_roots=(), which=lambda name: str(glm) if name == 'glm' else None)
        zai = next(provider for provider in value['providers'] if provider['id'] == 'zai')
        self.assertEqual(zai['cliPath'], str(glm))
        self.assertFalse(zai['runtimeReady'])


if __name__ == '__main__':
    unittest.main()
