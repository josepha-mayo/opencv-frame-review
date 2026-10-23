#!/usr/bin/env python3
"""Versioned studio UI over the unchanged media engine. Loopback only."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BASE = REPO / 'opencv-ready'
APP = BASE / 'candidate/app'


def check_source(root=REPO):
    """Check this build's runtime inputs, not the historical evidence archive."""
    manifest = json.loads((root / 'studio/BUILD_HASHES.json').read_text(encoding='utf-8'))
    failures = []
    for relative, expected in manifest['files'].items():
        path = root / relative
        if path.resolve().is_relative_to(root.resolve()) is False:
            raise RuntimeError('Invalid source manifest path')
        if not path.is_file():
            failures.append('Missing build file: ' + relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append('Changed build file: ' + relative)
    if failures:
        raise RuntimeError('\n'.join(failures))
    return {'build': manifest['build'], 'source_files_verified': len(manifest['files']),
            'media_runtime_checked': False, 'media_qualification': 'not established for this build'}


def check_runtime():
    if sys.platform != 'linux':
        raise RuntimeError('The media worker requires Linux resource/process controls and pinned Debian FFmpeg. Use the trusted Linux runtime in opencv-ready/RUNTIME.json.')
    sys.path.insert(0, str(APP))
    try:
        import engine
        engine.verify_runtime()
    except (ImportError, OSError, RuntimeError) as error:
        raise RuntimeError('Pinned media runtime unavailable: ' + str(error)) from error


def make_studio_server(port, data_dir):
    # Called only after preflight in the CLI. Tests may use this without starting
    # media workers, to verify routing/CSRF/host controls with standard library.
    sys.path.insert(0, str(APP))
    import server as backend

    from lesson_intake import LessonHandler, LessonManager
    server = backend.make_server(port, data_dir)
    server.manager.close()
    server.manager = LessonManager(data_dir)
    server.RequestHandlerClass = LessonHandler
    return server


def verify(output):
    if shutil.which('node') is None:
        raise RuntimeError('Node.js is required; DOM checks will not be silently skipped.')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'workspace'
    shutil.copytree(BASE / 'candidate', workspace / 'candidate', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(BASE / 'opencv-recovery', workspace / 'opencv-recovery')
    shutil.copytree(ROOT / 'static', workspace / 'candidate/app/static', dirs_exist_ok=True)
    tests = workspace / 'candidate/app/tests'
    stages = [
        ('units', ['-m', 'unittest', 'discover', '-s', str(tests)]),
        ('duration', [str(tests / 'integration_duration.py'), str(output / 'duration')]),
        ('duration-refusals', [str(tests / 'integration_duration_rejections.py'), str(output / 'duration-refusals'), str(output / 'duration/fixtures/640-360.mp4')]),
        ('original-audio', [str(tests / 'integration_audio.py'), str(output / 'original-audio')]),
        ('original-silent', [str(tests / 'integration_retime.py'), str(output / 'original-silent')]),
        ('audio-refusals', [str(tests / 'integration_audio_rejections.py'), str(output / 'audio-refusals')]),
        ('pixel-refusals', [str(tests / 'integration_rejections.py')]),
        ('lesson', [str(ROOT / 'tests/integration_lesson.py'), str(output / 'lesson')]),
        ('real-lessons', [str(ROOT / 'tests/integration_real_lessons.py'), str(output / 'real-lessons')]),
        ('studio-ui', ['-m', 'unittest', 'discover', '-s', str(ROOT / 'tests')]),
    ]
    outcomes = []
    receipt = {'build': check_source()['build'], 'complete': False, 'stages': outcomes}
    (output / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for name, args in stages:
        print('Checking ' + name, flush=True)
        with (output / (name + '.log')).open('w') as log:
            result = subprocess.run([sys.executable, *args], stdout=log, stderr=subprocess.STDOUT)
        outcomes.append({'stage': name, 'returncode': result.returncode, 'log': name + '.log'})
        receipt['complete'] = len(outcomes) == len(stages) and result.returncode == 0
        (output / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(output / (name + '.log')))
    print('Ten stages passed, including real classroom intake and the disclosed augmented edit challenge. Browser checks and creator benefit remain separate.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-source', action='store_true')
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--serve', action='store_true')
    mode.add_argument('--verify', type=Path, metavar='NEW_DIRECTORY')
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'runtime-jobs')
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError('Port must be between 1 and 65535.')
        status = check_source()
        if args.check_source:
            print(json.dumps(status))
            return 0
        check_runtime()
        status['media_runtime_checked'] = True
        print(json.dumps(status), flush=True)
        if args.check:
            return 0
        if args.verify:
            verify(args.verify)
            return 0
        server = make_studio_server(args.port, args.data_dir)
        print(f'Open http://127.0.0.1:{args.port}. Static inspection; explicit consent required.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.manager.close()
            server.server_close()
        return 0
    except (RuntimeError, OSError, ValueError) as error:
        print('Not ready: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
