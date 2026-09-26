import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from provider_setup import ClaudeSetup


class ClaudeSetupTest(unittest.TestCase):
    def test_install_requires_explicit_approval_and_available_homebrew(self):
        setup = ClaudeSetup()
        with patch('provider_setup.demo_mode', return_value=False), patch.object(sys, 'platform', 'darwin'), patch('provider_setup.claude_binary', return_value=None), patch('provider_setup._homebrew', return_value='/opt/homebrew/bin/brew'), patch('provider_setup.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'Approve'):
                setup.start(False)
            launch.assert_not_called()
        with patch('provider_setup.demo_mode', return_value=False), patch.object(sys, 'platform', 'darwin'), patch('provider_setup.claude_binary', return_value=None), patch('provider_setup._homebrew', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Homebrew'):
                setup.start(True)

    def test_approved_install_uses_fixed_homebrew_command_and_reports_completion(self):
        setup = ClaudeSetup()
        class Process:
            pid = 12345
            def wait(self, timeout=None): return 0
            def poll(self): return 0
        with patch('provider_setup.demo_mode', return_value=False), patch.object(sys, 'platform', 'darwin'), patch('provider_setup._homebrew', return_value='/opt/homebrew/bin/brew'), patch('provider_setup.claude_binary', side_effect=[None, '/opt/homebrew/bin/claude']), patch('provider_setup.subprocess.Popen', return_value=Process()) as launch:
            setup.start(True)
            for _ in range(100):
                if setup.snapshot()['state'] != 'installing': break
                time.sleep(0.01)
        self.assertEqual(setup.snapshot()['state'], 'installed')
        launch.assert_called_once_with(['/opt/homebrew/bin/brew', 'install', '--cask', 'claude-code'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == '__main__': unittest.main()
