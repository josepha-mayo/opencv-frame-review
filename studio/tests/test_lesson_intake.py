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
from lesson_intake import LessonManager, backend


class LessonIntake(unittest.TestCase):
    def test_prepared_lesson_requires_a_teaching_contract_before_planning(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                with patch.object(manager, 'preparation', return_value={'prepared_sha256': 'test'}), patch.object(backend.Manager, 'plan', return_value={'accepted': True}) as base:
                    for body in ({}, {'protected_regions': []}):
                        with self.assertRaisesRegex(ValueError, 'at least one teaching area'):
                            manager.plan('a' * 32, body)
                    base.assert_not_called()
                    body = {'protected_regions': [{'label': 'Equation', 'xywh': [0, 0, 100, 100]}]}
                    self.assertEqual(manager.plan('a' * 32, body), {'accepted': True})
                    base.assert_called_once_with('a' * 32, body)
                with patch.object(manager, 'preparation', return_value=None), patch.object(backend.Manager, 'plan', return_value={'canonical': True}):
                    self.assertEqual(manager.plan('a' * 32, {}), {'canonical': True})
            finally:
                manager.close()

    def test_decision_record_distinguishes_no_edit_from_no_distraction(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                jid = 'a' * 32
                manager.jobs[jid] = {'id': jid, 'status': 'review'}
                manager.jobpath(jid).mkdir()
                receipt = dict(uploaded_sha256='original', prepared_sha256='prepared', start_seconds=40,
                               duration_seconds=12, frames=360, source={'width': 1920}, prepared={'width': 640})
                job = dict(status='review', created_utc='test', candidates=[])
                with patch.object(manager, 'view', return_value=job), patch.object(manager, 'preparation', return_value=receipt):
                    with self.assertRaisesRegex(ValueError, 'Finish the review'):
                        manager.decision_record(jid)
                    job['status'] = 'declined'
                    result = manager.decision_record(jid)
                    self.assertFalse(result['edited_export_accepted'])
                    self.assertEqual(result['uploaded_sha256'], 'original')
                    self.assertEqual(result['prepared_sha256'], 'prepared')
                    self.assertIn('No candidate does not mean distraction-free or safe.', result['limitations'])
                    job.update(status='failed', error='No repeated cycle')
                    result = manager.decision_record(jid)
                    self.assertFalse(result['edited_export_accepted'])
                    self.assertEqual(result['failure_reason'], 'No repeated cycle')
                    self.assertIn('Retained sources', result['interpretation'])
                    job['status'] = 'declined'
                    (manager.jobpath(jid) / 'edited.mp4').write_bytes(b'unexpected')
                    with self.assertRaisesRegex(ValueError, 'Unexpected edited artifact'):
                        manager.decision_record(jid)
            finally:
                manager.close()

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
