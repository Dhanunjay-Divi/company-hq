#!/usr/bin/env python3
"""Compare output reducers on the same synthetic evidence, without model calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from bakeoff_evidence import compression_gate, text
from run_code_intel_bakeoff import environment, run

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = 'LEDGER_MISMATCH_SENTINEL'


def headroom_worker(input_file: Path, output_file: Path) -> int:
    from headroom import compress
    raw = input_file.read_text(encoding='utf-8')
    result = compress([{'role': 'tool', 'content': raw}], model='gpt-4o',
                      compress_user_messages=True, protect_recent=0, kompress_model='disabled')
    value = '\n'.join(str(m.get('content', '')) for m in result.messages)
    output_file.write_text(json.dumps({'text': value, 'token_estimate_before': result.tokens_before,
        'token_estimate_after': result.tokens_after, 'transforms': result.transforms_applied}, default=str))
    return 0


def fixtures(root: Path):
    normal = root / 'normal'; normal.mkdir()
    source = 'import pytest\n@pytest.mark.parametrize("i", range(200))\ndef test_many_pass(i):\n    assert i >= 0\n'
    (normal / 'test_pass.py').write_text(source)
    (normal / 'test_failure.py').write_text(source + '\ndef test_ledger_failure():\n    raise AssertionError("' + SENTINEL + '")\n')
    invalid = root / 'invalid'; invalid.mkdir()
    (invalid / 'test_invalid.py').write_text('def test_invalid(:\n    pass\n')
    return [
        ('passing_tests', normal, 'test_pass.py', 0, ['200 passed']),
        ('failing_test', normal, 'test_failure.py', 1, [SENTINEL, 'test_ledger_failure', 'test_failure.py', '1 failed']),
        ('collection_error', invalid, 'test_invalid.py', 2, ['SyntaxError', 'test_invalid.py']),
    ]


def capture(command, cwd, env):
    result = run(command, cwd=cwd, env=env, timeout=90)
    result['text'] = text(result.pop('stdout')) + text(result.pop('stderr'))
    return result


def evaluate(root: Path, output: Path) -> dict:
    pytest_python = os.environ.get('BAKEOFF_TEST_PYTHON')
    rtk = os.environ.get('BAKEOFF_RTK')
    headroom = os.environ.get('BAKEOFF_HEADROOM_PYTHON')
    if not pytest_python:
        return {'status': 'incomplete', 'reason': 'BAKEOFF_TEST_PYTHON not configured', 'cases': []}
    env = environment(root)
    env.update(PATH=str(Path(pytest_python).parent) + os.pathsep + env.get('PATH', ''),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', NO_COLOR='1', HF_HUB_OFFLINE='1',
               TRANSFORMERS_OFFLINE='1', TIKTOKEN_CACHE_DIR=os.environ.get('BAKEOFF_TOKEN_CACHE', str(root / 'token-cache')))
    records = []
    for name, cwd, file, expected_exit, required in fixtures(root):
        args = ['-vv', '-p', 'no:cacheprovider', file]
        raw = capture([pytest_python, '-m', 'pytest', *args], cwd, env)
        item = {'case': name, 'required_evidence': required, 'raw': raw}
        if rtk:
            compact = capture([rtk, 'pytest', *args], cwd, env)
            item['rtk'] = {'status': 'tested', 'result': compact,
                           'gate': compression_gate(raw, compact, required, expected_exit)}
        else:
            item['rtk'] = {'status': 'not_run'}
        if headroom:
            input_path = root / (name + '-input.txt'); input_path.write_text(raw['text'])
            output_path = root / (name + '-compressed.json')
            invocation = capture([headroom, str(Path(__file__).resolve()), '--headroom-worker',
                                  str(input_path), '--worker-output', str(output_path)], root, env)
            if invocation['ok'] and output_path.exists():
                payload = json.loads(output_path.read_text())
                # Compression does not execute pytest; preserve the original process result as metadata.
                compact = {'text': payload['text'], 'returncode': raw['returncode']}
                item['headroom'] = {'status': 'tested', 'result': payload,
                    'gate': compression_gate(raw, compact, required, expected_exit),
                    'exit_source': 'original process metadata, not generated text'}
            else:
                item['headroom'] = {'status': 'execution_failed', 'diagnostic': invocation}
        else:
            item['headroom'] = {'status': 'not_run'}
        records.append(item)
    status = 'tested'
    if any(c[n]['status'] != 'tested' for c in records for n in ('rtk', 'headroom')):
        status = 'incomplete'
    approved = [name for name in ('rtk', 'headroom') if all(c[name].get('gate', {}).get('passed') for c in records)]
    report = {'schema': 2, 'status': status, 'passes_all_fixture_gates': approved, 'cases': records,
        'pins': {'rtk': '0.49.0', 'headroom': '0.37.0', 'pytest': '8.4.2'},
        'scope': 'three identical pytest outputs per reducer; not end-to-end agent quality or billed tokens',
        'actual_model_tokens': None, 'billed_savings': None,
        'source_sha': os.environ.get('BENCHMARK_SOURCE_SHA'), 'workflow_run': os.environ.get('BENCHMARK_RUN_URL')}
    payload = json.dumps(report, indent=2).replace(str(root), '<synthetic-fixture>')
    (output / 'token-evidence.json').write_text(payload + '\n')
    return json.loads(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--headroom-worker', type=Path)
    parser.add_argument('--worker-output', type=Path)
    args = parser.parse_args()
    if args.headroom_worker:
        if not args.worker_output:
            parser.error('--worker-output is required')
        return headroom_worker(args.headroom_worker, args.worker_output)
    if not args.output_dir:
        parser.error('--output-dir is required')
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error('output must be outside source checkout')
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hq-reducer-evidence-') as temp:
        result = evaluate(Path(temp), out)
    summary = {key: val for key, val in result.items() if key != 'cases'}
    summary['cases'] = [{key: value for key, value in case.items() if key not in ('raw', 'rtk', 'headroom')} |
        {name: {key: value for key, value in case[name].items() if key != 'result'} for name in ('rtk', 'headroom')}
        for case in result['cases']]
    print(json.dumps(summary, indent=2))
    return 0 if result['status'] == 'tested' and result['passes_all_fixture_gates'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
