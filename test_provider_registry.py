from __future__ import annotations

import plistlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
        self.assertEqual(by_id['codex']['cliPath'], str(cli.resolve()))
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
        self.assertEqual(zai['cliPath'], str(glm.resolve()))
        self.assertFalse(zai['runtimeReady'])

    def test_bounded_standard_and_provider_specific_cli_locations_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            targets = {
                home / '.local' / 'bin' / 'codex': 'codex',
                home / '.cargo' / 'bin' / 'claude': 'claude',
                home / '.claude' / 'local' / 'claude': 'claude',
                home / '.local' / 'share' / 'uv' / 'tools' / 'kimi-cli' / 'bin' / 'kimi': 'kimi',
            }
            for path in targets:
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture'); path.chmod(0o700)
            value = registry.inventory(environ={}, app_roots=(), which=lambda _name: None, home=home)
        by_id = {provider['id']: provider for provider in value['providers']}
        self.assertEqual(by_id['codex']['cliPath'], str((home / '.local' / 'bin' / 'codex').resolve()))
        self.assertEqual(by_id['claude']['cliPath'], str((home / '.cargo' / 'bin' / 'claude').resolve()))
        self.assertEqual(by_id['kimi']['cliPath'], str((home / '.local' / 'share' / 'uv' / 'tools' / 'kimi-cli' / 'bin' / 'kimi').resolve()))

    def test_known_chatgpt_resources_codex_cli_is_allowed_without_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_cli = Path(temporary) / 'ChatGPT.app' / 'Contents' / 'Resources' / 'codex'
            resource_cli.parent.mkdir(parents=True); resource_cli.write_text('fixture'); resource_cli.chmod(0o700)
            with mock.patch.object(registry, '_CODEX_RESOURCE_CLI', resource_cli):
                value = registry.inventory(environ={}, app_roots=(), which=lambda _name: None, home=Path(temporary))
        codex = next(provider for provider in value['providers'] if provider['id'] == 'codex')
        self.assertEqual(codex['cliPath'], str(resource_cli.resolve()))
        self.assertTrue(codex['runtimeReady'])

    def test_desktop_launcher_override_or_path_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / 'Claude.app' / 'Contents' / 'MacOS' / 'Claude'
            launcher.parent.mkdir(parents=True); launcher.write_text('fixture'); launcher.chmod(0o700)
            link = root / 'claude'; link.symlink_to(launcher)
            override = registry.inventory(environ={'COMPANY_HQ_CLAUDE_PATH': str(launcher)}, app_roots=(), which=lambda _name: None, home=root)
            from_path = registry.inventory(environ={}, app_roots=(), which=lambda name: str(link) if name == 'claude' else None, home=root)
        self.assertIsNone(next(provider for provider in override['providers'] if provider['id'] == 'claude')['cliPath'])
        self.assertIsNone(next(provider for provider in from_path['providers'] if provider['id'] == 'claude')['cliPath'])

    def test_chrome_apps_root_and_cursor_generic_agent_are_not_misclassified(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            app = home / 'Applications' / 'Chrome Apps.localized' / 'Kimi Code.app' / 'Contents'
            app.mkdir(parents=True)
            with (app / 'Info.plist').open('wb') as output:
                plistlib.dump({'CFBundleIdentifier': 'com.kimi.code.desktop'}, output)
            value = registry.inventory(
                environ={}, app_roots=(home / 'Applications' / 'Chrome Apps.localized',),
                which=lambda name: '/not-a-real-agent' if name == 'agent' else None, home=home,
            )
        by_id = {provider['id']: provider for provider in value['providers']}
        self.assertEqual(by_id['kimi']['desktopPath'], str(home / 'Applications' / 'Chrome Apps.localized' / 'Kimi Code.app'))
        self.assertIsNone(by_id['cursor']['cliPath'])


if __name__ == '__main__':
    unittest.main()
