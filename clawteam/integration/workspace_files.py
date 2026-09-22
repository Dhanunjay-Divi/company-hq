"""Confined project inspection and optimistic text editing, with private drafts."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

MAX_FILE = 256 * 1024
_lock = threading.RLock()
_excluded = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'target', '.DS_Store'}


def _directory_flags():
    return os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_CLOEXEC', 0)


def _open_relative(project, relative, flags):
    """Open a file through verified directory handles where the OS supports it."""
    root, path = _path(project, relative)
    parts = path.relative_to(root).parts
    if not parts: raise ValueError('Choose a file inside this project.')
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if os.open in os.supports_dir_fd and nofollow:
        directory = os.open(root, _directory_flags())
        try:
            for part in parts[:-1]:
                child = os.open(part, _directory_flags() | nofollow, dir_fd=directory)
                os.close(directory); directory = child
            fd = os.open(parts[-1], flags | nofollow | getattr(os, 'O_CLOEXEC', 0), dir_fd=directory)
        finally:
            os.close(directory)
    else:
        # Windows does not expose openat-style traversal through Python. Repeat
        # the full path validation immediately before and after opening.
        _, path = _path(project, relative)
        fd = os.open(path, flags | nofollow | getattr(os, 'O_CLOEXEC', 0))
        try:
            _, checked = _path(project, relative)
            opened, current = os.fstat(fd), checked.stat()
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('File changed while opening it.')
        except BaseException:
            os.close(fd); raise
    opened = os.fstat(fd)
    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
        os.close(fd)
        raise ValueError('Only regular project files with one name can be opened.')
    return fd


def _open_directory(project, relative=''):
    """Open a directory without following a raced parent symlink."""
    root, path = _path(project, relative)
    parts = path.relative_to(root).parts
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if os.open in os.supports_dir_fd and nofollow:
        directory = os.open(root, _directory_flags())
        try:
            for part in parts:
                child = os.open(part, _directory_flags() | nofollow, dir_fd=directory)
                os.close(directory); directory = child
            return root, path, directory
        except BaseException:
            os.close(directory); raise
    _, checked = _path(project, relative)
    directory = os.open(checked, _directory_flags())
    try:
        _, after = _path(project, relative)
        opened, current = os.fstat(directory), after.stat()
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('Folder changed while opening it.')
    except BaseException:
        os.close(directory); raise
    return root, checked, directory


def _path(project, relative=''):
    root = Path(project).resolve(strict=True)
    if not isinstance(relative, str) or len(relative) > 2000 or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Choose a relative path inside this project.')
    candidate = root / relative
    # Reject symlinks at every component, even if their current target is inside.
    for parent in (candidate, *candidate.parents):
        if parent == root: break
        if parent.is_symlink(): raise ValueError('Symbolic links cannot be opened by the project editor.')
    result = candidate.resolve(strict=True)
    if not result.is_relative_to(root) or '.git' in result.relative_to(root).parts:
        raise ValueError('Choose a file inside this project.')
    return root, result


def listing(project, relative=''):
    root, path, directory = _open_directory(project, relative)
    try:
        entries = []
        scan_target = directory if os.scandir in os.supports_fd else path
        with os.scandir(scan_target) as scanned:
            for file in scanned:
                is_symlink = file.is_symlink()
                is_directory = file.is_dir(follow_symlinks=False)
                links = file.stat(follow_symlinks=False).st_nlink
                entries.append((file.name, is_symlink, is_directory, links))
    finally:
        os.close(directory)
    items = []
    for name, is_symlink, is_directory, links in sorted(entries, key=lambda x: (not x[2], x[0].lower())):
        if name in _excluded or is_symlink or not is_directory and links != 1: continue
        item_path = (path.relative_to(root) / name).as_posix()
        items.append({'name': name, 'path': item_path, 'kind': 'folder' if is_directory else 'file'})
        if len(items) == 500: break
    return {'path': path.relative_to(root).as_posix(), 'items': items, 'limited': len(items) == 500}


def read(project, relative):
    fd = _open_relative(project, relative, os.O_RDONLY)
    try:
        opened = os.fstat(fd)
        if opened.st_size > MAX_FILE: raise ValueError('The editor opens text files up to 256 KiB.')
        with os.fdopen(fd, 'rb', closefd=False) as file: data = file.read(MAX_FILE + 1)
    finally: os.close(fd)
    if len(data) > MAX_FILE: raise ValueError('The editor opens text files up to 256 KiB.')
    if b'\0' in data: raise ValueError('This is a binary file. Open it in its native app.')
    try: text = data.decode('utf-8')
    except UnicodeDecodeError: raise ValueError('This file is not UTF-8 text.') from None
    return {'path': relative, 'text': text, 'revision': hashlib.sha256(data).hexdigest()}


def write(project, relative, text, revision):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_FILE: raise ValueError('Text file is too large.')
    if not isinstance(revision, str): raise ValueError('Reload the file before saving.')
    with _lock:
        fd = _open_relative(project, relative, os.O_RDWR)
        try:
            opened = os.fstat(fd)
            if opened.st_size > MAX_FILE: raise ValueError('The editor opens text files up to 256 KiB.')
            with os.fdopen(fd, 'rb', closefd=False) as file: before = file.read(MAX_FILE + 1)
            if hashlib.sha256(before).hexdigest() != revision:
                raise ValueError('This file changed outside the editor. Reload it before saving.')
            os.lseek(fd, 0, os.SEEK_SET)
            with os.fdopen(fd, 'wb', closefd=False) as file:
                file.write(text.encode()); file.truncate(); file.flush(); os.fsync(fd)
        finally: os.close(fd)
    return read(project, relative)


def draft(state, team, body=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}', team): raise ValueError('Invalid draft ID.')
    folder = Path(state) / 'drafts'; path = folder / (team + '.json')
    with _lock:
        try: saved = json.loads(path.read_text())
        except (FileNotFoundError, ValueError): saved = {'text': '', 'revision': 0}
        if body is None: return saved
        if set(body) != {'text', 'revision'} or not isinstance(body.get('text'), str) or len(body['text']) > 24000:
            raise ValueError('Draft must contain text of at most 24000 characters.')
        if body['revision'] != saved['revision']: raise ValueError('This draft changed in another window. Reload before replacing it.')
        value = {'text': body['text'], 'revision': saved['revision'] + 1}
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(prefix='draft-', dir=folder)
        try:
            with os.fdopen(fd, 'w') as file: json.dump(value, file)
            os.replace(temp, path)
        finally: Path(temp).unlink(missing_ok=True)
        return value
