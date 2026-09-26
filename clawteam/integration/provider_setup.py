"""Explicit, bounded local setup for the official Claude Code runtime."""
from __future__ import annotations

import atexit
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from claude_runtime import claude_binary
from runtime_config import demo_mode


def _homebrew() -> str | None:
    for name in ('/opt/homebrew/bin/brew', '/usr/local/bin/brew'):
        path = Path(name)
        if path.is_file() and os.access(path, os.X_OK):
            return name
    return None


class ClaudeSetup:
    def __init__(self):
        self.lock = threading.RLock()
        self.process: subprocess.Popen | None = None
        self.closed = False
        self.state = 'idle'
        self.message = ''

    def snapshot(self):
        with self.lock:
            return {
                'state': self.state,
                'message': self.message,
                'canAutoInstall': sys.platform == 'darwin' and bool(_homebrew()) and not demo_mode(),
                'installCommand': 'brew install --cask claude-code',
            }

    def start(self, approved: bool):
        if approved is not True:
            raise ValueError('Approve the displayed Claude Code install command first.')
        if demo_mode() or sys.platform != 'darwin':
            raise ValueError('In-app installation is available only in the macOS desktop app.')
        if claude_binary():
            raise ValueError('Claude Code is already installed. Check connection instead.')
        brew = _homebrew()
        if not brew:
            raise ValueError('Homebrew is not installed. Use the official Terminal install command shown in HQ.')
        with self.lock:
            if self.closed:
                raise ValueError('Restart Company HQ before installing Claude Code.')
            if self.state == 'installing':
                return self.snapshot()
            self.state = 'installing'
            self.message = 'Installing Claude Code with Homebrew. HQ will check when it finishes.'
            threading.Thread(target=self._install, args=(brew,), daemon=True).start()
            return self.snapshot()

    def _install(self, brew: str):
        process = None
        try:
            with self.lock:
                if self.closed:
                    self.state = 'failed'
                    self.message = 'Company HQ closed before installation could start.'
                    return
                process = subprocess.Popen([brew, 'install', '--cask', 'claude-code'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True)
                self.process = process
            try:
                code = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
                code = -1
            ready = code == 0 and bool(claude_binary())
            with self.lock:
                self.state = 'installed' if ready else 'failed'
                self.message = ('Claude Code is installed. Sign in with Claude, then check connection.' if ready else
                    'Installation did not finish. Run the displayed command in Terminal to see Homebrew’s details.')
        except (OSError, subprocess.TimeoutExpired):
            with self.lock:
                self.state = 'failed'
                self.message = 'Installation could not finish. Run the displayed command in Terminal to see the error.'
        finally:
            with self.lock:
                if self.process is process:
                    self.process = None

    def close(self):
        with self.lock:
            self.closed = True
            process = self.process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass


_setup = ClaudeSetup()
atexit.register(_setup.close)


def setup() -> ClaudeSetup:
    return _setup
