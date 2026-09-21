"""Model-free evidence gates. Byte counts are not model-token or cost savings."""
from __future__ import annotations

import hashlib
import re
import statistics
from pathlib import Path
from typing import Any


def text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value or ''


def snapshot(root: Path) -> dict[str, str]:
    """Include nested additions and symlinks; never follow a link outside root."""
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if relative.parts[0] == '.git':
            continue
        if path.is_symlink():
            result[str(relative)] = 'link:' + str(path.readlink())
        elif path.is_file():
            result[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            result[str(relative) + '/'] = 'directory'
    return result


def changes(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    changed = sorted(p for p in before if p not in after or before[p] != after[p])
    added = sorted(set(after) - set(before))
    return {'source_unchanged': not changed, 'modified_or_deleted': changed,
            'generated_paths': added, 'project_clean': not changed and not added}


def coverage(stdout: str, expected: list[str], *, ok: bool) -> dict[str, Any]:
    """Successful stdout only. This is retrieval coverage, NOT answer accuracy."""
    hits = [s for s in expected if re.search(r'(?<![\w])' + re.escape(s) + r'(?![\w])', stdout)] if ok else []
    return {'matched': hits, 'expected': expected,
            'coverage_complete': bool(expected) and len(hits) == len(expected),
            'stdout_bytes': len(stdout.encode('utf-8')) if ok else None}


def assess(build: dict, queries: list[dict], boundary: dict) -> str:
    if not boundary.get('source_unchanged'):
        return 'source_changed'
    if not build.get('ok'):
        return 'build_failed'
    if not queries or not all(q.get('ok') for q in queries):
        return 'query_failed'
    if not all(q.get('coverage_complete') for q in queries):
        return 'coverage_incomplete'
    if not boundary.get('project_clean'):
        return 'needs_external_state_adapter'
    return 'smoke_passed'


def selection_status(results: dict[str, dict]) -> str:
    """Never issue a green selection gate when any configured test was skipped."""
    if not results or any(r.get('status') == 'not_run' for r in results.values()):
        return 'incomplete'
    if any(r.get('status') == 'source_changed' for r in results.values()):
        return 'blocked_source_mutation'
    if any(r.get('status') == 'smoke_passed' for r in results.values()):
        return 'smoke_candidates_only'
    return 'no_eligible_candidate'


def exit_code(results: dict[str, dict]) -> int:
    return 0 if selection_status(results) == 'smoke_candidates_only' else 1


def reduction(before: int, after: int) -> float | None:
    return round(1 - after / before, 6) if before > 0 else None


def compression_gate(raw: dict, compact: dict, required: list[str], expected_exit: int) -> dict:
    """A shorter error or a lost failure is not a successful compression."""
    a, b = text(raw.get('text')), text(compact.get('text'))
    valid_exit = raw.get('returncode') == compact.get('returncode') == expected_exit
    raw_complete = all(marker in a for marker in required)
    missing = [marker for marker in required if marker not in b]
    passed = valid_exit and raw_complete and not missing and len(b.encode()) < len(a.encode())
    return {'passed': passed, 'exit_preserved': valid_exit, 'raw_evidence_complete': raw_complete,
            'missing_evidence': missing, 'raw_bytes': len(a.encode()),
            'compact_bytes': len(b.encode()),
            'byte_reduction': reduction(len(a.encode()), len(b.encode())) if valid_exit and raw_complete and not missing else None,
            'actual_model_tokens': None, 'billed_savings': None}


def medians(queries: list[dict]) -> dict:
    successful = [q for q in queries if q.get('ok')]
    return {'query_seconds_median': statistics.median(q['seconds'] for q in successful) if successful else None,
            'stdout_bytes_median': statistics.median(q['stdout_bytes'] for q in successful) if successful else None}
