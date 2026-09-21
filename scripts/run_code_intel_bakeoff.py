#!/usr/bin/env python3
"""Credential-free structural smoke tests; not an end-to-end model benchmark.

Use only disposable fixtures. Run under an OS network sandbox in CI. A successful
run identifies smoke-test candidates, never a universally best integration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from bakeoff_evidence import assess, changes, coverage, exit_code, medians, selection_status, snapshot, text

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'benchmarks' / 'code-intel-fixture'
FILES = ('auth/session.py', 'api/reports.py', 'billing/invoice.ts')
CASES = (
    ('authorization', 'authorize_session', ['authorize_session', 'check_permission', 'get_report', 'auth/session.py', 'api/reports.py']),
    ('typescript', 'invoiceTotal', ['invoiceTotal', 'calculateTax', 'renderInvoice', 'billing/invoice.ts']),
)
PINS = {'graphify': 'graphifyy==0.9.65', 'codegraph': '@colbymchenry/codegraph@1.6.0',
        'graft': '@nanonets/graft@0.18.0', 'codebase_memory': 'v0.10.8'}


def environment(base: Path) -> dict[str, str]:
    """Only synthetic candidate processes get an empty HOME. Never alter os.environ."""
    home = base / 'empty-home'; home.mkdir(parents=True, mode=0o700)
    env = {k: os.environ[k] for k in ('PATH', 'LD_LIBRARY_PATH', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(base / 'config'),
               XDG_CACHE_HOME=str(base / 'cache'), XDG_STATE_HOME=str(base / 'state'),
               LANG='C.UTF-8', PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               CODEGRAPH_TELEMETRY='0', DO_NOT_TRACK='1')
    return env


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    proc.wait(timeout=5)


def run(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 60) -> dict:
    start = time.perf_counter()
    try:
        p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=os.name == 'posix')
        try:
            stdout, stderr = p.communicate(timeout=timeout)
            reason = None
        except subprocess.TimeoutExpired:
            stop(p); stdout, stderr = p.communicate()
            reason = 'timeout'
        return {'ok': p.returncode == 0 and reason is None, 'returncode': p.returncode,
                'stdout': text(stdout), 'stderr': text(stderr), 'error': reason,
                'seconds': round(time.perf_counter() - start, 6)}
    except OSError as exc:
        return {'ok': False, 'returncode': None, 'stdout': '', 'stderr': str(exc),
                'error': 'launch_failed', 'seconds': round(time.perf_counter() - start, 6)}


class MCP:
    """One warm MCP session. Drain stderr to disk; never mix it into answers."""
    def __init__(self, exe: str, cwd: Path, env: dict[str, str]):
        self.stderr = tempfile.TemporaryFile()
        self.proc = subprocess.Popen([exe, '--ui=false'], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1, start_new_session=os.name == 'posix')
        self.lines = queue.Queue(); self.sequence = 0
        def read():
            try:
                for line in self.proc.stdout:
                    self.lines.put(line)
            finally:
                self.lines.put(None)
        self.reader = threading.Thread(target=read, daemon=True); self.reader.start()

    def call(self, method: str, params: dict, timeout: int = 60) -> dict:
        self.sequence += 1; ident = self.sequence
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}) + '\n')
        self.proc.stdin.flush(); deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(method)
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(method) from exc
            if line is None:
                raise RuntimeError('MCP closed stdout')
            message = json.loads(line)
            if message.get('id') != ident:
                continue
            if 'error' in message:
                raise RuntimeError(json.dumps(message['error']))
            return message.get('result', {})

    def tool(self, name: str, arguments: dict) -> dict:
        started = time.perf_counter()
        result = self.call('tools/call', {'name': name, 'arguments': arguments}, timeout=120)
        body = '\n'.join(x.get('text', '') for x in result.get('content', []) if x.get('type') == 'text')
        return {'ok': not result.get('isError', False), 'stdout': body, 'stderr': '',
                'seconds': round(time.perf_counter() - started, 6)}

    def close(self) -> str:
        stop(self.proc); self.reader.join(timeout=2)
        self.stderr.seek(0); result = text(self.stderr.read()); self.stderr.close()
        self.proc.stdin.close(); self.proc.stdout.close()
        return result


def evaluate(name: str, base: Path, output: Path, repetitions: int) -> dict:
    variable = 'BAKEOFF_GRAFT_INSTALL' if name == 'graft' else 'BAKEOFF_' + name.upper()
    executable = os.environ.get(variable)
    if not executable:
        return {'status': 'not_run', 'reason': variable + ' is not configured', 'pin': PINS[name]}
    root = base / name; root.mkdir(); project = root / 'project'; project.mkdir()
    for relative in FILES:
        destination = project / relative; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE / relative, destination)
    (project / '.git').mkdir()
    env = environment(root); env['GRAPHIFY_OUT'] = str(root / 'graphify-state')
    env['COMPANY_HQ_GRAFT_INSTALL'] = executable
    env['COMPANY_HQ_GRAFT_STATE_ROOT'] = str(root / 'graft-state')
    env['COMPANY_HQ_STATE_ROOT'] = str(root / 'hq-state')
    for folder in ('cbm-cache', 'cbm-runtime', 'cbm-config'):
        (root / folder).mkdir(mode=0o700)
    env.update(CBM_CACHE_DIR=str(root / 'cbm-cache'), CBM_RUNTIME_DIR=str(root / 'cbm-runtime'),
               XDG_CONFIG_HOME=str(root / 'cbm-config'), CBM_ALLOWED_ROOT=str(project), CBM_LOG_LEVEL='warn')
    before = snapshot(project); queries = []; mcp = None
    build = {'ok': False, 'stdout': '', 'stderr': '', 'seconds': 0}
    diagnostic = ''
    try:
        if name == 'codebase_memory':
            mcp = MCP(executable, root, env)
            mcp.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                'clientInfo': {'name': 'company-hq-evidence', 'version': '2'}})
            mcp.proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); mcp.proc.stdin.flush()
            available = {t['name'] for t in mcp.call('tools/list', {}).get('tools', [])}
            trace = next((n for n in ('trace_call_path', 'trace_path') if n in available), None)
            if trace is None:
                raise RuntimeError('Pinned MCP runtime has no supported call-trace tool')
            build = mcp.tool('index_repository', {'repo_path': str(project), 'name': 'fixture', 'mode': 'full', 'persistence': False})
        elif name == 'graphify':
            build = run([executable, 'extract', str(project)], cwd=project, env=env)
        elif name == 'codegraph':
            build = run([executable, 'init', str(project)], cwd=project, env=env)
        else:
            build = run([sys.executable, str(ROOT / 'graft.py'), 'build', str(project)], cwd=ROOT, env=env)
        if build['ok']:
            for case_id, seed, expected in CASES:
                for attempt in range(repetitions):
                    if mcp:
                        result = mcp.tool(trace, {'project': 'fixture', 'function_name': seed, 'direction': 'both', 'depth': 2})
                        locations = mcp.tool('search_graph', {'project': 'fixture', 'name_pattern': '|'.join(x for x in expected if '/' not in x), 'limit': 20})
                        result['ok'] = result['ok'] and locations['ok']
                        result['stdout'] += '\n' + locations['stdout']
                        result['seconds'] += locations['seconds']
                        result['tool_calls'] = 2
                    elif name == 'graphify':
                        result = run([executable, 'query', seed], cwd=project, env=env)
                    elif name == 'codegraph':
                        result = run([executable, 'explore', seed], cwd=project, env=env)
                    else:
                        result = run([sys.executable, str(ROOT / 'graft.py'), 'query', str(project), seed, '--no-refresh'], cwd=ROOT, env=env)
                    result.update(coverage(result['stdout'], expected, ok=result['ok']))
                    result.update(case=case_id, repetition=attempt + 1)
                    queries.append(result)
    except Exception as exc:
        diagnostic = type(exc).__name__ + ': ' + str(exc)
        if build['ok']:
            queries.append({'ok': False, 'stdout': '', 'stderr': diagnostic, 'coverage_complete': False, 'seconds': 0})
    finally:
        if mcp:
            diagnostic += '\n' + mcp.close()
    boundary = changes(before, snapshot(project))
    record = {'pin': PINS[name], 'status': assess(build, queries, boundary), 'build': build,
              'queries': queries, 'boundary': boundary, 'diagnostic': diagnostic, **medians(queries)}
    payload = json.dumps(record, indent=2).replace(str(base), '<isolated-fixture>')
    (output / (name + '.json')).write_text(payload + '\n', encoding='utf-8')
    return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=3, choices=range(1, 6))
    args = parser.parse_args(); output = args.output_dir.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('output must be outside the source checkout')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hq-code-evidence-') as temporary:
        results = {name: evaluate(name, Path(temporary), output, args.repetitions) for name in PINS}
    report = {'schema': 2, 'claim_scope': 'two synthetic retrieval smoke cases; not correctness, token savings or universal ranking',
              'platform': platform.platform(), 'repetitions': args.repetitions,
              'selection': selection_status(results), 'results': results,
              'actual_model_tokens': None, 'billed_savings': None,
              'source_sha': os.environ.get('BENCHMARK_SOURCE_SHA'),
              'workflow_run': os.environ.get('BENCHMARK_RUN_URL'),
              'fixture_sha256': hashlib.sha256(b''.join(relative.encode() + (FIXTURE / relative).read_bytes() for relative in FILES)).hexdigest() if FIXTURE.exists() else None}
    (output / 'code-intel-results.json').write_text(json.dumps(report, indent=2) + '\n')
    summary = {key: value for key, value in report.items() if key != 'results'}
    summary['results'] = {name: {key: value for key, value in result.items() if key not in {'queries', 'build'}} | {'build_ok': result.get('build', {}).get('ok'), 'build_seconds': result.get('build', {}).get('seconds'), 'build_error': result.get('build', {}).get('stderr', '')[-3000:], 'query_cases': [{key: q.get(key) for key in ('case', 'repetition', 'ok', 'coverage_complete', 'matched', 'stdout_bytes', 'tool_calls')} for q in result.get('queries', [])]} for name, result in results.items()}
    print(json.dumps(summary, indent=2))
    return exit_code(results)

if __name__ == '__main__':
    raise SystemExit(main())
