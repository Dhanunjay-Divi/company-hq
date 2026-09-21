"""User-triggered, fixed macOS settings links; does not grant permissions."""
import subprocess
import sys

PANES = {
    'accessibility': 'Privacy_Accessibility',
    'screen-recording': 'Privacy_ScreenCapture',
}


def open_settings(body):
    if not isinstance(body, dict) or set(body) != {'pane'} or not isinstance(body['pane'], str) or body['pane'] not in PANES:
        raise ValueError('Choose Accessibility or Screen Recording settings.')
    if sys.platform != 'darwin':
        raise ValueError('Use your operating system settings to manage computer access.')
    try:
        subprocess.run(['/usr/bin/open', 'x-apple.systempreferences:com.apple.preference.security?' + PANES[body['pane']]],
                       check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        raise ValueError('System settings could not be opened. Open Privacy & Security manually.') from None
    return {'opened': True, 'pane': body['pane'], 'permissionGranted': False,
            'message': 'Settings opened. Choose which app to allow there; HQ has not granted access.'}
