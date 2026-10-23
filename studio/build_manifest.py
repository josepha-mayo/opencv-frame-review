"""Freeze a NEW studio source identity; never edits historical package manifests."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', required=True)
    parser.add_argument('--build', required=True, help='A new, explicit release identity')
    args = parser.parse_args()
    paths = [*ROOT.glob('*.py'), REPO/'Dockerfile', ROOT/'runtime-requirements.lock']
    for directory in (ROOT / 'static', ROOT / 'tests', ROOT / 'fixtures', REPO / 'opencv-ready/candidate', REPO / 'opencv-ready/opencv-recovery'):
        paths.extend(path for path in directory.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'))
    files = {path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths))}
    record = {'build': args.build,
              'scope': 'Studio, bounded preparation, frozen rapid-change engine, and separately versioned stationary blink detection/export. Source identity is separate from media/browser/cloud qualification.',
              'frozen_backend_commit': 'fd861d0ce2cd50bec741327975d95ff5488254e2',
              'files': files}
    (ROOT / 'BUILD_HASHES.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Froze', len(files), 'files. This establishes source identity only.')


if __name__ == '__main__':
    main()
