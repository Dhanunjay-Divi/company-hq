import subprocess
import unittest
from unittest.mock import patch

from access_settings import open_settings


class AccessSettingsTest(unittest.TestCase):
    def test_only_fixed_links_open_and_never_claim_permission(self):
        for pane, suffix in [('accessibility', 'Privacy_Accessibility'), ('screen-recording', 'Privacy_ScreenCapture')]:
            with patch('access_settings.sys.platform', 'darwin'), patch('access_settings.subprocess.run') as run:
                result = open_settings({'pane': pane})
            self.assertEqual(run.call_args.args[0], ['/usr/bin/open', 'x-apple.systempreferences:com.apple.preference.security?' + suffix])
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertTrue(result['opened'])
            self.assertFalse(result['permissionGranted'])

    def test_invalid_input_and_unsupported_os_never_launch(self):
        with patch('access_settings.subprocess.run') as run:
            for body in (None, [], {}, {'pane': []}, {'pane': 'https://bad'}, {'pane': 'accessibility', 'command': 'bad'}):
                with self.assertRaises(ValueError): open_settings(body)
            with patch('access_settings.sys.platform', 'linux'), self.assertRaises(ValueError):
                open_settings({'pane': 'accessibility'})
            run.assert_not_called()

    def test_errors_are_sanitized(self):
        with patch('access_settings.sys.platform', 'darwin'), patch('access_settings.subprocess.run', side_effect=subprocess.TimeoutExpired('private', 10)):
            with self.assertRaisesRegex(ValueError, 'could not be opened') as error:
                open_settings({'pane': 'accessibility'})
            self.assertNotIn('private', str(error.exception))
