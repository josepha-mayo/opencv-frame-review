"""Intake contract, ownership and source-reference checks, without media stubs claiming decode."""
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_worker import parameters, MAX_UPLOAD
from lesson_intake import LessonManager


class LessonIntake(unittest.TestCase):
    def test_excerpt_parameters_cannot_escape_bounded_finite_grid(self):
        for start, length in [('nan', 12), (0, 'inf'), (-1, 12), (601, 12), (0, .9), (0, 12.1), (0, 1.01)]:
            with self.assertRaises(ValueError):
                parameters(start, length)
        self.assertEqual(parameters('45.5', '12'), (45.5, 12))

    def test_unsupported_container_refuses_before_a_job_or_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                with patch.object(manager.pool, 'submit') as submit:
                    for data in (b'#EXTM3U\nhttps://example.com/video', b'http://example.com', b'\x89PNG\r\n', b''):
                        with self.assertRaises(ValueError):
                            manager.create_import('lesson', data, 0, 12, 'a' * 64)
                    submit.assert_not_called()
                self.assertEqual(manager.jobs, {})
            finally:
                manager.close()

    def test_upload_owner_and_hash_are_saved_before_queuing(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                data = b'\x1aE\xdf\xa3bounded-test-header'
                with patch.object(manager.pool, 'submit') as submit:
                    def inspect(*args):
                        jid = args[1]
                        folder = manager.jobpath(jid)
                        self.assertEqual((folder / 'owner.txt').read_text(), 'a' * 64)
                        request = json.loads((folder / 'prepare-request.json').read_text())
                        self.assertEqual(request['upload_sha256'], hashlib.sha256(data).hexdigest())
                        self.assertFalse((folder / 'approval.json').exists())
                    submit.side_effect = inspect
                    job = manager.create_import('lesson.webm', data, 5, 3, 'a' * 64)
                    self.assertTrue(job['preparing_lesson'])
                    self.assertEqual(job['status'], 'queued')
            finally:
                manager.close()

    @unittest.skipUnless(hasattr(os, 'O_NOFOLLOW'), 'Linux no-follow file checks')
    def test_prepared_reference_receipt_refuses_changed_source_or_original(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                with patch.object(manager.pool, 'submit'):
                    job = manager.create_import('lesson.webm', b'\x1aE\xdf\xa3test', 0, 3)
                folder = manager.jobpath(job['id'])
                (folder / 'input.mp4').write_bytes(b'prepared-test')
                receipt = {'prepared_sha256': hashlib.sha256(b'prepared-test').hexdigest(),
                           'uploaded_sha256': hashlib.sha256(b'\x1aE\xdf\xa3test').hexdigest()}
                (folder / 'preparation.json').write_text(json.dumps(receipt))
                self.assertEqual(manager.preparation(job['id']), receipt)
                (folder / 'input.mp4').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'identity changed'):
                    manager.preparation(job['id'])
                (folder / 'input.mp4').write_bytes(b'prepared-test')
                (folder / 'uploaded-original.bin').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'identity changed'):
                    manager.preparation(job['id'])
            finally:
                manager.close()
