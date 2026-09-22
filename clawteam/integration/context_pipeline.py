"""Private, bounded command-evidence recall with optional local enrichers.

The caller owns command execution.  This module only records an already captured result.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib, json, os, re, subprocess, tempfile, threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_BYTES = 4 * 1024 * 1024
DEFAULT_LIMIT = 50
MAX_RECORDS = 500
MAX_COMPACT_BYTES = 16 * 1024
RAW_PAGE_BYTES = 64 * 1024
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def _safe_component(value: str) -> str:
    return _digest(value)[:32]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def _locked(folder: Path):
    """Serialize evidence mutation and reads across threads and HQ processes."""
    with _locks_guard:
        mutex = _locks.setdefault(str(folder), threading.RLock())
    lock_path = folder / '.evidence.lock'
    with mutex, lock_path.open('a+b') as file:
        if os.name == 'nt':
            import msvcrt
            if file.tell() == 0: file.write(b'0'); file.flush()
            file.seek(0); msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                file.seek(0); msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)

def _private_env(folder: Path) -> dict[str, str]:
    env = {**os.environ, 'RTK_TELEMETRY_DISABLED': '1', 'RTK_DB_PATH': str(folder / 'rtk-db'),
           'RTK_RECALL': '0', 'RTK_TEE': '0'}
    for key in tuple(env):
        upper = key.upper()
        if upper.endswith(('_API_KEY', '_TOKEN', '_SECRET')) or upper in {
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY'
        }:
            env.pop(key, None)
    return env

@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    captured_at: str
    command: list[str]
    exit_code: int | None
    raw_bytes: int
    raw_truncated: bool
    original_raw_bytes: int
    compact_bytes: int | None
    compact: str | None
    raw_sha256: str
    rtk: str

class ContextPipeline:
    """State is external to the checkout and segmented by team and bound project."""
    def __init__(self, state_root: Path | str, *, rtk_path: Path | str | None = None,
                 graphify_python: Path | str | None = None) -> None:
        self.root = Path(state_root).expanduser().resolve() / 'context-evidence'
        self.rtk_path = Path(rtk_path).expanduser().absolute() if rtk_path else None
        self.graphify_python = Path(graphify_python).expanduser().absolute() if graphify_python else None

    def _dir(self, team_id: str, project_path: Path | str) -> Path:
        # Do not create or inspect the project; its textual binding is only hashed.
        path = self.root / _safe_component(team_id) / _safe_component(str(project_path))
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try: path.chmod(0o700)
        except OSError: pass
        return path

    @staticmethod
    def _raw(captured: dict[str, Any]) -> str:
        stdout, stderr = str(captured.get('stdout', '')), str(captured.get('stderr', ''))
        return stdout + ('' if not stdout or not stderr else '\n') + stderr

    @staticmethod
    def _filter_name(command: list[str]) -> str:
        joined = ' '.join(command).lower()
        if 'pytest' in joined: return 'pytest'
        if 'cargo test' in joined or 'cargo-test' in joined: return 'cargo-test'
        if 'npm test' in joined: return 'npm-test'
        return 'command-output'

    @staticmethod
    def _markers(raw: str, exit_code: int | None) -> list[str]:
        if exit_code in (None, 0): return []
        # Error lines and common test/file locations are required to remain discoverable.
        return [line for line in raw.splitlines() if re.search(r'(error|failed|failure|assert|exception|traceback|\.py:\d+|\.rs:\d+)', line, re.I)][:24]

    @staticmethod
    def _tail_bytes(value: str, maximum: int) -> tuple[str, bool]:
        data = value.encode('utf-8')
        if len(data) <= maximum: return value, False
        # Decode after cutting bytes so metadata is a genuine byte bound.
        tail = data[-maximum:]
        while tail and tail[0] & 0xC0 == 0x80: tail = tail[1:]
        return tail.decode('utf-8'), True

    def _compact(self, raw: str, command: list[str], exit_code: int | None, folder: Path) -> tuple[str | None, str]:
        if not self.rtk_path or not self.rtk_path.is_file(): return None, 'unavailable'
        try:
            completed = subprocess.run([str(self.rtk_path), 'pipe', '--filter', self._filter_name(command)],
                input=raw, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=_private_env(folder), timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired): return None, 'unavailable'
        compact = completed.stdout if completed.returncode == 0 else ''
        if not compact or any(marker not in compact for marker in self._markers(raw, exit_code)):
            return None, 'raw_fallback'
        return compact, 'filtered'

    def record(self, team_id: str, project_path: Path | str, captured: dict[str, Any]) -> EvidenceRecord:
        command = [str(x) for x in captured.get('command', [])]
        original_raw = self._raw(captured)
        original_raw_bytes = len(original_raw.encode())
        # Bounded private store; keep the tail because it normally includes final failure summaries.
        raw, raw_truncated = self._tail_bytes(original_raw, MAX_BYTES)
        folder = self._dir(team_id, project_path)
        record_id = _digest(_now() + raw + json.dumps(command))[:24]
        raw_path = folder / f'{record_id}.raw'
        with _locked(folder):
            fd, temp_raw = tempfile.mkstemp(prefix='.raw-', dir=folder)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as file:
                    file.write(raw); file.flush(); os.fsync(file.fileno())
                Path(temp_raw).chmod(0o600); os.replace(temp_raw, raw_path)
            finally:
                Path(temp_raw).unlink(missing_ok=True)
            compact, rtk = self._compact(raw, command, captured.get('exit_code', captured.get('returncode')), folder)
            if compact is not None:
                compact, _ = self._tail_bytes(compact, MAX_COMPACT_BYTES)
            record = EvidenceRecord(record_id, _now(), command, captured.get('exit_code', captured.get('returncode')),
                len(raw.encode()), raw_truncated, original_raw_bytes, len(compact.encode()) if compact is not None else None, compact,
                hashlib.sha256(raw.encode()).hexdigest(), rtk)
            index = folder / 'index.jsonl'
            previous = index.read_text(encoding='utf-8').splitlines() if index.exists() else []
            retained = previous[-(MAX_RECORDS - 1):]
            retained.append(json.dumps(asdict(record), separators=(',', ':')))
            fd, temp_index = tempfile.mkstemp(prefix='.index-', dir=folder)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as file:
                    file.write('\n'.join(retained) + '\n'); file.flush(); os.fsync(file.fileno())
                Path(temp_index).chmod(0o600); os.replace(temp_index, index)
            finally:
                Path(temp_index).unlink(missing_ok=True)
            keep_ids = {json.loads(line).get('id') for line in retained}
            for candidate in folder.glob('*.raw'):
                if candidate.stem not in keep_ids: candidate.unlink(missing_ok=True)
        return record

    def recall(self, team_id: str, project_path: Path | str, *, cursor: int = 0, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        if cursor < 0 or limit < 1 or limit > DEFAULT_LIMIT: raise ValueError('invalid pagination')
        folder = self._dir(team_id, project_path); index = folder / 'index.jsonl'
        with _locked(folder):
            rows = [json.loads(line) for line in index.read_text().splitlines()] if index.exists() else []
        page = rows[cursor:cursor + limit]
        return {'items': page, 'cursor': cursor, 'next_cursor': cursor + len(page) if cursor + len(page) < len(rows) else None}

    def raw(self, team_id: str, project_path: Path | str, record_id: str, *, offset: int = 0, limit: int = RAW_PAGE_BYTES) -> dict[str, Any]:
        if not re.fullmatch(r'[0-9a-f]{24}', record_id) or offset < 0 or not 1 <= limit <= RAW_PAGE_BYTES: raise ValueError('invalid raw page')
        folder = self._dir(team_id, project_path)
        with _locked(folder): value = (folder / f'{record_id}.raw').read_bytes()
        page = value[offset:offset + limit]
        return {'text': page.decode('utf-8', errors='replace'), 'offset': offset, 'next_offset': offset + len(page) if offset + len(page) < len(value) else None, 'total_bytes': len(value)}

    def _graph_env(self, folder: Path) -> dict[str, str]:
        env = _private_env(folder)
        env.update(GRAPHIFY_OUT=str(folder / 'graphify'), GRAPHIFY_TELEMETRY_DISABLED='1')
        return env

    def build_graph(self, project_path: Path | str) -> dict[str, Any]:
        if not self.graphify_python or not self.graphify_python.is_file(): return {'status': 'unavailable'}
        project = Path(project_path).expanduser().resolve(); folder = self._dir('graphify', project)
        result = subprocess.run([str(self.graphify_python), '-m', 'graphify', 'update', str(project), '--no-cluster'], cwd=project,
            env=self._graph_env(folder), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
        return {'status': 'built' if result.returncode == 0 else 'failed', 'exit_code': result.returncode}

    def query_graph(self, project_path: Path | str, query: str, *, broad: bool = False) -> dict[str, Any]:
        if not broad: return {'status': 'deferred', 'reason': 'Codebase Memory MCP remains primary for narrow recall'}
        if not self.graphify_python or not self.graphify_python.is_file(): return {'status': 'unavailable'}
        project = Path(project_path).expanduser().resolve(); folder = self._dir('graphify', project)
        result = subprocess.run([str(self.graphify_python), '-m', 'graphify', 'query', query, '--graph', str(folder / 'graphify' / 'graph.json')], cwd=project,
            env=self._graph_env(folder), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        return {'status': 'ok' if result.returncode == 0 else 'failed', 'exit_code': result.returncode, 'text': result.stdout[:65536]}
