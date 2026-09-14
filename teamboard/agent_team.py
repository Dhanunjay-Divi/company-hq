#!/opt/homebrew/bin/python3
"""Local activity journal and launcher for native Codex teams. No model API calls."""
import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

BASE = Path(__file__).resolve().parent
MAX_EVENTS = 500
MODELS = ('gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-5.5', 'gpt-6-astra')
STATES = ('queued', 'running', 'blocked', 'completed', 'failed', 'stopped')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def bounded(value, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Text must contain 1–{limit} characters')
    return value


def run_dir(run_id, base=BASE):
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError('Use the canonical run UUID returned by start')
    return base / 'runs' / run_id


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def event(state, kind, sender, recipient, text):
    stamp = now()
    state['events'].append(dict(id=str(uuid.uuid4()), time=stamp, kind=kind,
                                **{'from': sender, 'to': recipient}, text=bounded(text)))
    if len(state['events']) > MAX_EVENTS:
        state['events_dropped'] = state.get('events_dropped', 0) + len(state['events']) - MAX_EVENTS
        state['events'] = state['events'][-MAX_EVENTS:]
    state['updated_at'] = stamp


def start(project, title, base=BASE):
    project = Path(project).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError('Project must be an existing directory')
    run_id = str(uuid.uuid4())
    create_run_directory(run_id, base)
    stamp = now()
    state = dict(schema=1, id=run_id, title=bounded(title, 200), project=str(project),
                 created_at=stamp, updated_at=stamp, status='active', agents=[], events=[],
                 events_dropped=0,
                 usage_note='No model usage is measured here. Models and status are reported by the workflow. '
                 'Messages are recorded summaries; delivery happens through native Codex tools. '
                 'Only the latest 500 events are retained. No private reasoning or automatic transcript capture.')
    event(state, 'run_started', 'coordinator', 'team', 'Activity journal opened; no workers launched by start.')
    with opened_run(run_id, base) as directory:
        write_fd(directory, state)
    return state


def create_run_directory(run_id, base):
    run_dir(run_id, base)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try: os.mkdir('runs', mode=0o700, dir_fd=fd)
        except FileExistsError: pass
        runs = os.open('runs', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try: os.mkdir(run_id, mode=0o700, dir_fd=runs)
        finally: os.close(runs)
    finally: os.close(fd)
    with opened_run(run_id, base) as directory:
        # Create exactly once before exposing state, avoiding concurrent
        # O_CREAT/O_NOFOLLOW first-open behavior on macOS.
        lock = os.open('.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       0o600, dir_fd=directory)
        os.close(lock)


def read(run_id, base=BASE):
    with opened_run(run_id, base) as directory:
        return read_fd(directory)


@contextmanager
def opened_run(run_id, base=BASE):
    run_dir(run_id, base)  # Validate the UUID before any file operations.
    descriptors = []
    try:
        for part in (str(base), 'runs', run_id):
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=descriptors[-1] if descriptors else None)
            descriptors.append(fd)
            if os.fstat(fd).st_uid != os.getuid():
                raise ValueError('Run directories must belong to the current user')
        yield descriptors[-1]
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def read_fd(directory):
    fd = os.open('state.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    with os.fdopen(fd) as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('State must be a regular file owned by this user')
        return json.load(source)


def write_fd(directory, state):
    name = '.state-' + str(uuid.uuid4())
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(state, output, ensure_ascii=False, indent=2)
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        os.replace(name, 'state.json', src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try: os.unlink(name, dir_fd=directory)
        except FileNotFoundError: pass


def mutate(run_id, operation, base=BASE):
    with opened_run(run_id, base) as directory:
        fd = os.open('.lock', os.O_RDWR | os.O_NOFOLLOW, dir_fd=directory)
        with os.fdopen(fd, 'a') as lock:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise ValueError('Run lock must be an owned, unlinked regular file')
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = read_fd(directory)
            if state['status'] != 'active':
                raise ValueError('Run is terminal; start a new run for follow-up work')
            operation(state)
            write_fd(directory, state)
            return state


def find_agent(state, agent_id):
    return next((a for a in state['agents'] if a['id'] == agent_id), None)


def register(state, agent_id, name, role, model, task, runtime_id='', status='queued'):
    if find_agent(state, agent_id):
        raise ValueError('Agent ID already exists in this run')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:/._-]{0,199}', model):
        raise ValueError('Invalid model label; use unknown if the runtime model was not observed')
    if status not in STATES:
        raise ValueError('Invalid agent status')
    agent = dict(id=bounded(agent_id, 80), name=bounded(name, 100), role=bounded(role, 100),
                 model=model, task=bounded(task), runtime_id=runtime_id, status=status,
                 updated_at=now(), summary='')
    state['agents'].append(agent)
    event(state, 'agent_registered', 'coordinator', agent_id, f"{name} · {role} · {model}: {task}")


def update(state, agent_id, status, summary):
    agent = find_agent(state, agent_id)
    if agent is None:
        raise ValueError('Unknown agent ID')
    if status not in STATES:
        raise ValueError('Invalid agent status')
    agent.update(status=status, summary=bounded(summary), updated_at=now())
    event(state, 'status', agent_id, 'team', f'{status}: {summary}')


def message(state, sender, recipient, text, delivery='note'):
    participants = {a['id'] for a in state['agents']} | {'team', 'coordinator', 'user'}
    if sender not in participants or recipient not in participants:
        raise ValueError('Message endpoints must be registered agent IDs, team, coordinator, or user')
    if delivery not in ('sent', 'received', 'note'):
        raise ValueError('Invalid delivery label')
    event(state, 'note' if delivery == 'note' else 'message', sender, recipient,
          f'[{delivery}] {bounded(text, 3900)}')


def finish(state, status, summary):
    if status not in ('completed', 'failed', 'stopped'):
        raise ValueError('Invalid terminal run status')
    if any(a['status'] in ('queued', 'running', 'blocked') for a in state['agents']):
        raise ValueError('Reconcile active agents with actual runtime status before finishing the run')
    state['status'] = status
    event(state, 'run_finished', 'coordinator', 'team', summary)


def input_text(value):
    return bounded(sys.stdin.read(4001) if value == '-' else value)


def launch_command(project, task, run_id, model, codex, effort='medium'):
    instructions = (
        f'Use the shared agent-toolkit skill. Team Board run ID: {run_id}. '
        'For an idea or from-scratch product, read the toolkit OPERATING-MODEL.md, '
        'clarify material unknowns, then plan and execute the connected customer/product, design, '
        'engineering, QA, marketing and launch work within the requested scope. '
        'Use installed Ruflo and codebase-memory MCP integrations according to the skill; '
        'load agency-agents specialist references only where relevant. '
        f'Journal CLI: {BASE / "agent_team.py"}. The registered lead ID is lead. '
        'Use native subagents only when independent work merits it; select Luna for simple scans, '
        'Terra for bounded implementation, Sol for complex reasoning/review, or GPT-5.5 when requested. '
        'The user requests the best reviewed available model as supervisor for planning, delegation, synthesis and final review. '
        'Consult the shared runtime capabilities and routing policy; do not permanently assume one model is best. '
        'Use the smaller workers for routine execution; use department supervisors for whole-product work and avoid idle workers. '
        'Record actual assignments, status changes, concise sent/received messages and results in this run. '
        'Journaling does not send messages: deliver through native collaboration tools first, then record '
        'a sanitized summary. Do not record credentials, customer content or private reasoning. '
        'Stop or reconcile your child agents before completing; update lead and finish this run accurately. '
        'Use separate worktrees for conflicting concurrent writers. Follow project instructions.\n\n'
        + task)
    return [codex, '--cd', str(project), '--model', model,
            '-c', 'model_reasoning_effort=' + json.dumps(effort),
            '-c', 'agents.default_subagent_model="gpt-5.6-terra"',
            '-c', 'agents.default_subagent_reasoning_effort="medium"', instructions]


def run_process(command, run_id, base=BASE, popen=subprocess.Popen):
    """Keep the native process owned even when optional journal recording fails."""
    def record(operation):
        try:
            mutate(run_id, operation, base)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Team Board recording unavailable: {exc}. Native task remains authoritative.', file=sys.stderr)

    try:
        process = popen(command)
    except OSError as exc:
        record(lambda s: update(s, 'lead', 'failed', 'Native Codex failed to start: ' + str(exc)[:500]))
        record(lambda s: finish(s, 'failed', 'Launcher could not start Codex.'))
        return 1
    record(lambda s: update(s, 'lead', 'running', 'Native Codex process started; model configured by launcher.'))
    try:
        code = process.wait()
    except KeyboardInterrupt:
        # The foreground process group also receives Ctrl-C. Reap our own child;
        # no claim is made about descendant task completion.
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        record(lambda s: update(s, 'lead', 'stopped', 'CLI interrupted and owned process reaped; reconcile child tasks in Codex.'))
        print('Interrupted. Reconcile child task state in native Codex.', file=sys.stderr)
        return 130
    try:
        current = read(run_id, base)
    except (OSError, ValueError, KeyError):
        print('Native CLI exited; journal unreadable. Check task outcome in Codex.', file=sys.stderr)
        return code
    if current['status'] == 'active':
        lead = find_agent(current, 'lead')
        if lead and lead['status'] in ('queued', 'running'):
            record(lambda s: update(s, 'lead', 'blocked',
                    f'Native CLI exited with code {code}; final outcome was not recorded. Reconcile in Codex.'))
        else:
            record(lambda s: message(s, 'coordinator', 'team',
                    f'Native CLI exited with code {code}. Existing agent outcomes preserved; run completion needs reconciliation.'))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('start', help='Open a run journal without starting model workers')
    p.add_argument('--project', required=True); p.add_argument('--title', required=True)
    p = subs.add_parser('agent', help='Register an actual assignment')
    p.add_argument('--run', required=True); p.add_argument('--id', required=True)
    p.add_argument('--name', required=True); p.add_argument('--role', required=True)
    p.add_argument('--model', required=True, help='Reported model ID, including provider/model IDs; unknown if unavailable')
    p.add_argument('--task', required=True); p.add_argument('--runtime-id', default='')
    p.add_argument('--status', choices=STATES, default='queued')
    p = subs.add_parser('update')
    p.add_argument('--run', required=True); p.add_argument('--id', required=True)
    p.add_argument('--status', choices=STATES, required=True); p.add_argument('--summary', required=True)
    p = subs.add_parser('message', help='Record a summary; does NOT deliver it to an agent')
    p.add_argument('--run', required=True); p.add_argument('--from', dest='sender', required=True)
    p.add_argument('--to', required=True); p.add_argument('--text', required=True, help='Use - to read stdin')
    p.add_argument('--delivery', choices=('sent', 'received', 'note'), default='note')
    p = subs.add_parser('finish')
    p.add_argument('--run', required=True)
    p.add_argument('--status', choices=('completed', 'failed', 'stopped'), required=True)
    p.add_argument('--summary', required=True)
    p = subs.add_parser('status'); p.add_argument('--run', required=True)
    subs.add_parser('list')
    subs.add_parser('view', help='Open the native macOS activity viewer')
    p = subs.add_parser('work', help='Start an interactive native Codex task, using your existing login')
    p.add_argument('--project', required=True); p.add_argument('--model', default='auto', help='auto selects from the current reviewed runtime catalog')
    p.add_argument('--reason', help='Optional context for a model selection')
    p.add_argument('task', help='Task text, or - to read stdin')
    args = parser.parse_args()
    if args.command == 'start':
        result = start(args.project, args.title)
        print(json.dumps({'run_id': result['id'], 'state': str(run_dir(result['id']) / 'state.json')}))
    elif args.command == 'agent':
        mutate(args.run, lambda s: register(s, args.id, args.name, args.role, args.model,
                                            args.task, args.runtime_id, args.status))
        print('Agent assignment recorded')
    elif args.command == 'update':
        mutate(args.run, lambda s: update(s, args.id, args.status, args.summary))
        print('Status recorded')
    elif args.command == 'message':
        text = input_text(args.text)
        mutate(args.run, lambda s: message(s, args.sender, args.to, text, args.delivery))
        print('Message summary recorded; this command does not send messages')
    elif args.command == 'finish':
        mutate(args.run, lambda s: finish(s, args.status, args.summary))
        print('Run finished')
    elif args.command == 'status':
        print(json.dumps(read(args.run), indent=2, ensure_ascii=False))
    elif args.command == 'list':
        rows = []
        for path in sorted((BASE / 'runs').glob('*/state.json')):
            try:
                s = json.loads(path.read_text())
                rows.append({k: s[k] for k in ('id', 'title', 'project', 'status', 'updated_at')})
            except (OSError, ValueError, KeyError):
                rows.append({'state_file': str(path), 'error': 'unreadable run'})
        print(json.dumps(rows, indent=2))
    elif args.command == 'view':
        app = BASE / 'Agent Team Board.app'
        if not app.is_dir():
            raise ValueError('Build the viewer with teamboard/macos/build.sh first')
        return subprocess.call(['open', str(app)])
    elif args.command == 'work':
        task = input_text(args.task)
        codex = shutil.which('codex')
        if codex is None:
            raise ValueError('Native Codex CLI not found in PATH')
        sys.path.insert(0, str(BASE.parent))
        from discover import discover
        capabilities = discover()
        selection = capabilities['selection']
        models = {row.get('model') or row['id']: row for row in capabilities['providers']['codex']['models']}
        model = selection.get('model') if args.model == 'auto' else args.model
        if not model or model not in models:
            raise ValueError('Requested supervisor is unavailable in the verified Codex catalog; run discover.py --refresh or configure its own provider client')
        effort = selection.get('effort') if args.model == 'auto' else models[model].get('defaultReasoningEffort')
        if not effort:
            raise ValueError('Supervisor reasoning configuration needs review before launching')
        state = start(args.project, task[:200])
        run_id = state['id']
        mutate(run_id, lambda s: register(s, 'lead', 'Lead', 'Coordinator', model,
                                          task, status='queued'))
        print(f'Team Board run: {run_id}', flush=True)
        command = launch_command(state['project'], task, run_id, model, codex, effort)
        if args.reason:
            mutate(run_id, lambda s: message(s, 'coordinator', 'team',
                                              'Model selection reason: ' + args.reason))
        return run_process(command, run_id)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'agent-team: {exc}', file=sys.stderr)
        raise SystemExit(1)
