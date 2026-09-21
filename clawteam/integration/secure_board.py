#!/usr/bin/env python3
"""Loopback-only ClawTeam board for native Codex coordination metadata."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import signal
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from company_profile import load_profile
from runtime_config import clawteam_data_dir, frontend_dist

INTEGRATION_DIR = Path(__file__).resolve().parent


def _configure_environment() -> Path:
    os.umask(0o077)
    data_dir = clawteam_data_dir().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CLAWTEAM_DATA_DIR"] = str(data_dir)
    os.environ["CLAWTEAM_TRANSPORT"] = "file"
    os.environ.pop("CLAWTEAM_REDIS_URL", None)
    return data_dir


DATA_DIR = _configure_environment()

from clawteam.board.collector import BoardCollector  # noqa: E402
from clawteam.board.server import BoardHandler, TeamSnapshotCache  # noqa: E402
from clawteam.events.bus import EventBus  # noqa: E402
from clawteam.events import global_bus  # noqa: E402
from clawteam.team import redis_wakeup  # noqa: E402
from clawteam.team.mailbox import MailboxManager  # noqa: E402
from clawteam.team.manager import TeamManager  # noqa: E402

# Metadata operations must not load user hooks/plugins or contact Redis.
global_bus._bus = EventBus()
global_bus._initialized = True
redis_wakeup.publish_wakeup = lambda *args, **kwargs: False


class SecureBoardHandler(BoardHandler):
    """Preserve the upstream board while enforcing its local trust boundary."""

    static_dir = frontend_dist()
    legacy_static_dir = INTEGRATION_DIR / "static"
    allowed_origins: frozenset[str] = frozenset()
    allowed_hosts: frozenset[str] = frozenset()
    server_version = "ClawTeamMetadataBoard/0.3.0"

    def _trusted_host(self) -> bool:
        return self.headers.get("Host", "").lower() in self.allowed_hosts

    def _reject_untrusted_host(self) -> bool:
        if self._trusted_host():
            return False
        self.send_error(421, "Untrusted Host header")
        return True

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def send_header(self, keyword: str, value: str):
        if keyword.lower() == "access-control-allow-origin":
            return
        super().send_header(keyword, value)

    def _serve_static(self, filename: str, content_type: str):
        root = self.static_dir if (self.static_dir / "index.html").exists() else self.legacy_static_dir
        filepath = (root / filename).resolve()
        if not filepath.is_relative_to(root.resolve()):
            self.send_error(404)
            return
        if not filepath.is_file():
            self.send_error(404, "Static file not found")
            return
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self._reject_untrusted_host():
            return
        path = urlparse(self.path).path
        if path == "/api/proxy" or path.startswith("/api/proxy/"):
            self.send_error(404)
            return
        if path.startswith("/api/company/"):
            team_name = unquote(path[len("/api/company/"):])
            try:
                team = TeamManager.get_team(team_name)
                if team is None:
                    self.send_error(404, "Team not found")
                    return
                self._serve_json(load_profile(DATA_DIR, team_name, {m.name for m in team.members}))
            except (ValueError, OSError) as exc:
                self.send_error(400, str(exc))
            return
        if path == '/api/source':
            archive = INTEGRATION_DIR.parent.parent / 'company-hq' / 'SOURCE.zip'
            if not archive.is_file(): self.send_error(404); return
            content = archive.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="company-hq-source.zip"')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers(); self.wfile.write(content); return
        from hq_api import handle_get
        if handle_get(self, DATA_DIR): return
        if path.startswith('/assets/'):
            self._serve_static(path.lstrip('/'), mimetypes.guess_type(path)[0] or 'application/octet-stream')
            return
        super().do_GET()

    def do_POST(self):
        if self._reject_untrusted_host():
            return
        origin = self.headers.get("Origin", "").lower()
        if origin not in self.allowed_origins:
            self.send_error(403, "Same-origin POST required")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.send_error(415, "application/json required")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        path = urlparse(self.path).path
        max_body = 9 * 1024 * 1024 if path.startswith('/api/attachments/') else 65536
        if length <= 0 or length > max_body:
            self.send_error(413, "Request body exceeds the allowed size")
            return

        path = urlparse(self.path).path
        if path.startswith(('/api/runtime/','/api/knowledge/','/api/workspaces','/api/task/','/api/budget/','/api/providers/','/api/folders/','/api/attachments/')):
            from hq_api import handle_post
            try:
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_error(400, 'Invalid JSON request'); return
            handle_post(self, DATA_DIR, path, payload)
            return
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "team"] and parts[3] == "message":
            self._post_message(unquote(parts[2]), length)
            return
        if len(parts) == 4 and parts[:2] == ["api", "team"] and parts[3] == "task":
            self._post_task(unquote(parts[2]), length)
            return
        self.send_error(404)

    def _json_error(self, status, message):
        body = json.dumps({'error': message}).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _post_task(self, team_name: str, length: int):
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Task must be a JSON object")
            subject, description, owner = (payload.get(k, "") for k in ("subject", "description", "owner"))
            if not all(isinstance(v, str) for v in (subject, description, owner)):
                raise ValueError("Task fields must be text")
            if not subject.strip() or len(subject) > 2000 or len(description) > 12000:
                raise ValueError("A short task title is required; description limit is 12000 characters")
            team = TeamManager.get_team(team_name)
            if team is None:
                raise ValueError("Team not found")
            aliases = {alias: m.name for m in team.members for alias in (m.name, TeamManager.inbox_name_for(m))}
            if owner and owner not in aliases:
                raise ValueError("Choose a registered task owner")
            from clawteam.team.tasks import TaskStore
            task = TaskStore(team_name).create(subject=subject.strip(), description=description, owner=aliases.get(owner, ""))
            self._serve_json({"status": "ok", "task_id": task.id, "starts_agent": False})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.send_error(400, str(exc))

    def _post_message(self, team_name: str, length: int):
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Message must be a JSON object")
            sender = str(payload.get("from", "")).strip()
            recipient = str(payload.get("to", "")).strip()
            content = str(payload.get("content", "")).strip()
            if not sender or not recipient or not content:
                raise ValueError("from, to, and content are required")
            if len(content) > 12000:
                raise ValueError("message exceeds 12000 characters")
            team = TeamManager.get_team(team_name)
            if team is None:
                raise ValueError(f"Team '{team_name}' not found")
            aliases = {m.name for m in team.members}
            aliases.update(TeamManager.inbox_name_for(m) for m in team.members)
            if (sender != "user" and sender not in aliases) or recipient not in aliases:
                raise ValueError("sender must be user or a member; recipient must be a registered member")
            message = MailboxManager(team_name).send(sender, recipient, content)
            self._serve_json({
                "status": "delivered_to_inbox",
                "request_id": message.request_id,
                "wakes_agent": False,
                "note": "Message saved to the agent inbox. The agent reads it at its next checkpoint. To continue immediately, return to this Codex conversation.",
            })
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.send_error(400, str(exc))


def make_server(port: int):
    from http.server import ThreadingHTTPServer

    collector = BoardCollector()
    SecureBoardHandler.collector = collector
    SecureBoardHandler.interval = 2.0
    SecureBoardHandler.team_cache = TeamSnapshotCache(ttl_seconds=2.0)
    server = ThreadingHTTPServer(("127.0.0.1", port), SecureBoardHandler)
    actual_port = server.server_address[1]
    SecureBoardHandler.allowed_hosts = frozenset({
        f"127.0.0.1:{actual_port}", f"localhost:{actual_port}", f"[::1]:{actual_port}"
    })
    SecureBoardHandler.allowed_origins = frozenset({
        f"http://127.0.0.1:{actual_port}", f"http://localhost:{actual_port}"
    })
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Secure local ClawTeam metadata board")
    parser.add_argument("--port", type=int, default=0, help="loopback port; 0 selects an available port")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    server = make_server(args.port)
    host, port = server.server_address
    print(f"ClawTeam metadata board: http://{host}:{port}", flush=True)
    print(f"State: {DATA_DIR}", flush=True)
    print("Inbox delivery is recorded; it does not wake native Codex automatically.", flush=True)
    def terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        from codex_bridge import get_codex_bridge
        get_codex_bridge(DATA_DIR / "runtime").shutdown_all()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
