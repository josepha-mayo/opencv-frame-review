"""Source tampering, loopback routing and request controls; no media processing."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

STUDIO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_launcher', STUDIO / 'run.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class BuildSource(unittest.TestCase):
    def test_source_manifest_accepts_exact_bytes_and_rejects_missing_or_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'studio').mkdir()
            sample = root / 'owned.bin'
            sample.write_bytes(b'owned source')
            (root / 'studio/BUILD_HASHES.json').write_text(json.dumps({'build': 'test', 'files': {'owned.bin': hashlib.sha256(sample.read_bytes()).hexdigest()}}))
            self.assertEqual(launcher.check_source(root)['source_files_verified'], 1)
            sample.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'Changed build file'):
                launcher.check_source(root)
            sample.unlink()
            with self.assertRaisesRegex(RuntimeError, 'Missing build file'):
                launcher.check_source(root)

    def test_manifest_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'studio').mkdir()
            (root / 'studio/BUILD_HASHES.json').write_text(json.dumps({'files': {'../outside': '0' * 64}}))
            with self.assertRaisesRegex(RuntimeError, 'Invalid source manifest path'):
                launcher.check_source(root)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows refusal check')
    def test_windows_media_worker_refuses_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, 'requires Linux'):
            launcher.check_runtime()


class StudioHTTP(unittest.TestCase):
    def test_studio_assets_and_original_api_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            server = launcher.make_studio_server(0, Path(directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = 'http://127.0.0.1:' + str(server.server_address[1])
            try:
                for route, filename in (('/', 'index.html'), ('/static/app.js', 'app.js'), ('/static/styles.css', 'styles.css')):
                    with urllib.request.urlopen(url + route, timeout=3) as response:
                        self.assertEqual(response.read(), (STUDIO / 'static' / filename).read_bytes())
                        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
                        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
                with urllib.request.urlopen(url + '/api/profile', timeout=3) as response:
                    profile = json.load(response)
                    self.assertEqual(profile['duration_contract']['maximum_frames'], 360)
                for route in ('/../../CODEX_HANDOFF.md', '/static/profile.json'):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(url + route, timeout=3)
                    self.assertEqual(error.exception.code, 404)
                    error.exception.close()
                request = urllib.request.Request(url + '/api/jobs', data=b'unapproved', method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request, timeout=3)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
                self.assertEqual(server.manager.jobs, {})
            finally:
                server.shutdown()
                thread.join(3)
                server.manager.close()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
