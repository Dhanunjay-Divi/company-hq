"""Recoverable local chat visibility, export, and bound-folder actions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import time
import threading

_STATE_LOCK = threading.RLock()

from transcript_archive import TranscriptArchive

_CHAT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\Z")


class ChatManagement:
    def __init__(self, state: Path):
        self.state = Path(state)
        self.path = self.state / "chat-management.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {"deleted": {}}
        if self.path.is_symlink() or self.path.stat().st_size > 65536:
            raise ValueError("Chat management storage is invalid.")
        value = json.loads(self.path.read_text())
        deleted = value.get("deleted") if isinstance(value, dict) else None
        if not isinstance(deleted, dict):
            raise ValueError("Chat management storage is invalid.")
        return {"deleted": {name: stamp for name, stamp in deleted.items()
                            if isinstance(name, str) and _CHAT.fullmatch(name) and isinstance(stamp, int)}}

    def _write(self, value: dict) -> None:
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.state, prefix=".chat-management-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(value, output, separators=(",", ":"))
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def deleted(self) -> set[str]:
        return set(self._read()["deleted"])

    def delete(self, team: str) -> None:
        self._validate(team)
        with _STATE_LOCK:
            value = self._read()
            value["deleted"][team] = int(time.time())
            self._write(value)

    def restore(self, team: str) -> None:
        self._validate(team)
        with _STATE_LOCK:
            value = self._read()
            value["deleted"].pop(team, None)
            self._write(value)

    def export(self, team: str, kind: str) -> dict:
        self._validate(team)
        if kind not in {"json", "markdown"}:
            raise ValueError("Choose Markdown or JSON export.")
        events = self._all_events(team)
        if kind == "json":
            return {"filename": f"{team}-transcript.json", "mimeType": "application/json", "content": json.dumps(events, indent=2)}
        lines = [f"# {team}", ""]
        for event in events:
            role = "You" if event.get("type") == "message.user" else "Company HQ"
            text = str(event.get("data", {}).get("text", ""))
            lines.extend((f"## {role}", "", text, ""))
        return {"filename": f"{team}-transcript.md", "mimeType": "text/markdown", "content": "\n".join(lines)}

    def _all_events(self, team: str) -> list[dict]:
        archive = TranscriptArchive(self.state / "runtime")
        before = None
        result: list[dict] = []
        while True:
            page = archive.page(team, before=before, limit=100)
            result[0:0] = page["events"]
            before = page["before"]
            if before is None:
                return result

    def save_export(self, team: str, kind: str) -> dict:
        result = self.export(team, kind)
        folder = self.state / 'exports'
        if folder.is_symlink(): raise ValueError('Export folder must not be a symlink.')
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, filename = tempfile.mkstemp(prefix=result['filename'].rsplit('.',1)[0]+'-', suffix='.'+result['filename'].rsplit('.',1)[1], dir=folder)
        with os.fdopen(fd,'w',encoding='utf-8') as output:
            os.fchmod(output.fileno(),0o600)
            output.write(result['content'])
        result['savedPath'] = filename
        result['revealed'] = False
        if platform.system() == 'Darwin':
            try:
                subprocess.run(['/usr/bin/open','-R',filename],check=True,timeout=10,shell=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                result['revealed'] = True
            except (OSError,subprocess.SubprocessError): pass
        return result

    @staticmethod
    def _validate(team: str) -> None:
        if not isinstance(team, str) or not _CHAT.fullmatch(team):
            raise ValueError("Invalid chat.")


def reveal_bound_folder(state: Path, team: str, profile: dict) -> str:
    ChatManagement._validate(team)
    raw = profile.get("projectRoot")
    if not isinstance(raw, str) or not raw:
        raise ValueError("This chat has no bound folder.")
    try:
        folder = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("This chat's bound folder is unavailable.") from exc
    if not folder.is_dir() or folder in {Path("/"), Path.home()}:
        raise ValueError("This chat's bound folder is unavailable.")
    # A private conversation may reveal only its exact managed directory.
    if profile.get("workspaceKind") == "managed":
        root = (Path(state).resolve() / "managed-workspaces").resolve()
        if folder.parent != root or folder.name != team:
            raise ValueError("This chat's managed folder binding is invalid.")
    if platform.system() != "Darwin":
        raise ValueError("Show in Finder is only available on macOS.")
    try:
        subprocess.run(["/usr/bin/open", str(folder)], check=True, timeout=10,
                       shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Finder could not open this chat's bound folder.") from exc
    return str(folder)
