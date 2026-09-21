from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_code_intel_bakeoff as runner


class RunnerTests(unittest.TestCase):
    def test_timeout_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as td:
            value = runner.run([sys.executable, '-c', 'import time; print("partial",flush=True); time.sleep(5)'], cwd=Path(td), env=runner.environment(Path(td)), timeout=1)
        self.assertFalse(value['ok']); self.assertEqual(value['error'], 'timeout')
        self.assertIn('partial', value['stdout'])

    def test_environment_does_not_mutate_provider_home(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'UNKNOWN_VENDOR_TOKEN': 'never pass', 'OPENAI_API_KEY': 'never pass', 'CODEX_HOME': '/do-not-copy'}):
            before = dict(os.environ)
            env = runner.environment(Path(td))
            self.assertEqual(dict(os.environ), before)
            self.assertNotIn('UNKNOWN_VENDOR_TOKEN', env)
            self.assertNotIn('CODEX_HOME', env)
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertEqual(env['HOME'], str(Path(td) / 'empty-home'))

    def evaluate_fake(self, mutation=False):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); fixture = base / 'fixture'; fixture.mkdir()
            for relative in runner.FILES:
                file = fixture / relative; file.parent.mkdir(exist_ok=True); file.write_text('original fixture')
            tool = base / 'graphify'
            tool.write_text('#!' + sys.executable + '\nimport os,sys\nfrom pathlib import Path\n'
                + 'assert "OPENAI_API_KEY" not in os.environ\n'
                + ('if sys.argv[1]=="extract": Path("auth/session.py").write_text("changed")\n' if mutation else '')
                + 'if sys.argv[1]=="query": print("authorize_session check_permission get_report auth/session.py api/reports.py invoiceTotal calculateTax renderInvoice billing/invoice.ts")\n')
            tool.chmod(0o700); work = base / 'work'; work.mkdir(); out = base / 'out'; out.mkdir()
            with patch.object(runner, 'FIXTURE', fixture), patch.dict(os.environ, {'BAKEOFF_GRAPHIFY': str(tool), 'OPENAI_API_KEY': 'never pass'}):
                result = runner.evaluate('graphify', work, out, 2)
            self.assertTrue((out / 'graphify.json').exists())
            self.assertEqual(len(result['queries']), 4)
            return result

    def test_successful_fake_adapter_exercises_capture_and_evidence(self):
        self.assertEqual(self.evaluate_fake()['status'], 'smoke_passed')

    def test_fake_source_mutation_is_detected(self):
        self.assertEqual(self.evaluate_fake(mutation=True)['status'], 'source_changed')

    def test_unconfigured_is_not_run(self):
        with patch.dict(os.environ, {}, clear=True):
            value = runner.evaluate('graft', Path('/unused'), Path('/unused'), 1)
        self.assertEqual(value['status'], 'not_run')

    def test_missing_binary_is_failed_launch_not_small_fast_success(self):
        with tempfile.TemporaryDirectory() as td:
            value = runner.run(['/definitely/no/candidate'], cwd=Path(td), env=runner.environment(Path(td)))
        self.assertFalse(value['ok']); self.assertEqual(value['error'], 'launch_failed')

if __name__ == '__main__':
    unittest.main()
