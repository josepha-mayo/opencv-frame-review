"""Versioned stationary two-state blink proposals, separate from the frozen detector.

This recognizes a small repeated appearance, never a semantic distraction. The
creator must decide whether holding one observed state preserves the lesson.
"""
import hashlib
import json
from pathlib import Path

MODE = 'steady-detail-v1'
POLICY = {'version': 'steady-proposal-v2', 'action': MODE,
          'minimum_luma_range': 24, 'minimum_transitions': 6,
          'maximum_transitions_per_second': 4, 'minimum_state_dwell_frames': 5,
          'maximum_state_dwell_frames': 60,
          'maximum_box': [24, 32], 'minimum_pixels': 4,
          'state_mean_error_floor': 2.0, 'state_mean_error_max': 6.0,
          'state_mean_error_fraction': 0.15, 'minimum_state_separation': 12.0,
          'state_sample_error_max': 16,
          'rgb_influence_padding': 4, 'fallback_window_frames': 120,
          'fallback_stride_frames': 30, 'chroma_mean_error_max': 2.0,
          'chroma_sample_error_max': 16}


def detect_native(source, width, height, cv2, np, guard=lambda: None):
    result = detect(np.stack([f[:width*height].reshape(height,width) for f in source]),cv2,np,guard)
    accepted = []
    for candidate in result['candidates']:
        x,y,w,h = candidate['bbox'];lo,hi = candidate['interval_frames'];ref=candidate['reference_frame']
        measurements=[]
        for plane in (1,2):
            offset=width*height+(plane-1)*width*height//4
            patches=np.stack([raw[offset:offset+width*height//4].reshape(height//2,width//2)[y//2:(y+h)//2,x//2:(x+w)//2] for raw in source[lo:hi+1]]).astype(np.int16)
            error=np.abs(patches-patches[ref-lo])
            measurements.append({'maximum_frame_mean':float(error.mean(axis=(1,2)).max()),'maximum_sample':int(error.max())})
        if all(m['maximum_frame_mean']<=2 and m['maximum_sample']<=16 for m in measurements):
            candidate['chroma_stability']=measurements
            accepted.append(candidate)
        guard()
    result['candidates']=accepted
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def detect(luma, cv2, np, guard=lambda: None):
    result = _window(luma, cv2, np, guard)
    if result['candidates'] or len(luma) <= 120:
        return result
    # Typing can stop partway through an excerpt. Search fixed four-second
    # windows on a one-second grid, never silently hold through the typing.
    seen = set()
    for start in range(0, len(luma)-119, 30):
        found = _window(luma[start:start+120], cv2, np, guard)
        for candidate in found['candidates']:
            key = tuple(candidate['bbox'])
            if key in seen:
                continue
            seen.add(key)
            candidate['id'] = 'steady-'+str(len(result['candidates']))
            candidate['interval_frames'] = [start, start+119]
            candidate['interval_seconds'] = [start/30, (start+119)/30]
            candidate['reference_frame'] += start
            candidate['alternate_frame'] += start
            result['candidates'].append(candidate)
            if len(result['candidates']) == 8:
                return result
    return result


def _window(luma, cv2, np, guard):
    """All frames of an admitted excerpt; no guessed or synthesized pixels."""
    n, h, w = luma.shape
    if n < 90:
        return {'policy': POLICY, 'candidates': []}
    low, high = luma.min(axis=0), luma.max(axis=0)
    span = high.astype(np.int16) - low
    middle = (high.astype(np.int16) + low) // 2
    changes = np.zeros((h, w), np.uint16)
    middle_samples = np.zeros((h, w), np.uint16)
    previous = luma[0] > middle
    for frame in luma[1:]:
        state = frame > middle
        changes += state != previous
        middle_samples += np.minimum(np.abs(frame.astype(np.int16)-low), np.abs(frame.astype(np.int16)-high)) > 12
        previous = state
        guard()
    active = ((span >= POLICY['minimum_luma_range']) &
              (changes >= POLICY['minimum_transitions']) &
              (changes <= n / 30 * POLICY['maximum_transitions_per_second']) &
              (middle_samples <= 2)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(active, 8)
    proposals = []
    for index in range(1, count):
        x, y, bw, bh, pixels = map(int, stats[index])
        if pixels < POLICY['minimum_pixels'] or bw > 24 or bh > 32:
            continue
        # Native 4:2:0 samples share a 2x2 block. Bind that complete block.
        x0, y0 = x//2*2, y//2*2
        x1, y1 = min(w, (x+bw+1)//2*2), min(h, (y+bh+1)//2*2)
        patch = luma[:, y0:y1, x0:x1].astype(np.int16)
        averages = patch.mean(axis=(1, 2))
        dark, light = int(averages.argmin()), int(averages.argmax())
        errors = np.stack([np.abs(patch-patch[ref]) for ref in (dark, light)])
        mean_errors = errors.mean(axis=(2, 3))
        state = mean_errors.argmin(axis=0)
        assigned = errors[state, np.arange(n)]
        separation = float(np.abs(patch[dark]-patch[light]).mean())
        # Preparation reduces thin-caret contrast and adds small codec errors.
        # Permit bounded within-state variation relative to the observed state
        # separation; do not admit a third appearance or change export checks.
        mean_limit = max(POLICY['state_mean_error_floor'], min(POLICY['state_mean_error_max'],
                         separation*POLICY['state_mean_error_fraction']))
        if separation < POLICY['minimum_state_separation'] or float(assigned.mean(axis=(1, 2)).max()) > mean_limit or int(assigned.max()) > POLICY['state_sample_error_max']:
            continue
        edges = np.flatnonzero(np.diff(state)) + 1
        dwell = np.diff(np.r_[0, edges, n])
        if (len(edges) < 6 or np.any(dwell[1:-1] < POLICY['minimum_state_dwell_frames'])
                or np.any(dwell > POLICY['maximum_state_dwell_frames'])):
            continue
        if min(int((state==s).sum()) for s in (0, 1)) < 15:
            continue
        ix, iy = max(0, x0-4), max(0, y0-4)
        influence = [ix, iy, min(w, x1+4)-ix, min(h, y1+4)-iy]
        ring = np.ones((influence[3], influence[2]), bool)
        ring[y0-iy:y1-iy, x0-ix:x1-ix] = False
        contrasts = []
        for frame in (dark,light):
            context = luma[frame,iy:iy+influence[3],ix:ix+influence[2]]
            background = float(np.median(context[ring]))
            contrasts.append(float(np.abs(patch[frame]-background).mean()))
        reference = light if contrasts[1] >= contrasts[0] else dark
        alternate = dark if reference == light else light
        proposals.append({'id': 'steady-'+str(len(proposals)), 'bbox': [x0, y0, x1-x0, y1-y0],
                          'influence_xywh': influence, 'interval_frames': [0, n-1],
                          'interval_seconds': [0, (n-1)/30], 'pixels': int((x1-x0)*(y1-y0)),
                          'reference_frame': reference, 'alternate_frame': alternate,
                          'reference_selection': 'Greater mean luma contrast against the median surrounding ring. This is not semantic caret recognition.',
                          'reference_state': 'brighter' if reference == light else 'darker',
                          'state_transitions': int(len(edges)),
                          'minimum_interior_dwell_frames': int(dwell[1:-1].min()),
                          'maximum_observed_dwell_frames': int(dwell.max()),
                          'state_mean_error_max': float(assigned.mean(axis=(1, 2)).max()),
                          'state_mean_error_limit': mean_limit,
                          'state_separation': separation,
                          'state_sample_error_max': int(assigned.max()),
                          'action': MODE, 'meaning': 'Keep the more contrasting observed state steady during this interval; review both states. This may be instructional content.'})
        if len(proposals) == 8:
            break
    return {'policy': POLICY, 'candidates': proposals}


def plan(folder, analysis, detection, body, sha, validate_regions):
    candidate = next((c for c in detection['candidates'] if c['id'] == body.get('candidate_id')), None)
    if candidate is None or body.get('export_mode') != MODE:
        raise ValueError('Choose an existing steady-detail proposal and its explicit edit.')
    if body.get('prediction_sha256') != analysis['prediction_sha256'] or sha(folder/'input.mp4') != analysis['input_sha256'] or sha(folder/'prediction.json') != analysis['prediction_sha256']:
        raise ValueError('Source changed; analyze again before reviewing.')
    h, w = analysis['input_profile']['height'], analysis['input_profile']['width']
    x, y, bw, bh = candidate['influence_xywh']
    influence_runs = [[row*w+x, bw] for row in range(y, y+bh)]
    regions = validate_regions(body.get('protected_regions', []), [h, w], influence_runs)
    if not regions:
        raise ValueError('Mark at least one teaching area before steadying a detail.')
    recipe = {'export_mode': MODE, 'candidate_id': candidate['id'], 'input_profile': analysis['input_profile'],
              'input_sha256': analysis['input_sha256'], 'prediction_sha256': analysis['prediction_sha256'],
              'steady_analysis_sha256': sha(folder/'steady-analysis.json'),
              'implementation_sha256': sha(__file__), 'proposal': candidate,
              'boundary_implementation_sha256': sha(Path(__file__).with_name('steady_boundaries.py')),
              'protected_regions': regions, 'reference_frame': candidate['reference_frame'],
              'scope': 'Hold the more contrasting observed state of this stationary two-state detail only during the proposed interval. Native samples outside the box, all frames outside the interval and decoded RGB outside the influence area must remain exact.'}
    return {'candidate_id': candidate['id'], 'prediction_sha256': analysis['prediction_sha256'],
            'export_mode': MODE, 'protected_regions': regions, 'recipe': recipe,
            'recipe_sha256': hashlib.sha256(canonical(recipe)).hexdigest()}
