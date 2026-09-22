import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_authority import TaskStore, beads_binary, _cache
from clawteam.store.file import FileTaskStore
from clawteam.team.models import TaskStatus


@unittest.skipUnless(beads_binary(), 'Pinned Beads engine is not installed')
class BeadsAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hq-task-authority-')
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.project = self.root / 'project'; self.project.mkdir()
        self.env = patch.dict(os.environ, {'CLAWTEAM_DATA_DIR': str(self.state), 'CLAWTEAM_INTEGRATION_TESTING': '1',
            'CLAWTEAM_INTEGRATION_TEST_DATA_DIR': str(self.state), 'COMPANY_HQ_DEMO': '0'})
        self.env.start(); _cache.clear()

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def test_migration_dag_claim_close_and_isolation(self):
        legacy = FileTaskStore('alpha')
        old = legacy.create('Existing task', metadata={'evidence': 'test'})
        before = (self.state / 'tasks' / 'alpha' / f'task-{old.id}.json').read_bytes()
        store = TaskStore('alpha'); store.migrate()
        self.assertTrue(store.migrated)
        self.assertEqual(store.get(old.id).metadata['evidence'], 'test')
        build = store.create('Build', blocked_by=[old.id])
        self.assertEqual(build.status, TaskStatus.blocked)
        with self.assertRaises(ValueError): store.update(build.id, status=TaskStatus.in_progress, caller='worker')
        with self.assertRaises(ValueError): store.update(old.id, add_blocked_by=[build.id])
        store.update(old.id, status=TaskStatus.completed)
        self.assertEqual(store.get(build.id).status, TaskStatus.pending)
        store.update(build.id, status=TaskStatus.in_progress, caller='worker')
        with self.assertRaises(ValueError): store.update(build.id, status=TaskStatus.in_progress, caller='other')
        store.update(build.id, status=TaskStatus.completed, caller='worker')
        self.assertEqual(TaskStore('alpha').get(build.id).status, TaskStatus.completed)
        self.assertEqual(TaskStore('beta').list_tasks(), [])
        self.assertEqual((self.state / 'tasks' / 'alpha' / f'task-{old.id}.json').read_bytes(), before)
        self.assertEqual(list(self.project.iterdir()), [])
        with patch('task_authority.beads_binary', return_value=None):
            _cache.clear()
            with self.assertRaises(ValueError): TaskStore('alpha').list_tasks()

    def test_failed_import_keeps_original_authority(self):
        original = FileTaskStore('alpha').create('Broken legacy dependency', blocked_by=['missing'])
        store = TaskStore('alpha')
        with self.assertRaises(ValueError): store.migrate()
        self.assertFalse(store.migrated)
        self.assertEqual(store.list_tasks()[0].id, original.id)
        self.assertEqual(list(store.root.glob('import-*')), [])


class TaskBoundaryTests(unittest.TestCase):
    def test_invalid_names(self):
        for name in ('../alpha', '/', '-flag', 'a/b'):
            with self.assertRaises(ValueError): TaskStore(name)

    def test_beads_environment_and_no_project_working_directory(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp, patch('task_authority.clawteam_data_dir', return_value=Path(tmp)), \
             patch('task_authority.beads_binary', return_value=Path('/fixture/bd')), \
             patch('task_authority.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '[]', '')) as run:
            store = TaskStore('alpha'); store.root.mkdir(parents=True)
            with patch.dict(os.environ, {'OPENAI_API_KEY':'test-not-a-key','GH_TOKEN':'test-token','CUSTOM_SECRET':'test-secret'}):
                store._run(['list'])
            env = run.call_args.kwargs['env']
            self.assertEqual(env['BD_DISABLE_METRICS'], '1')
            self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('GH_TOKEN',env);self.assertNotIn('CUSTOM_SECRET',env)
            self.assertEqual(env.get('HOME'), os.environ.get('HOME'))
            self.assertEqual(run.call_args.kwargs['cwd'], store.root)
            self.assertIn('--sandbox', run.call_args.args[0])


if __name__ == '__main__': unittest.main()
