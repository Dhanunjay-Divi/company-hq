"""Private, chat-scoped image attachments. Uploading never starts a model turn."""
from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import re
import threading
import uuid

MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_CHAT_BYTES = 100 * 1024 * 1024
MAX_CHAT_IMAGES = 100
MIME_EXTENSIONS = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/webp': '.webp',
}
STORAGE_EXTENSIONS = frozenset((*MIME_EXTENSIONS.values(), '.image'))
_LOCK = threading.RLock()
TEAM_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')


def _directory(state: Path, team: str) -> Path:
    if not isinstance(team, str) or not TEAM_RE.fullmatch(team):
        raise ValueError('Invalid chat identifier')
    root = Path(state) / 'images'
    directory = root / team
    if root.is_symlink() or directory.is_symlink():
        raise ValueError('Image storage is unavailable')
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.mkdir(exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ValueError('Image storage is unavailable') from exc
    if root.is_symlink() or directory.is_symlink() or not root.is_dir() or not directory.is_dir():
        raise ValueError('Image storage is unavailable')
    return directory


def _safe_name(value: str) -> str:
    name = value.replace('\\', '/').rsplit('/', 1)[-1].strip()
    if not name or name in ('.', '..') or len(name) > 240 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError('Enter a short image filename')
    return name


def _mime(data: bytes) -> str:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('Choose a PNG, JPEG or WebP image')


def upload(state: Path, team: str, body: dict) -> dict:
    if not isinstance(body, dict) or set(body) != {'name', 'mimeType', 'dataBase64'}:
        raise ValueError('Send an image name, type and encoded content')
    name, mime, encoded = body['name'], body['mimeType'], body['dataBase64']
    if not all(isinstance(item, str) for item in (name, mime, encoded)):
        raise ValueError('Invalid image attachment')
    name = _safe_name(name)
    if len(encoded) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
        raise ValueError('Each image must be 6 MB or smaller')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('Invalid image content') from exc
    if not data or len(data) > MAX_IMAGE_BYTES or _mime(data) != mime:
        raise ValueError('Image content does not match its type or size limit')
    with _LOCK:
        directory = _directory(state, team)
        try:
            existing = [
                path for path in directory.iterdir()
                if path.suffix in STORAGE_EXTENSIONS and not path.is_symlink() and path.is_file()
            ]
            existing_bytes = sum(path.lstat().st_size for path in existing)
        except OSError as exc:
            raise ValueError('Image storage is unavailable') from exc
        if len(existing) >= MAX_CHAT_IMAGES or existing_bytes + len(data) > MAX_CHAT_BYTES:
            raise ValueError('This chat has reached its image storage allowance')
        image_id = uuid.uuid4().hex
        meta = {'id': image_id, 'name': name, 'mimeType': mime, 'size': len(data)}
        image_path = directory / f'{image_id}{MIME_EXTENSIONS[mime]}'
        meta_path = directory / f'{image_id}.json'
        try:
            for path, content in ((image_path, data), (meta_path, json.dumps(meta).encode())):
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as output:
                    output.write(content)
        except Exception as exc:
            for path in (image_path, meta_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ValueError('Image storage is unavailable') from exc
    return {**meta, 'url': f'/api/attachments/{team}/{image_id}'}


def read(state: Path, team: str, image_id: str) -> tuple[dict, Path]:
    if not isinstance(image_id, str) or not re.fullmatch(r'[a-f0-9]{32}', image_id):
        raise ValueError('Invalid image identifier')
    directory = _directory(state, team)
    meta_path = directory / f'{image_id}.json'
    if meta_path.is_symlink() or not meta_path.is_file():
        raise ValueError('Image not found in this chat')
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('Image is unavailable') from exc
    if not isinstance(meta, dict) or meta.get('id') != image_id:
        raise ValueError('Image is unavailable')
    mime = meta.get('mimeType')
    name = meta.get('name')
    size = meta.get('size')
    if mime not in MIME_EXTENSIONS or not isinstance(name, str) or _safe_name(name) != name:
        raise ValueError('Image is unavailable')
    canonical_path = directory / f'{image_id}{MIME_EXTENSIONS[mime]}'
    legacy_path = directory / f'{image_id}.image'
    if canonical_path.is_symlink() or legacy_path.is_symlink():
        raise ValueError('Image not found in this chat')
    path = canonical_path if canonical_path.is_file() else legacy_path
    if not path.is_file():
        raise ValueError('Image not found in this chat')
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise ValueError('Image is unavailable') from exc
    if isinstance(size, bool) or not isinstance(size, int) or size != actual_size or not 0 < actual_size <= MAX_IMAGE_BYTES:
        raise ValueError('Image is unavailable')
    try:
        actual_mime = _mime(path.read_bytes())
        resolved_path = path.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise ValueError('Image is unavailable') from exc
    if actual_mime != mime:
        raise ValueError('Image is unavailable')
    return {**meta, 'url': f'/api/attachments/{team}/{image_id}'}, resolved_path


def resolve(state: Path, team: str, ids: list) -> list[dict]:
    if not isinstance(ids, list) or len(ids) > 4 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Attach up to four different images')
    result = []
    for image_id in ids:
        meta, path = read(state, team, image_id)
        result.append({**meta, 'path': str(path)})
    return result
