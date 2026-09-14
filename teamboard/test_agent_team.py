import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import agent_team as t


def record_worker(args):
    base, run_id, n = args
    t.mutate(run_id, lambda s: t.message(s, 'coordinator', 'team', f'worker {n}'), Path(base))


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'product'; self.project.mkdir()
        (self.project / 'existing.txt').write_text('original')
        self.base = self.root / 'toolkit'
        self.state = t.start(self.project, 'Integration fixture', self.base)
        self.run = self.state['id']

    def mutate(self, f):
        return t.mutate(self.run, f, self.base)

    def test_lifecycle_no_project_writes(self):
        self.mutate(lambda s: t.register(s, 'scan', 'Scout', 'Explorer', 'gpt-5.6-luna', 'Inspect one file', status='running'))
        self.mutate(lambda s: t.message(s, 'coordinator', 'scan', 'Read existing.txt', 'sent'))
        with self.assertRaises(ValueError):
            self.mutate(lambda s: t.finish(s, 'completed', 'premature'))
        self.mutate(lambda s: t.update(s, 'scan', 'completed', 'One file inspected'))
        final = self.mutate(lambda s: t.finish(s, 'completed', 'Verified fixture'))
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(list(self.project.iterdir()), [self.project / 'existing.txt'])
        self.assertEqual((self.project / 'existing.txt').read_text(), 'original')
        with self.assertRaises(ValueError):
            self.mutate(lambda s: t.message(s, 'coordinator', 'team', 'terminal write'))

    def test_failed_update_rolls_back(self):
        before = (t.run_dir(self.run, self.base) / 'state.json').read_bytes()
        for operation in (
            lambda s: t.update(s, 'missing', 'completed', 'No actual agent'),
            lambda s: t.message(s, 'missing', 'team', 'Invalid sender'),
            lambda s: t.register(s, 'x', 'X', 'Role', 'invalid model label', 'Task'),
        ):
            with self.assertRaises(ValueError):
                self.mutate(operation)
            self.assertEqual(before, (t.run_dir(self.run, self.base) / 'state.json').read_bytes())

    def test_concurrent_writers_do_not_lose_messages(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            list(pool.map(record_worker, [(str(self.base), self.run, i) for i in range(24)]))
        state = t.read(self.run, self.base)
        self.assertEqual(len(state['events']), 25)
        self.assertEqual(len({e['id'] for e in state['events']}), 25)
        self.assertEqual((t.run_dir(self.run, self.base) / 'state.json').stat().st_mode & 0o777, 0o600)

    def test_events_bounded_and_truncation_explicit(self):
        def many(s):
            for i in range(520):
                t.message(s, 'coordinator', 'team', f'Message {i}')
        state = self.mutate(many)
        self.assertEqual(len(state['events']), 500)
        self.assertEqual(state['events_dropped'], 21)

    def test_traversal_and_unknown_run_do_not_create_paths(self):
        for run_id in ('../escape', 'bad', self.run.upper()):
            with self.assertRaises(ValueError):
                t.run_dir(run_id, self.base)
        other = '11111111-1111-1111-1111-111111111111'
        with self.assertRaises(OSError):
            t.mutate(other, lambda s: None, self.base)
        self.assertFalse(t.run_dir(other, self.base).exists())

    def test_launcher_uses_argv_preserves_policy_and_economical_model(self):
        task = 'Review `literal`; $(not-a-command) and spaces'
        cmd = t.launch_command(self.project, task, self.run, 'gpt-5.6-sol', '/native/codex')
        self.assertEqual(cmd[:5], ['/native/codex', '--cd', str(self.project), '--model', 'gpt-5.6-sol'])
        self.assertTrue(cmd[-1].endswith(task))
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', cmd)
        self.assertNotIn('--ignore-user-config', cmd)

    def test_symlink_run_state_and_lock_cannot_write_external_files(self):
        other = '11111111-1111-1111-1111-111111111111'
        alias = t.run_dir(other, self.base)
        alias.symlink_to(t.run_dir(self.run, self.base), target_is_directory=True)
        before = t.read(self.run, self.base)
        with self.assertRaises(OSError):
            t.mutate(other, lambda s: t.message(s, 'coordinator', 'team', 'not allowed'), self.base)
        self.assertEqual(t.read(self.run, self.base), before)
        lock = t.run_dir(self.run, self.base) / '.lock'
        external = self.root / 'external'; external.write_text('preserve')
        lock.unlink()
        lock.symlink_to(external)
        with self.assertRaises(OSError):
            self.mutate(lambda s: None)
        self.assertEqual(external.read_text(), 'preserve')
        lock.unlink()
        lock.touch(mode=0o600)
        state = t.run_dir(self.run, self.base) / 'state.json'
        state.unlink(); state.symlink_to(external)
        with self.assertRaises(OSError):
            self.mutate(lambda s: None)
        self.assertEqual(external.read_text(), 'preserve')

    def test_journal_failure_after_spawn_still_waits_for_owned_process(self):
        self.mutate(lambda s: t.register(s, 'lead', 'Lead', 'Lead', 'gpt-5.6-sol', 'Task'))
        process = mock.Mock(); process.wait.return_value = 0
        def popen(command):
            self.mutate(lambda s: t.update(s, 'lead', 'stopped', 'Concurrent reconciliation'))
            self.mutate(lambda s: t.finish(s, 'stopped', 'Closed concurrently'))
            return process
        self.assertEqual(t.run_process(['unused'], self.run, self.base, popen), 0)
        process.wait.assert_called_once_with()

    def test_cli_exit_preserves_completed_agent_summary(self):
        self.mutate(lambda s: t.register(s, 'lead', 'Lead', 'Lead', 'gpt-5.6-sol', 'Task'))
        process = mock.Mock()
        def wait():
            self.mutate(lambda s: t.update(s, 'lead', 'completed', 'Actual finished work'))
            return 0
        process.wait.side_effect = wait
        self.assertEqual(t.run_process(['unused'], self.run, self.base, lambda _: process), 0)
        current = t.read(self.run, self.base)
        self.assertEqual(current['agents'][0]['status'], 'completed')
        self.assertEqual(current['agents'][0]['summary'], 'Actual finished work')
        self.assertEqual(current['status'], 'active')

    def test_launch_failure_is_terminal_and_not_claimed_as_work(self):
        self.mutate(lambda s: t.register(s, 'lead', 'Lead', 'Lead', 'gpt-5.6-sol', 'Task'))
        def fail(_): raise FileNotFoundError('fixture executable absent')
        self.assertEqual(t.run_process(['unused'], self.run, self.base, fail), 1)
        self.assertEqual(t.read(self.run, self.base)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
