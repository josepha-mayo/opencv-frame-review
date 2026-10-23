"""Fetch the two licensed evaluation originals, with byte caps and fixed hashes.

Usage: python research/fetch-real-evaluation-sources.py NEW_DIRECTORY
Media licenses/attribution are documented in real-lesson-evaluation.md.
"""
from pathlib import Path
import hashlib
import sys
import urllib.request

target = Path(sys.argv[1]); target.mkdir(exist_ok=False)
sources = [
    ('ittt-present-simple.webm', 'https://upload.wikimedia.org/wikipedia/commons/b/be/English_Grammar_%E2%80%94_Present_Simple_%E2%80%94_Teaching_Ideas_%E2%80%94_1.webm', '554bfe67be9ff2edd7a1c04283e9744a78c7b8ec171ebc569bb250144adc33aa'),
    ('wiki-citations.webm', 'https://upload.wikimedia.org/wikipedia/commons/c/c5/8.2_Adding_citations.webm', 'a146328c73c9582a99b35006d3e9e9965881f6a50dd0f05621832911b271419d'),
]
for name, url, expected in sources:
    request = urllib.request.Request(url, headers={'User-Agent': 'FrameReviewEvaluation/1.0 (licensed lesson evaluation)'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(64 * 1024**2 + 1)
    if len(data) > 64 * 1024**2 or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Evaluation source changed: ' + name)
    (target / name).write_bytes(data)
    print(name, expected)
