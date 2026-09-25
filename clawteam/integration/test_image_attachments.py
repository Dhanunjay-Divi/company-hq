from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import hq_api
import image_attachments
from codex_bridge import _turn_input, _user_message
from image_attachments import read, resolve, upload


PNG = b'\x89PNG\r\n\x1a\n' + b'fixture-png'
JPEG = b'\xff\xd8\xff\xe0' + b'fixture-jpeg'
WEBP = b'RIFF\x0c\x00\x00\x00WEBPVP8 ' + b'fixture-webp'


def body(name='screen.png', mime='image/png', data=PNG):
    return {
        'name': name,
        'mimeType': mime,
        'dataBase64': base64.b64encode(data).decode('ascii'),
    }


class ImageAttachmentsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='company-hq-images-')
        self.state = Path(self.temporary.name) / 'state'
        self.state.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_upload_round_trip_uses_content_extension_and_private_files(self):
        for team, mime, data, extension in (
            ('chat-png', 'image/png', PNG, '.png'),
            ('chat-jpeg', 'image/jpeg', JPEG, '.jpg'),
            ('chat-webp', 'image/webp', WEBP, '.webp'),
        ):
            with self.subTest(mime=mime):
                saved = upload(self.state, team, body(mime=mime, data=data))
                meta, path = read(self.state, team, saved['id'])
                self.assertEqual(path.suffix, extension)
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(meta['mimeType'], mime)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                metadata_path = path.parent / f"{saved['id']}.json"
                self.assertEqual(stat.S_IMODE(metadata_path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(path.parent.parent.stat().st_mode), 0o700)

    def test_validated_legacy_image_remains_readable_and_counts_toward_cap(self):
        team = 'image-attachments-check-09b07c'
        saved = upload(self.state, team, body())
        _, canonical_path = read(self.state, team, saved['id'])
        legacy_path = canonical_path.with_suffix('.image')
        canonical_path.rename(legacy_path)

        meta, restored_path = read(self.state, team, saved['id'])
        self.assertEqual(meta['id'], saved['id'])
        self.assertEqual(restored_path, legacy_path.resolve())
        self.assertEqual(restored_path.read_bytes(), PNG)
        self.assertEqual(resolve(self.state, team, [saved['id']])[0]['path'], str(legacy_path.resolve()))

        with patch.object(image_attachments, 'MAX_CHAT_BYTES', len(PNG)):
            with self.assertRaisesRegex(ValueError, 'storage allowance'):
                upload(self.state, team, body('second.png'))

    def test_rejects_malformed_base64_body_mime_and_size(self):
        invalid_bodies = (
            None,
            {},
            {'name': 'x.png', 'mimeType': 'image/png', 'dataBase64': '***'},
            body(mime='image/jpeg', data=PNG),
            body(mime='text/html', data=PNG),
            body(data=b''),
        )
        for invalid in invalid_bodies:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    upload(self.state, 'chat-one', invalid)

        with patch.object(image_attachments, 'MAX_IMAGE_BYTES', len(PNG) - 1):
            with self.assertRaisesRegex(ValueError, '6 MB or smaller|size limit'):
                upload(self.state, 'chat-one', body())

    def test_filename_is_basename_only_and_empty_basename_is_rejected(self):
        saved = upload(self.state, 'chat-one', body('../../private/screen.png'))
        self.assertEqual(saved['name'], 'screen.png')
        metadata = json.loads((self.state / 'images' / 'chat-one' / f"{saved['id']}.json").read_text())
        self.assertEqual(metadata['name'], 'screen.png')
        self.assertNotIn('private', json.dumps(saved))
        for unsafe in ('/', '..', 'bad\x7fname.png', 'bad\nname.png'):
            with self.subTest(name=unsafe), self.assertRaisesRegex(ValueError, 'filename'):
                upload(self.state, 'chat-one', body(unsafe))

    def test_chat_and_image_identifiers_cannot_traverse_or_cross_chats(self):
        saved = upload(self.state, 'chat-one', body())
        for team in ('../chat-one', 'chat/one', '', '-chat', 'a' * 129):
            with self.subTest(team=team), self.assertRaises(ValueError):
                read(self.state, team, saved['id'])
        for image_id in ('../' + saved['id'], saved['id'] + '.png', '', 'g' * 32):
            with self.subTest(image_id=image_id), self.assertRaises(ValueError):
                read(self.state, 'chat-one', image_id)
        with self.assertRaisesRegex(ValueError, 'not found'):
            read(self.state, 'chat-two', saved['id'])

    def test_symlinked_storage_and_files_are_rejected(self):
        outside = Path(self.temporary.name) / 'outside'
        outside.mkdir()
        symlink_state = Path(self.temporary.name) / 'symlink-state'
        symlink_state.mkdir()
        os.symlink(outside, symlink_state / 'images')
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            upload(symlink_state, 'chat-one', body())

        saved = upload(self.state, 'chat-one', body())
        _, image_path = read(self.state, 'chat-one', saved['id'])
        private = outside / 'private.png'
        private.write_bytes(PNG)
        image_path.unlink()
        os.symlink(private, image_path)
        with self.assertRaisesRegex(ValueError, 'not found'):
            read(self.state, 'chat-one', saved['id'])

    def test_storage_failures_do_not_expose_private_state_paths(self):
        blocked_state = Path(self.temporary.name) / 'blocked-state'
        blocked_state.mkdir()
        (blocked_state / 'images').write_text('not a directory')
        with self.assertRaisesRegex(ValueError, '^Image storage is unavailable$') as failure:
            upload(blocked_state, 'chat-one', body())
        self.assertNotIn(str(blocked_state), str(failure.exception))

        private_path = self.state / 'images' / 'chat-one' / 'private-file.png'
        with patch.object(image_attachments.os, 'open', side_effect=OSError(f'cannot write {private_path}')):
            with self.assertRaisesRegex(ValueError, '^Image storage is unavailable$') as failure:
                upload(self.state, 'chat-one', body())
        self.assertNotIn(str(private_path), str(failure.exception))

    def test_chat_storage_allowance_is_enforced_before_writing(self):
        with patch.object(image_attachments, 'MAX_CHAT_BYTES', len(PNG)):
            first = upload(self.state, 'chat-one', body())
            with self.assertRaisesRegex(ValueError, 'storage allowance'):
                upload(self.state, 'chat-one', body('second.png'))
        files = list((self.state / 'images' / 'chat-one').iterdir())
        self.assertEqual(len(files), 2)
        self.assertEqual(read(self.state, 'chat-one', first['id'])[0]['size'], len(PNG))

    def test_resolve_accepts_only_four_unique_ids_and_never_client_paths(self):
        ids = [upload(self.state, 'chat-one', body(f'{number}.png'))['id'] for number in range(4)]
        resolved = resolve(self.state, 'chat-one', ids)
        self.assertEqual([item['id'] for item in resolved], ids)
        expected_directory = (self.state / 'images' / 'chat-one').resolve()
        self.assertTrue(all(Path(item['path']).parent == expected_directory for item in resolved))
        for invalid in (ids + [ids[0]], [ids[0], ids[0]], [{'path': '/etc/passwd'}], '/etc/passwd'):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'four different images'):
                resolve(self.state, 'chat-one', invalid)

    def test_tampered_metadata_or_content_is_not_resolved(self):
        saved = upload(self.state, 'chat-one', body())
        directory = self.state / 'images' / 'chat-one'
        metadata_path = directory / f"{saved['id']}.json"
        metadata = json.loads(metadata_path.read_text())
        metadata['id'] = '0' * 32
        metadata_path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            read(self.state, 'chat-one', saved['id'])

    def test_runtime_route_uses_only_server_resolved_chat_attachments(self):
        class Handler:
            response = None
            error = None

            def _serve_json(self, value):
                self.response = value

            def _json_error(self, status, message):
                self.error = (status, message)

        class Bridge:
            sent = None

            def status(self, team):
                return {"provider":"codex", "model":"gpt-fixture"}

            def send(self, *args, **kwargs):
                self.sent = (args, kwargs)
                return {'accepted': True}

        bridge = Bridge()
        server_attachment = {
            'id': 'a' * 32,
            'name': 'screen.png',
            'mimeType': 'image/png',
            'size': len(PNG),
            'url': '/api/attachments/chat-one/' + 'a' * 32,
            'path': str((self.state / 'images' / 'chat-one' / ('a' * 32 + '.png')).resolve()),
        }
        handler = Handler()
        with patch.object(hq_api, 'routing_service'), patch.object(hq_api, 'bridge', return_value=bridge), patch.object(
            hq_api, 'project_for', return_value='/managed/chat-one',
        ), patch.object(hq_api, 'demo_mode', return_value=False), patch.object(
            image_attachments, 'resolve', return_value=[server_attachment],
        ) as resolver:
            hq_api.handle_post(handler, self.state, '/api/runtime/chat-one/send', {
                'prompt': 'Review this image',
                'attachmentIds': ['a' * 32],
                'attachments': [{'path': '/etc/passwd'}],
                'path': '/private/arbitrary',
            })
        self.assertIsNone(handler.error)
        self.assertEqual(handler.response, {'accepted': True})
        resolver.assert_called_once_with(self.state, 'chat-one', ['a' * 32])
        self.assertEqual(bridge.sent[0], ('chat-one', 'Review this image'))
        self.assertEqual(bridge.sent[1], {'attachments': [server_attachment]})

    def test_bridge_input_gets_local_path_but_user_event_gets_safe_metadata_only(self):
        attachment = {
            'id': 'a' * 32,
            'name': 'screen.png',
            'mimeType': 'image/png',
            'size': len(PNG),
            'url': '/api/attachments/chat-one/' + 'a' * 32,
            'path': '/private/company-hq-state/images/chat-one/private.png',
            'dataBase64': base64.b64encode(PNG).decode('ascii'),
        }
        native_input = _turn_input('Review this image', [attachment])
        self.assertEqual(native_input[1], {'type': 'localImage', 'path': attachment['path']})
        event = _user_message('Review this image', [attachment])
        self.assertEqual(event['attachments'], [{
            'id': attachment['id'],
            'name': attachment['name'],
            'url': attachment['url'],
        }])
        serialized = json.dumps(event)
        self.assertNotIn('/private/company-hq-state', serialized)
        self.assertNotIn(attachment['dataBase64'], serialized)


if __name__ == '__main__':
    unittest.main()
