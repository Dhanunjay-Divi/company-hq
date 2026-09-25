"""User-triggered, fixed macOS settings links; does not grant permissions."""
import subprocess
import sys

PANES = {
    'accessibility': 'Privacy_Accessibility',
    'screen-recording': 'Privacy_ScreenCapture',
    'dictation': None,
}


def open_settings(body):
    if not isinstance(body, dict) or set(body) != {'pane'} or not isinstance(body['pane'], str) or body['pane'] not in PANES:
        raise ValueError('Choose Accessibility or Screen Recording settings.')
    if sys.platform != 'darwin':
        raise ValueError('Use your operating system settings to manage computer access.')
    try:
        pane = PANES[body['pane']]
        url = ('x-apple.systempreferences:com.apple.Keyboard-Settings.extension'
               if pane is None else 'x-apple.systempreferences:com.apple.preference.security?' + pane)
        subprocess.run(['/usr/bin/open', url],
                       check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        raise ValueError('System settings could not be opened. Open System Settings manually.') from None
    return {'opened': True, 'pane': body['pane'], 'permissionGranted': False,
            'message': 'Settings opened. Choose which app to allow there; HQ has not granted access.'}
