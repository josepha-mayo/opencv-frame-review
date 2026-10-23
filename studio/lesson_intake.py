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
import steady_detail
from protected_regions import validate_regions

NATURAL_EXAMPLES = {'terminal': ('natural-terminal.mp4', 'NATURAL_TERMINAL_CREDIT.json'),
                    'jupyter': ('natural-jupyter.mp4', 'NATURAL_JUPYTER_CREDIT.json'),
                    'npm': ('natural-npm.mp4', 'NATURAL_NPM_CREDIT.json')}


class LessonManager(backend.Manager):
    def __init__(self, root):
        super().__init__(root)
        self.import_lock = threading.Lock()

    def natural_demo(self, owner=None, example='terminal'):
        if not isinstance(example, str) or example not in NATURAL_EXAMPLES:
            raise ValueError('Choose an available natural lesson example.')
        filename, credit_name = NATURAL_EXAMPLES[example]
        credit = backend.read_json(STUDIO/'fixtures'/credit_name)
        data = backend.bounded_regular_bytes(STUDIO/'fixtures'/filename,8*1024**2)
        if hashlib.sha256(data).hexdigest() != credit['prepared_sample_sha256']:
            raise ValueError('Natural lesson sample changed.')
        with self.lock:
            result = self.create('natural-'+example+'-prepared-excerpt.mp4',data)
            folder = self.jobpath(result['id'])
            if owner is not None:
                (folder/'owner.txt').write_text(owner)
            backend.write_json(folder/'sample-credit.json',credit)
            return self.view(result['id'])

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
            self.run(jid, 'analyze')
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

    def plan(self, jid, body):
        # A prepared lesson must declare the teaching it is trying to preserve.
        # This is a human preservation contract, never semantic recognition.
        with self.lock:
            if self.preparation(jid) and not body.get('protected_regions'):
                raise ValueError('Mark at least one teaching area before planning an edit to a prepared lesson. If the candidate is teaching content, leave it unchanged.')
            if str(body.get('candidate_id','')).startswith('steady-') or body.get('export_mode') == steady_detail.MODE:
                folder = self.jobpath(jid)
                if self.jobs[jid]['status'] != 'review':
                    raise backend.Conflict('This job is not awaiting review.')
                return steady_detail.plan(folder,backend.read_json(folder/'analysis.json'),
                                          backend.read_json(folder/'steady-analysis.json'),body,backend.sha,validate_regions)
            return super().plan(jid, body)

    def approve(self, jid, body):
        if not (str(body.get('candidate_id','')).startswith('steady-') or body.get('export_mode') == steady_detail.MODE):
            return super().approve(jid, body)
        with self.lock:
            if body.get('approve') is not True:
                raise ValueError('Explicit approval is required.')
            plan = self.plan(jid,body)
            if body.get('recipe_sha256') != plan['recipe_sha256']:
                raise backend.Conflict('Steady detail or teaching areas changed; review the plan again.')
            backend.write_json(self.jobpath(jid)/'approval.json',dict(plan,approve=True,approved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
            self.jobs[jid]['status'] = 'queued'
            self.save(jid)
            self.pool.submit(self.run,jid,'export')
            return self.view(jid)

    def run(self, jid, mode):
        folder = self.jobpath(jid)
        is_steady = mode == 'export' and (folder/'approval.json').is_file() and backend.read_json(folder/'approval.json').get('export_mode') == steady_detail.MODE
        if is_steady or mode == 'analyze':
            from steady_jobs import run
            return run(self,jid,mode,backend,STUDIO)
        return super().run(jid,mode)

    def decision_record(self, jid):
        with self.lock:
            job = self.view(jid)
            if job['status'] not in ('declined', 'complete', 'failed'):
                raise backend.Conflict('Finish the review before downloading its decision record.')
            receipt = self.preparation(jid)
            if not receipt:
                raise KeyError('Prepared lesson unavailable')
            if job['status'] == 'declined' and (self.jobpath(jid) / 'edited.mp4').exists():
                raise ValueError('Unexpected edited artifact in an unchanged lesson.')
            return {'schema': 'lesson-decision-v1', 'job_id': jid,
                    'created_utc': job['created_utc'], 'decision': job['status'],
                    'uploaded_sha256': receipt['uploaded_sha256'],
                    'prepared_sha256': receipt['prepared_sha256'],
                    'excerpt': {k: receipt[k] for k in ('start_seconds', 'duration_seconds', 'frames')},
                    'source': receipt['source'], 'prepared': receipt['prepared'],
                    'candidates': [{k: c[k] for k in ('id', 'bbox', 'interval_frames', 'pixels')} for c in job['candidates']],
                    'edited_export_accepted': job['status'] == 'complete',
                    'failure_reason': job.get('error') if job['status'] == 'failed' else None,
                    'interpretation': ('Processing failed; no edited export was accepted. Retained sources are available.' if job['status'] == 'failed' else 'Creator left the prepared clip unchanged; no edit was approved.' if job['status'] == 'declined' else 'Creator approved one bounded edit; read the encoded report for its measurements.'),
                    'detector_scope': 'Frozen rapid-change detector: at least 7 alternating luminance transitions in a rolling second, connected support at least 64 pixels. Separate steady-detail-v1: small stationary two-state luma appearance, at least 6 transitions, bounded state and chroma errors, minimum dwell. Proposals are not semantic distraction labels.',
                    'limitations': ['No candidate does not mean distraction-free or safe.',
                                    'Ordinary caret blinking, notifications and camera movement may be outside this detector.',
                                    'Preparation changes picture/audio and may make small teaching labels unreadable.',
                                    'Exact edit measurements reference the prepared clip, not the uploaded original.',
                                    'This record does not establish learning benefit or accessibility compliance.']}

    def view(self, jid):
        out = super().view(jid)
        folder = self.jobpath(jid)
        if (folder/'sample-credit.json').is_file():
            out['sample_credit'] = backend.read_json(folder/'sample-credit.json')
        if (folder/'steady-analysis.json').is_file() and (folder/'analysis.json').is_file():
            detection = backend.read_json(folder/'steady-analysis.json')
            for item in detection['candidates']:
                candidate = dict(item)
                candidate['recipe_sha256'] = hashlib.sha256(steady_detail.canonical(item)).hexdigest()
                candidate['overlay_url'] = f'/api/jobs/{jid}/steady/{item["id"]}-reference.png'
                candidate['alternate_url'] = f'/api/jobs/{jid}/steady/{item["id"]}-alternate.png'
                out['candidates'].append(candidate)
        preparation = self.preparation(jid)
        if preparation:
            out['preparation'] = preparation
            if out['artifacts'] or out['status'] == 'failed':
                out['artifacts'] = {('Prepared lesson clip' if name in ('Original input', 'Original unchanged') else name): url
                                    for name, url in out['artifacts'].items()}
                if out['status'] == 'failed':
                    out['artifacts']['Prepared lesson clip'] = f'/api/jobs/{jid}/intake/prepared'
                out['artifacts']['Uploaded original'] = f'/api/jobs/{jid}/intake/upload'
                out['artifacts']['Preparation receipt'] = f'/api/jobs/{jid}/intake/receipt'
                out['artifacts']['Lesson decision record'] = f'/api/jobs/{jid}/intake/decision'
        if out.get('sample_credit') and out['artifacts']:
            example = out['sample_credit'].get('id', 'terminal')
            if example not in NATURAL_EXAMPLES:
                raise ValueError('Natural lesson provenance identity changed.')
            out['artifacts']['Natural sample provenance'] = '/api/samples/natural-'+example+'-credit.json'
        return out


class LessonHandler(backend.Handler):
    def headers_safe(self, ctype, length, attachment=None):
        if ctype.startswith('text/') or ctype in ('application/javascript', 'application/x-javascript'):
            ctype += '; charset=utf-8'
        return super().headers_safe(ctype, length, attachment)

    def file(self, path, attachment=None):
        if path.parent == APP / 'static' and path.name in ('index.html', 'app.js', 'styles.css'):
            path = STUDIO / 'static' / path.name
        return super().file(path, attachment)

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path == '/api/natural-demo':
            try:
                self.secure(True)
                payload = json.loads(self.body(1024) or b'{}')
                if not isinstance(payload, dict) or set(payload)-{'example'}:
                    raise ValueError('Choose an available natural lesson example.')
                return self.respond(202,self.server.manager.natural_demo(getattr(self,'session',None),payload.get('example','terminal')))
            except (ValueError,KeyError,PermissionError,OSError) as error:
                return self.handle_error(error)
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
        samples = {'/api/samples/natural-terminal.mp4':('fixtures/natural-terminal.mp4','video/mp4','natural-terminal-prepared-excerpt.mp4'),
                   '/api/samples/natural-terminal.png':('static/natural-terminal.png','image/png',None),
                   '/api/samples/natural-terminal-credit.json':('fixtures/NATURAL_TERMINAL_CREDIT.json','application/json','natural-terminal-provenance.json')}
        for example in ('jupyter', 'npm'):
            filename, credit = NATURAL_EXAMPLES[example]
            samples['/api/samples/'+filename] = ('fixtures/'+filename,'video/mp4',filename)
            samples['/api/samples/natural-'+example+'-credit.json'] = ('fixtures/'+credit,'application/json','natural-'+example+'-provenance.json')
        if path == '/static/natural-terminal.png':
            path = '/api/samples/natural-terminal.png'
        if path in samples:
            try:
                self.secure()
                name,kind,attachment = samples[path]
                expected = backend.read_json(STUDIO/'BUILD_HASHES.json')['files']['studio/'+name]
                data = backend.bounded_regular_bytes(STUDIO/name,8*1024**2)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError('Natural lesson asset changed.')
                self.send_response(200);self.headers_safe(kind,len(data),attachment);self.wfile.write(data)
                return
            except (ValueError,KeyError,PermissionError,OSError) as error:
                return self.handle_error(error)
        steady_match = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/steady/(steady-[0-7]-(?:reference|alternate)\.png)',path)
        if steady_match:
            try:
                self.secure()
                jid, name = steady_match.groups()
                folder = self.server.manager.jobpath(jid)
                previews = backend.read_json(folder/'steady-previews.json')
                if name not in previews:
                    raise KeyError('Steady-detail preview unavailable')
                return self.verified_image(folder/name,previews[name])
            except (ValueError,KeyError,PermissionError,OSError) as error:
                return self.handle_error(error)
        match = re.fullmatch(r'/api/jobs/([0-9a-f]{32})/intake/(upload|receipt|preview|decision|prepared)', path)
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
            if role == 'decision':
                data = json.dumps(self.server.manager.decision_record(jid), indent=2).encode()
                self.send_response(200)
                self.headers_safe('application/json', len(data), 'lesson-decision.json')
                self.wfile.write(data)
                return
            if role in ('upload', 'prepared'):
                source = self.server.manager.uploaded_path(jid) if role == 'upload' else folder / 'input.mp4'
                data = backend.bounded_regular_bytes(source, MAX_UPLOAD if role == 'upload' else 8 * 1024**2)
                if hashlib.sha256(data).hexdigest() != receipt['uploaded_sha256' if role == 'upload' else 'prepared_sha256']:
                    raise ValueError('Retained lesson source changed')
            else:
                data = json.dumps(receipt, indent=2).encode()
            self.send_response(200)
            self.headers_safe('video/mp4' if role == 'prepared' else 'application/octet-stream' if role == 'upload' else 'application/json', len(data),
                              'prepared-lesson.mp4' if role == 'prepared' else 'uploaded-original.bin' if role == 'upload' else 'preparation.json')
            self.wfile.write(data)
        except (ValueError, KeyError, PermissionError, OSError) as error:
            return self.handle_error(error)
