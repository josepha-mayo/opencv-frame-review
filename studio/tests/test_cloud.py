"""Real HTTP ownership, origin, retention and deployment identity checks."""
from pathlib import Path
import datetime
import hashlib
import http.client
import importlib.util
import json
import sys
import tempfile
import threading
import unittest

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))
import cloud_server
from common import write_json


class CloudHTTP(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = cloud_server.make_cloud_server(['demo.example'], 0, Path(self.temp.name), bind='127.0.0.1')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(3)
        self.server.manager.close()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, *, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=3)
        connection.request(method, path, body=body, headers={'Host': 'demo.example', **(headers or {})})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def seed(self, owner, age_hours=0, status='declined'):
        jid = 'a' * 32
        path = self.server.manager.root / jid
        path.mkdir()
        now = datetime.datetime.now(datetime.timezone.utc)
        job = {'id': jid, 'status': status, 'created_utc': (now - datetime.timedelta(hours=age_hours)).isoformat()}
        self.server.manager.jobs[jid] = job
        write_json(path / 'job.json', job)
        (path / 'owner.txt').write_text(owner)
        return jid, path

    def test_cookie_private_attributes_and_visible_aws_transport(self):
        status, headers, body = self.request('/api/profile')
        self.assertEqual(status, 200)
        for attribute in ('HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/'):
            self.assertIn(attribute, headers['Set-Cookie'])
        value = json.loads(body)
        self.assertEqual(value['transport']['kind'], 'aws')
        self.assertEqual(value['transport']['retention_hours'], 24)

    def test_job_cannot_be_read_by_another_browser_even_with_known_job_id(self):
        owner = 'b' * 64
        jid, path = self.seed(owner)
        for cookie in ('', 'creator_session=' + 'c' * 64):
            status, _, _ = self.request('/api/jobs/' + jid, headers={'Cookie': cookie})
            self.assertEqual(status, 404)
        status, _, body = self.request('/api/jobs/' + jid, headers={'Cookie': 'creator_session=' + owner})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['status'], 'declined')
        status, _, _ = self.request('/api/jobs/' + jid + '/download/original.mp4', headers={'Cookie': 'creator_session=' + 'c' * 64})
        self.assertEqual(status, 404)

    def test_cross_origin_wrong_host_and_missing_csrf_refuse_without_job(self):
        self.assertEqual(self.request('/api/profile', headers={'Host': 'attacker.example'})[0], 400)
        self.assertEqual(self.request('/api/profile', headers={'Origin': 'https://attacker.example'})[0], 400)
        self.assertEqual(self.request('/api/jobs', method='POST', body=b'not approved')[0], 403)
        self.assertEqual(self.server.manager.jobs, {})

    def test_health_has_no_job_data_and_deployment_has_source_identity(self):
        self.assertEqual(json.loads(self.request('/health')[2]), {'status': 'ready'})
        deployment = json.loads(self.request('/api/deployment')[2])
        self.assertEqual(deployment['hosting'], 'Amazon ECS')
        self.assertEqual(deployment['workers'], 1)
        self.assertGreater(deployment['source_files_verified'], 70)

    def test_sample_download_is_exact_and_unrecognized_upload_never_starts_worker(self):
        status, headers, body = self.request('/api/samples/workshop.mp4')
        self.assertEqual(status, 200)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertIn(hashlib.sha256(body).hexdigest(), self.server.allowed_sources)
        status, _, lesson = self.request('/api/samples/lesson.mp4')
        self.assertEqual(status, 200)
        self.assertIn(hashlib.sha256(lesson).hexdigest(), self.server.allowed_sources)
        status, headers, body = self.request('/api/profile')
        token = json.loads(body)['csrf_token']
        status, _, body = self.request('/api/jobs', method='POST', body=b'unrecognized arbitrary media',
                                      headers={'X-App-Token': token, 'Cookie': headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(status, 400)
        self.assertIn('bundled synthetic', json.loads(body)['error'])
        self.assertEqual(self.server.manager.jobs, {})

    def test_demo_requires_request_token_and_creates_only_packaged_source(self):
        self.assertEqual(self.request('/api/demo', method='POST', body=b'{}')[0], 403)
        _, headers, body = self.request('/api/profile')
        token = json.loads(body)['csrf_token']
        cookie = headers['Set-Cookie'].split(';')[0]
        seen = []
        def create(filename, data):
            seen.append((filename, hashlib.sha256(data).hexdigest()))
            jid, _ = self.seed('', status='review')
            return self.server.manager.jobs[jid]
        self.server.manager.create = create
        status, _, body = self.request('/api/demo', method='POST', body=b'{}', headers={'X-App-Token':token, 'Cookie':cookie})
        self.assertEqual(status, 202)
        self.assertEqual(seen[0][0], 'graph-a-line-lesson.mp4')
        self.assertIn(seen[0][1], self.server.allowed_sources)
        self.assertEqual(json.loads(body)['status'], 'review')
        self.assertEqual(self.request('/api/jobs/'+'a'*32, headers={'Cookie':cookie})[0], 200)

    def test_retention_removes_expired_review_but_never_running_worker(self):
        jid, path = self.seed('b' * 64, age_hours=25, status='review')
        cloud_server.expire_jobs(self.server.manager)
        self.assertFalse(path.exists())
        self.assertNotIn(jid, self.server.manager.jobs)
        jid, path = self.seed('b' * 64, age_hours=25, status='exporting')
        cloud_server.expire_jobs(self.server.manager)
        self.assertTrue(path.exists())
        # No worker was spawned by this controlled lifecycle fixture.
        self.server.manager.jobs[jid]['status'] = 'failed'

    def test_insecure_cookie_mode_cannot_bind_public_interface(self):
        with self.assertRaisesRegex(ValueError, 'loopback tests'):
            cloud_server.make_cloud_server(['demo.example'], 0, Path(self.temp.name) / 'other', secure_cookie=False)


if __name__ == '__main__':
    unittest.main()
