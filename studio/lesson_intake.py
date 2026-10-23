"""Serial lesson preparation around the unchanged preservation engine."""
from pathlib import Path
import datetime
import hashlib
import json
import secrets
import subprocess
import sys
import threading
import urllib.parse

STUDIO = Path(__file__).resolve().parent
APP = STUDIO.parent / 'opencv-ready/candidate/app'
sys.path.insert(0, str(APP))
import server as backend
from prepare_worker import MAX_UPLOAD, parameters


class LessonManager(backend.Manager):
    def __init__(self, root):
        super().__init__(root)
        self.import_lock = threading.Lock()

    def uploaded_path(self, jid):
        archived = self.root / '.uploads' / (jid + '.bin')
        return archived if archived.is_file() else self.jobpath(jid) / 'uploaded-original.bin'

    def remove_upload(self, jid):
        self.jobpath(jid)  # validate before constructing the archive path
        (self.root / '.uploads' / (jid + '.bin')).unlink(missing_ok=True)

    def create_import(self, name, data, start, duration, owner=None):
        start, duration = parameters(start, duration)
        if not 0 < len(data) <= MAX_UPLOAD:
            raise ValueError('Choose a lesson file of at most 64 MiB.')
        # Reject playlists, URLs, images and unsupported containers before probe.
        if not (data[:4] == b'\x1aE\xdf\xa3' or len(data) >= 12 and data[4:8] == b'ftyp'):
            raise ValueError('Choose an MP4/MOV or WebM lesson file. Playlists and URLs are not accepted.')
        with self.lock:
            if len(self.jobs) >= 8 or sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()) + len(data) > 512 * 1024**2:
                raise backend.Conflict('Lesson capacity reached. Download your results and try again after expiry.')
            jid = secrets.token_hex(16)
            folder = self.root / jid
            folder.mkdir(mode=0o700)
            (folder / 'uploaded-original.bin').write_bytes(data)
            backend.write_json(folder / 'prepare-request.json', {'start_seconds': start, 'duration_seconds': duration,
                               'upload_sha256': hashlib.sha256(data).hexdigest()})
            if owner is not None:
                (folder / 'owner.txt').write_text(owner)
            self.jobs[jid] = {'id': jid, 'status': 'queued', 'input_name': backend.safe_name(name),
                              'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'preparing_lesson': True}
            self.save(jid)
            self.pool.submit(self.prepare_then_analyze, jid)
            return self.view(jid)

    def prepare_then_analyze(self, jid):
        proc = None
        try:
            with self.lock:
                if self.jobs[jid]['status'] == 'cancelled':
                    return
                folder = self.jobpath(jid)
                self.jobs[jid]['status'] = 'analyzing'
                self.save(jid)
                with (folder / 'prepare.log').open('wb') as log:
                    proc = subprocess.Popen([sys.executable, str(STUDIO / 'prepare_worker.py'), str(folder)],
                                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
                self.processes[jid] = proc
            try:
                code = proc.wait(timeout=105)
            finally:
                self.stop_process(proc)
                with self.lock:
                    self.processes.pop(jid, None)
            with self.lock:
                if self.jobs[jid]['status'] == 'cancelled':
                    return
            if code != 0:
                failure = backend.read_json(folder / 'prepare-error.json') if (folder / 'prepare-error.json').is_file() else {}
                raise ValueError(failure.get('error', 'Lesson preparation stopped; no edit was generated.'))
            receipt = backend.read_json(folder / 'preparation.json')
            if receipt['prepared_sha256'] != backend.sha(folder / 'input.mp4'):
                raise ValueError('Prepared lesson source changed.')
            archive = self.root / '.uploads'
            archive.mkdir(mode=0o700, exist_ok=True)
            (folder / 'uploaded-original.bin').replace(archive / (jid + '.bin'))
            with self.lock:
                self.jobs[jid]['preparing_lesson'] = False
                self.save(jid)
            super().run(jid, 'analyze')
        except BaseException as error:
            if proc is not None:
                self.stop_process(proc)
            with self.lock:
                self.processes.pop(jid, None)
                if self.jobs[jid]['status'] != 'cancelled':
                    self.jobs[jid].update(status='failed', error=str(error), preparing_lesson=False)
                    self.save(jid)

    def preparation(self, jid):
        folder = self.jobpath(jid)
        path = folder / 'preparation.json'
        if not path.is_file():
            return None
        receipt = json.loads(backend.bounded_regular_bytes(path, 32768))
        if receipt['prepared_sha256'] != backend.sha(folder / 'input.mp4') or receipt['uploaded_sha256'] != backend.sha(self.uploaded_path(jid)):
            raise ValueError('Lesson preparation/source identity changed.')
        return receipt

    def view(self, jid):
        out = super().view(jid)
        preparation = self.preparation(jid)
        if preparation:
            out['preparation'] = preparation
            if out['artifacts']:
                out['artifacts'] = {('Prepared lesson clip' if name in ('Original input', 'Original unchanged') else name): url
                                    for name, url in out['artifacts'].items()}
                out['artifacts']['Uploaded original'] = f'/api/jobs/{jid}/intake/upload'
                out['artifacts']['Preparation receipt'] = f'/api/jobs/{jid}/intake/receipt'
        return out


class LessonHandler(backend.Handler):
    def file(self, path, attachment=None):
        if path.parent == APP / 'static' and path.name in ('index.html', 'app.js', 'styles.css'):
            path = STUDIO / 'static' / path.name
        return super().file(path, attachment)

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != '/api/imports':
            return super().do_POST()
        try:
            self.secure(True)
            start, duration = parameters(self.headers.get('X-Clip-Start', '0'), self.headers.get('X-Clip-Duration', '12'))
            name = urllib.parse.unquote(self.headers.get('X-Filename', 'lesson.mp4'))
            with self.server.manager.import_lock:
                result = self.server.manager.create_import(name, self.body(MAX_UPLOAD), start, duration, getattr(self, 'session', None))
            return self.respond(202, result)
        except (ValueError, KeyError, PermissionError, OSError) as error:
            return self.handle_error(error)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        import re
        match = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/intake/(upload|receipt|preview)', path)
        if not match:
            return super().do_GET()
        try:
            self.secure()
            jid, role = match.groups()
            receipt = self.server.manager.preparation(jid)
            if not receipt:
                raise KeyError('Prepared lesson unavailable')
            folder = self.server.manager.jobpath(jid)
            if role == 'preview':
                return self.verified_image(folder / 'prepared-preview.png', receipt['preview_sha256'])
            data = backend.bounded_regular_bytes(self.server.manager.uploaded_path(jid), MAX_UPLOAD) if role == 'upload' else json.dumps(receipt, indent=2).encode()
            if role == 'upload' and hashlib.sha256(data).hexdigest() != receipt['uploaded_sha256']:
                raise ValueError('Uploaded source changed')
            self.send_response(200)
            self.headers_safe('application/octet-stream' if role == 'upload' else 'application/json', len(data),
                              'uploaded-original.bin' if role == 'upload' else 'preparation.json')
            self.wfile.write(data)
        except (ValueError, KeyError, PermissionError, OSError) as error:
            return self.handle_error(error)
