"""Single-worker HTTPS-origin adapter for the qualified creator engine on ECS.

TLS terminates at the AWS load balancer. Media remains scoped to an opaque
HttpOnly browser cookie. The frozen engine and its resource limits are unchanged.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import http.cookies
import http.server
import json
import os
import re
import secrets
import shutil
import sys
import threading
import time
import urllib.parse

import run as studio
sys.path.insert(0, str(studio.APP))
import server as backend

COOKIE = 'creator_session'
RETENTION_SECONDS = 24 * 60 * 60


class CloudHandler(backend.Handler):
    def end_headers(self):
        if getattr(self, 'new_session', False):
            secure = '; Secure' if self.server.secure_cookie else ''
            self.send_header('Set-Cookie', f'{COOKIE}={self.session}; Path=/; HttpOnly; SameSite=Strict; Max-Age={RETENTION_SECONDS}{secure}')
            self.new_session = False
        super().end_headers()

    def secure(self, post=False):
        super().secure(post)
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except http.cookies.CookieError:
            cookie = http.cookies.SimpleCookie()
        value = cookie[COOKIE].value if COOKIE in cookie else ''
        self.new_session = not bool(re.fullmatch('[0-9a-f]{64}', value))
        self.session = secrets.token_hex(32) if self.new_session else value
        self.limit_requests(post)
        path = urllib.parse.urlsplit(self.path).path
        match = re.match(r'^/api/jobs/([0-9a-f]{32})(?:/|$)', path)
        if match:
            owner_file = self.server.manager.jobpath(match[1]) / 'owner.txt'
            if not owner_file.is_file() or not secrets.compare_digest(owner_file.read_text(), self.session):
                raise KeyError('Unknown job')

    def limit_requests(self, post):
        # ALB appends the actual remote client to X-Forwarded-For. Limit the
        # socket peer as a fallback, and keep the map bounded independently.
        peer = self.headers.get('X-Forwarded-For', '').split(',')[-1].strip() or self.client_address[0]
        if len(peer) > 80:
            raise ValueError('Invalid forwarded address')
        now = time.monotonic()
        with self.server.rate_lock:
            if len(self.server.rates) > 1000:
                self.server.rates = {key: value for key, value in self.server.rates.items() if now - value[0] < 60}
            if peer not in self.server.rates and len(self.server.rates) >= 1000:
                raise backend.Conflict('Demo request capacity reached. Try again shortly.')
            started, reads, writes = self.server.rates.get(peer, (now, 0, 0))
            if now - started >= 60:
                started, reads, writes = now, 0, 0
            reads += not post
            writes += post
            self.server.rates[peer] = (started, reads, writes)
            if reads > 180 or writes > 20:
                raise backend.Conflict('Demo request limit reached. Wait one minute before trying again.')

    def file(self, path, attachment=None):
        if path.parent == studio.APP / 'static' and path.name in ('index.html', 'app.js', 'styles.css'):
            path = studio.ROOT / 'static' / path.name
        return super().file(path, attachment)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/health':
            return self.respond(200, {'status': 'ready'})
        if path == '/api/deployment':
            try:
                self.secure()
                return self.respond(200, self.server.deployment)
            except (ValueError, KeyError, PermissionError, OSError) as error:
                return self.handle_error(error)
        if path in ('/api/samples/workshop.mp4', '/api/samples/lesson.mp4'):
            try:
                self.secure()
                sample = studio.ROOT / 'fixtures/lesson.mp4' if path.endswith('/lesson.mp4') else studio.BASE / 'candidate/fixtures/workshop-audio.mp4'
                data = sample.read_bytes()
                if hashlib.sha256(data).hexdigest() not in self.server.allowed_sources:
                    raise ValueError('The packaged lesson sample changed')
                self.send_response(200)
                self.headers_safe('video/mp4', len(data), 'synthetic-lesson.mp4')
                self.wfile.write(data)
                return
            except (ValueError, KeyError, PermissionError, OSError) as error:
                return self.handle_error(error)
        return super().do_GET()

    def respond(self, code, obj):
        if urllib.parse.urlsplit(self.path).path == '/api/profile' and code == 200:
            obj = dict(obj, transport={'kind': 'aws', 'retention_hours': 24,
                                     'message': 'AWS judge demo: bundled synthetic clips only. Uploads are processed on AWS. Jobs expire after 24 hours and a service restart can clear them sooner. Download results you want to keep. Use the local build for other media.'})
        return super().respond(code, obj)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path not in ('/api/jobs', '/api/demo'):
            return super().do_POST()
        try:
            self.secure(True)
            expire_jobs(self.server.manager)
            if path == '/api/demo':
                if self.body(1024) not in (b'{}', b''):
                    raise ValueError('The demonstration takes no custom parameters')
                data = (studio.ROOT / 'fixtures/lesson.mp4').read_bytes()
                filename = 'graph-a-line-lesson.mp4'
            else:
                data = self.body(backend.MAX_INPUT)
                filename = urllib.parse.unquote(self.headers.get('X-Filename', 'input.mp4'))
            if hashlib.sha256(data).hexdigest() not in self.server.allowed_sources:
                raise ValueError('This public demo accepts only the bundled synthetic clips. Download the lesson sample below, then select it for analysis. Use the local build for other media.')
            # Retain the existing one-worker, eight-job and aggregate-disk caps.
            result = self.server.manager.create(filename, data)
            (self.server.manager.jobpath(result['id']) / 'owner.txt').write_text(self.session)
            return self.respond(202, result)
        except (ValueError, KeyError, PermissionError, OSError) as error:
            return self.handle_error(error)


def expire_jobs(manager, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    with manager.lock:
        for jid, job in list(manager.jobs.items()):
            if job['status'] in backend.ACTIVE:
                continue
            created = datetime.datetime.fromisoformat(job['created_utc'])
            if (now - created).total_seconds() <= RETENTION_SECONDS:
                continue
            path = manager.jobpath(jid).resolve()
            if path.parent != manager.root or not re.fullmatch('[0-9a-f]{32}', path.name):
                raise RuntimeError('Unexpected expired-job path')
            shutil.rmtree(path)
            del manager.jobs[jid]


def make_cloud_server(hosts, port, data_dir, *, bind='0.0.0.0', secure_cookie=True):
    if not hosts or any(not re.fullmatch(r'[a-zA-Z0-9.-]+(?::[0-9]+)?', host) for host in hosts):
        raise ValueError('Explicit public host names are required')
    manager = backend.Manager(data_dir)
    try:
        server = http.server.ThreadingHTTPServer((bind, port), CloudHandler)
    except BaseException:
        manager.close()
        raise
    server.daemon_threads = True
    server.manager = manager
    server.csrf_token = secrets.token_hex(32)
    server.allowed_hosts = set(hosts)
    server.allowed_origins = {'https://' + host for host in hosts}
    if not secure_cookie:
        if bind != '127.0.0.1':
            server.server_close()
            manager.close()
            raise ValueError('Non-secure cookies are restricted to loopback tests')
        server.allowed_origins.update('http://' + host for host in hosts)
    server.secure_cookie = secure_cookie
    server.rates = {}
    server.rate_lock = threading.Lock()
    identity = studio.check_source()
    manifest = json.loads((studio.ROOT / 'BUILD_HASHES.json').read_text(encoding='utf-8'))
    server.allowed_sources = {digest for path, digest in manifest['files'].items()
                              if path.startswith(('opencv-ready/candidate/fixtures/', 'studio/fixtures/')) and path.endswith('.mp4')}
    server.deployment = {'build': identity['build'], 'source_files_verified': identity['source_files_verified'],
                         'source_manifest_sha256': hashlib.sha256((studio.ROOT / 'BUILD_HASHES.json').read_bytes()).hexdigest(),
                         'hosting': 'Amazon ECS', 'analysis': 'OpenCV 5.0.0', 'media_runtime': 'Pinned Debian FFmpeg 7.1.5',
                         'retention_hours': 24, 'workers': 1, 'max_jobs': 8}
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--hosts', default=os.environ.get('PUBLIC_HOSTS', ''))
    parser.add_argument('--data-dir', type=Path, default=Path('/tmp/creator-jobs'))
    args = parser.parse_args()
    studio.check_source()
    studio.check_runtime()
    server = make_cloud_server([host.strip() for host in args.hosts.split(',') if host.strip()], args.port, args.data_dir)
    stop_cleanup = threading.Event()
    def cleanup():
        while not stop_cleanup.wait(30):
            try:
                expire_jobs(server.manager)
            except (OSError, ValueError, KeyError) as error:
                print('Retention cleanup failed: ' + type(error).__name__, flush=True)
    cleaner = threading.Thread(target=cleanup, daemon=True)
    cleaner.start()
    print(json.dumps({'listening': args.port, 'hosts': sorted(server.allowed_hosts), **server.deployment}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_cleanup.set()
        cleaner.join(3)
        server.manager.close()
        server.server_close()


if __name__ == '__main__':
    main()
