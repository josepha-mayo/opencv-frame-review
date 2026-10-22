"""Lossless static crops from aligned decoded frames; no media playback or editing."""
from pathlib import Path
import hashlib
import math
import numpy as np
import cv2

SCHEMA = 'encoded-boundaries-v1'


def boundary_rows(lo, hi, timestamps):
    n = len(timestamps)
    if not (type(lo) is int and type(hi) is int and 0 <= lo <= hi < n):
        raise ValueError('Invalid boundary frame interval')
    if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in timestamps):
        raise ValueError('Boundary timestamps must be finite')
    if any(a >= b for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('Boundary timestamps must increase')
    specs = [('Before edit', (lo - 1) % n, lo == 0),
             ('Edit begins', lo, False),
             ('Final edited frame', hi, False),
             ('Original frames resume', (hi + 1) % n, hi + 1 == n)]
    return [{'label': label, 'frame': frame, 'seconds': timestamps[frame],
             'loop_wrap': wrap} for label, frame, wrap in specs]


class ReviewFrames:
    """Capture at most twelve exact PNG crops while measurement already streams."""
    def __init__(self, job, mask, lo, hi, timestamps, guard=lambda: None):
        if mask.ndim != 2 or mask.dtype != np.uint8 or not np.any(mask):
            raise ValueError('Review needs a nonempty uint8 mask')
        self.job, self.guard = Path(job), guard
        self.shape = (*mask.shape, 3)
        self.rows = boundary_rows(lo, hi, timestamps)
        self.wanted = {row['frame'] for row in self.rows}
        x, y, w, h = cv2.boundingRect(mask)
        x0, y0 = max(0, x - 16), max(0, y - 16)
        x1, y1 = min(mask.shape[1], x + w + 16), min(mask.shape[0], y + h + 16)
        self.crop = [x0, y0, x1 - x0, y1 - y0]
        self.captured = {}

    def capture(self, frame, original, control, edited):
        if frame not in self.wanted:
            return
        if frame in self.captured:
            raise ValueError('Duplicate review frame')
        x, y, w, h = self.crop
        images = {}
        for name, rgb in [('original', original), ('control', control), ('edited', edited)]:
            if rgb.shape != self.shape or rgb.dtype != np.uint8:
                raise ValueError('Unaligned review frame shape or type')
            crop = np.ascontiguousarray(rgb[y:y+h, x:x+w])
            ok, encoded = cv2.imencode('.png', cv2.cvtColor(crop, cv2.COLOR_RGB2BGR),
                                       [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok:
                raise RuntimeError('Review PNG encoding failed')
            # This is lossless still-image packaging, not a new video encode.
            roundtrip = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if roundtrip is None or not np.array_equal(cv2.cvtColor(roundtrip, cv2.COLOR_BGR2RGB), crop):
                raise RuntimeError('Review PNG RGB roundtrip changed')
            data = encoded.tobytes()
            filename = f'boundary-f{frame:05d}-{name}.png'
            with (self.job / filename).open('xb') as output:
                output.write(data)
            images[name] = {'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(),
                            'decoded_crop_rgb_sha256': hashlib.sha256(crop.tobytes()).hexdigest()}
            self.guard()
        self.captured[frame] = images

    def finish(self, binding, strong_return_transition):
        if set(self.captured) != self.wanted:
            raise ValueError('Missing aligned boundary frame')
        required = {'input_sha256', 'prediction_sha256', 'recipe_sha256', 'output_hashes'}
        if set(binding) != required or set(binding['output_hashes']) != {'control', 'edited'}:
            raise ValueError('Incomplete boundary source binding')
        hashes = [binding[k] for k in required - {'output_hashes'}] + list(binding['output_hashes'].values())
        if any(not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v) for v in hashes):
            raise ValueError('Invalid boundary source hash')
        return {'schema': SCHEMA, **binding, 'crop_xywh': self.crop,
                'rows': [dict(row, images=self.captured[row['frame']]) for row in self.rows],
                'strong_return_transition': strong_return_transition,
                'notice': 'Exact aligned decoded RGB crops, without overlay or baked-in scaling. Static images do not establish motion quality, safety or acceptance.',
                'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
