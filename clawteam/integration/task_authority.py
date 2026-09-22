"""One task authority per team, with an atomic external-state Beads migration.

ClawTeam remains the wire model and a read-only compatibility source after a
team migrates. No task data, hooks or configuration are written to a project.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from clawteam.store.base import BaseTaskStore
from clawteam.store.file import FileTaskStore
from clawteam.team.models import TaskItem, TaskPriority, TaskStatus
from runtime_config import REPO_ROOT, clawteam_data_dir, demo_mode

_cache = {}
_locks = {}
_guard = threading.Lock()
_priorities = [TaskPriority.urgent, TaskPriority.high, TaskPriority.medium, TaskPriority.low]
_to_status = {'pending': 'open', 'in_progress': 'in_progress', 'blocked': 'blocked', 'completed': 'closed'}


def beads_binary():
    path = Path(os.environ.get('COMPANY_HQ_BEADS_BIN') or REPO_ROOT / 'build/tools' / ('bd.exe' if os.name == 'nt' else 'bd'))
    return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None


@contextmanager
def _lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with _guard:
        mutex = _locks.setdefault(str(root), threading.RLock())
    with mutex, (root / '.hq.lock').open('a+b') as file:
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


class TaskStore(BaseTaskStore):
    def __init__(self, team_name):
        if not isinstance(team_name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}', team_name):
            raise ValueError('Invalid team name')
        super().__init__(team_name)
        self.root = clawteam_data_dir() / 'beads' / team_name
        self.database = self.root / 'database'
        self.legacy = FileTaskStore(team_name)

    @property
    def migrated(self):
        return (self.database / 'hq-authority.json').is_file()

    def _run(self, args, *, database=None, actor='hq', json_output=True):
        binary = beads_binary()
        if not binary:
            raise ValueError('The Beads task engine is unavailable. Run Company HQ setup to restore it.')
        database = database or self.database
        # Prevent inherited Beads routing, telemetry and ambient git identity from
        # changing the selected store. Preserve HOME and provider account paths.
        env = {k: v for k, v in os.environ.items() if not k.startswith(('BEADS_', 'BD_', 'GIT_')) and not k.upper().endswith(('_API_KEY', '_TOKEN', '_SECRET'))}
        env.update(BEADS_DIR=str(database), BEADS_ACTOR=actor, BD_NON_INTERACTIVE='1',
                   BD_DISABLE_METRICS='1', DO_NOT_TRACK='1', CI='true',
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   GIT_AUTHOR_NAME='Company HQ', GIT_AUTHOR_EMAIL='hq@localhost',
                   GIT_COMMITTER_NAME='Company HQ', GIT_COMMITTER_EMAIL='hq@localhost')
        result = subprocess.run([str(binary), '--sandbox', *args, *(['--json'] if json_output else [])],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=90)
        if result.returncode:
            # User-facing errors exclude backend paths, account identity, command
            # arguments and task bodies. Full command output is not a transcript.
            if result.returncode == 13: raise ValueError('Task ownership changed; refresh before claiming it.')
            raise ValueError('Task operation was rejected. Check dependencies, ownership and task status.')
        return json.loads(result.stdout) if json_output and result.stdout.strip() else None

    @staticmethod
    def _native_id(task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,160}', task_id):
            raise ValueError('Invalid task ID')
        return task_id if task_id.startswith('hq-') else 'hq-' + task_id

    def migrate(self):
        if self.migrated: return
        if demo_mode() or not beads_binary(): return
        with _lock(self.root):
            if self.migrated: return
            original = self.legacy.list_tasks()
            staging = Path(tempfile.mkdtemp(prefix='import-', dir=self.root))
            try:
                self._run(['init', '--quiet', '--non-interactive', '--skip-agents', '--skip-hooks', '--prefix', 'hq'], database=staging, json_output=False)
                ids = {task.id for task in original}
                for task in original:
                    if any(dep not in ids for dep in task.blocked_by):
                        raise ValueError('An existing task has a missing dependency; resolve it before migration.')
                    self._create(task, database=staging, dependencies=False)
                for task in original:
                    for dep in task.blocked_by:
                        self._run(['dep', 'add', self._native_id(task.id), self._native_id(dep)], database=staging)
                # Import completed tasks only after their completed prerequisites.
                remaining = {task.id: task for task in original if task.status == TaskStatus.completed}
                closed = set()
                while remaining:
                    ready = [t for t in remaining.values() if set(t.blocked_by) <= closed]
                    if not ready: raise ValueError('Completed legacy tasks have unresolved dependencies; migration was not activated.')
                    for task in ready:
                        self._run(['close', self._native_id(task.id), '--reason', 'Imported existing completion'], database=staging)
                        closed.add(task.id); remaining.pop(task.id)
                for task in original:
                    if task.status in (TaskStatus.in_progress, TaskStatus.blocked):
                        self._run(['update', self._native_id(task.id), '--status', _to_status[task.status.value]], database=staging)
                observed = self._run(['list', '--all', '--limit', '0'], database=staging)
                if len(observed) != len(original): raise ValueError('Task migration verification failed; original data is unchanged.')
                (staging / 'hq-authority.json').write_text(json.dumps({'schema': 1, 'engine': 'beads', 'version': '1.3.0', 'importedCount': len(original)}))
                (staging / 'legacy-backup.json').write_text(json.dumps([task.model_dump(mode='json', by_alias=True) for task in original]))
                os.replace(staging, self.database)
            except BaseException:
                shutil.rmtree(staging, ignore_errors=True)
                raise
            finally:
                staging.with_suffix('.gate.lock').unlink(missing_ok=True)

    def _create(self, task, *, database=None, dependencies=True):
        data = task.model_dump(mode='json', by_alias=True)
        args = ['create', task.subject, '--id', self._native_id(task.id), '--type', 'task',
                '--description', task.description, '--assignee', task.owner,
                '--priority', str(_priorities.index(task.priority)), '--metadata', json.dumps({'hq': data})]
        if dependencies and task.blocked_by:
            args += ['--deps', ','.join(self._native_id(i) for i in task.blocked_by)]
        return self._run(args, database=database)

    def create(self, subject, description='', owner='', priority=None, blocks=None, blocked_by=None, metadata=None):
        self.migrate()
        if not self.migrated:
            return self.legacy.create(subject, description, owner, priority, blocks, blocked_by, metadata)
        if blocks: raise ValueError('Use blocked_by on the dependent task.')
        task = TaskItem(id='hq-' + uuid.uuid4().hex[:12], subject=subject, description=description,
            owner=owner, priority=priority or TaskPriority.medium, blocked_by=blocked_by or [], metadata=metadata or {})
        with _lock(self.root):
            self._create(task)
            self._invalidate()
        return self.get(task.id)

    def _invalidate(self):
        with _guard: _cache.pop(str(self.database), None)

    def list_tasks(self, status=None, owner=None, priority=None, sort_by_priority=False):
        if not self.migrated:
            return self.legacy.list_tasks(status, owner, priority, sort_by_priority)
        key = str(self.database)
        with _guard: cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 2:
            tasks = copy.deepcopy(cached[1])
        else:
            with _lock(self.root): rows = self._run(['list', '--all', '--limit', '0'])
            closed = {row['id'] for row in rows if row['status'] == 'closed'}
            id_map = {row['id']: (row.get('metadata') or {}).get('hq', {}).get('id', row['id']) for row in rows}
            tasks = []
            for row in rows:
                legacy = (row.get('metadata') or {}).get('hq', {})
                dependencies = [d['depends_on_id'] for d in row.get('dependencies', []) if d.get('type') == 'blocks']
                pending = [id_map.get(d, d) for d in dependencies if d not in closed]
                state = {'closed': 'completed', 'in_progress': 'in_progress', 'blocked': 'blocked'}.get(row['status'], 'pending')
                if state == 'pending' and pending: state = 'blocked'
                data = {**legacy, 'id': id_map[row['id']], 'subject': row['title'], 'description': row.get('description', ''),
                    'owner': row.get('assignee', ''), 'status': state, 'blockedBy': pending,
                    'priority': _priorities[min(3, max(0, row.get('priority', 2)))].value,
                    'createdAt': row.get('created_at'), 'updatedAt': row.get('updated_at')}
                data['metadata'] = {**legacy.get('metadata', {}), 'taskEngine': 'beads', 'nativeId': row['id'],
                    'dependencies': [id_map.get(d, d) for d in dependencies]}
                tasks.append(TaskItem.model_validate(data))
            with _guard: _cache[key] = (time.monotonic(), copy.deepcopy(tasks))
        tasks = [t for t in tasks if (status is None or t.status == status) and (owner is None or t.owner == owner) and (priority is None or t.priority == priority)]
        if sort_by_priority: tasks.sort(key=lambda t: (_priorities.index(t.priority), t.created_at, t.id))
        return tasks

    def get(self, task_id):
        return next((t for t in self.list_tasks() if t.id == task_id), None)

    def update(self, task_id, status=None, owner=None, subject=None, description=None, priority=None,
               add_blocks=None, add_blocked_by=None, metadata=None, caller='', force=False):
        self.migrate()
        if not self.migrated:
            return self.legacy.update(task_id, status, owner, subject, description, priority, add_blocks, add_blocked_by, metadata, caller, force)
        if force: raise ValueError('Forced claim/completion is not supported by Company HQ.')
        if add_blocks: raise ValueError('Update blocked_by on the dependent task.')
        with _lock(self.root):
            # Avoid reacquiring an OS lock through list_tasks.
            rows = self._run(['show', self._native_id(task_id)])
            if not rows: return None
            row = rows[0]; native_id = row['id']
            if status == TaskStatus.in_progress:
                if any(d.get('status') != 'closed' and d.get('dependency_type') == 'blocks' for d in row.get('dependencies', [])):
                    raise ValueError('Complete the prerequisites before starting this task.')
                actor = owner or caller or row.get('assignee') or 'hq'
                self._run(['update', native_id, '--claim'], actor=actor)
            args = ['update', native_id]
            if status is not None and status != TaskStatus.in_progress: args += ['--status', _to_status[TaskStatus(status).value]]
            for value, flag in [(owner, '--assignee'), (subject, '--title'), (description, '--description')]:
                if value is not None: args += [flag, value]
            if priority is not None: args += ['--priority', str(_priorities.index(priority))]
            if metadata:
                saved = row.get('metadata') or {}; saved.setdefault('hq', {}).setdefault('metadata', {}).update(metadata)
                args += ['--metadata', json.dumps(saved)]
            for dep in add_blocked_by or []: self._run(['dep', 'add', native_id, self._native_id(dep)])
            if len(args) > 2: self._run(args, actor=caller or 'hq')
            self._invalidate()
        return self.get(task_id)

    def release_stale_locks(self):
        # A disconnected UI is not evidence that an agent's lease is abandoned.
        return [] if self.migrated else self.legacy.release_stale_locks()


def install_task_authority():
    """Wire upstream consumers to the same facade, without modifying vendor code."""
    import clawteam.team.tasks
    import clawteam.board.collector
    clawteam.team.tasks.TaskStore = TaskStore
    clawteam.board.collector.TaskStore = TaskStore
