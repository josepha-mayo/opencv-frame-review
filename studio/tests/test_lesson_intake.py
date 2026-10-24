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
from prepare_worker import parameters, MAX_UPLOAD, lesson_tracks, publish_receipt
from lesson_intake import LessonManager, backend, original_download


class LessonIntake(unittest.TestCase):
    def test_polling_cannot_observe_an_incomplete_preparation_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'preparation.json';value={'frames':360,'prepared_sha256':'a'*64}
            real_replace=os.replace
            def publish(pending,destination):
                self.assertFalse(target.exists())
                self.assertEqual(json.loads(Path(pending).read_text()),value)
                real_replace(pending,destination)
            with patch('prepare_worker.os.replace',side_effect=publish)as replace:
                publish_receipt(target,value);replace.assert_called_once()
            self.assertEqual(json.loads(target.read_text()),value)
            with patch('prepare_worker.os.replace',side_effect=OSError('publication interrupted')):
                with self.assertRaises(OSError):publish_receipt(target,{'frames':1})
            self.assertEqual(json.loads(target.read_text()),value)
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_original_download_uses_container_bytes_for_a_playable_suffix(self):
        for data,expected in [(b'OggSsource',('video/ogg','uploaded-original.ogv')),
                              (b'\x1aE\xdf\xa3\x42\x82\x84webm',('video/webm','uploaded-original.webm')),
                              (b'\x1aE\xdf\xa3matroska',('video/x-matroska','uploaded-original.mkv')),
                              (b'\x00\x00\x00\x18ftypisom',('video/mp4','uploaded-original.mp4')),
                              (b'\x00\x00\x00\x18ftypqt  ',('video/quicktime','uploaded-original.mov'))]:
            self.assertEqual(original_download(data),expected)
        with self.assertRaises(ValueError):original_download(b'not a supported original')

    def test_ogg_skeleton_versions_are_metadata_without_discarding_lesson_tracks(self):
        video={'index':1,'codec_type':'video','codec_name':'theora'}
        audio={'index':2,'codec_type':'audio','codec_name':'vorbis'}
        metadata={'format':{'format_name':'ogg'},'streams':[{'index':0,'codec_type':'data'},video,audio]}
        for version,length in ((3,64),(4,80)):
            header=b'OggS\x00\x02'+b'\x00'*20+bytes([1,length])+b'fishead\x00'+version.to_bytes(2,'little')+b'\x00'*(length-10)
            self.assertEqual(lesson_tracks(metadata,header),(video,[audio],True))

    def test_skeleton_exception_cannot_hide_subtitles_unknown_data_or_other_containers(self):
        video={'index':1,'codec_type':'video','codec_name':'theora'}
        data={'index':0,'codec_type':'data'}
        header=b'OggS\x00\x02'+b'\x00'*20+bytes([1,64])+b'fishead\x00'+b'\x03\x00'+b'\x00'*54
        for metadata,h in [
            ({'format':{'format_name':'mov'},'streams':[data,video]},header),
            ({'format':{'format_name':'ogg'},'streams':[data,video,{'codec_type':'subtitle'}]},header),
            ({'format':{'format_name':'ogg'},'streams':[data,video]},header[:40]),
            ({'format':{'format_name':'ogg'},'streams':[data,video]},header.replace(b'fishead',b'unknown')),
            ({'format':{'format_name':'ogg'},'streams':[{'index':3,'codec_type':'data'},video]},header),
            ({'format':{'format_name':'ogg'},'streams':[{'index':0,'codec_type':'subtitle'},video]},header)]:
            with self.assertRaises(ValueError):lesson_tracks(metadata,h)

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
                    backend.write_json(manager.jobpath(jid)/'result.json', {'schema':'steady-detail-export-v1','acceptance':{'status':'rejected_experiment'},'encoded_boundary_checks':{'passed':False}})
                    result = manager.decision_record(jid)
                    self.assertFalse(result['encoded_export_measurements']['encoded_boundary_checks']['passed'])
                    self.assertFalse(result['edited_export_accepted'])
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

    def test_ogg_original_is_queued_without_approval_and_retains_exact_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LessonManager(directory)
            try:
                data = b'OggS\x00bounded-test-header'
                with patch.object(manager.pool, 'submit') as submit:
                    job = manager.create_import('drawing.ogv', data, 0, 3, 'a' * 64)
                    submit.assert_called_once()
                folder = manager.jobpath(job['id'])
                self.assertEqual(job['status'], 'queued')
                self.assertEqual((folder/'uploaded-original.bin').read_bytes(), data)
                self.assertEqual((folder/'owner.txt').read_text(), 'a' * 64)
                self.assertFalse((folder/'approval.json').exists())
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
