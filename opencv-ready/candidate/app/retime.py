"""Bounded periodic-decoration retiming. No semantic or safety classification."""
import numpy as np
from native_yuv import planes, support_masks

MAX_PERIOD = 30
MIN_CYCLES = 3
MAX_REPEAT_FRAME_MAE = 2.0
MIN_LUMA_RANGE = 32.0
MAX_REPEAT_SAMPLE_ERROR = 32  # Explicit v2 development budget, not semantic equivalence.


def detect_period(source, mask, lo, hi):
    if mask.ndim != 2 or not mask.any() or mask.shape[0] % 2 or mask.shape[1] % 2:
        raise ValueError('An occupied even-dimension mask is required.')
    if not 0 <= lo < hi < len(source):
        raise ValueError('Invalid inclusive interval.')
    h, w = mask.shape
    selected, chroma = support_masks(mask)
    if any(f.dtype != np.uint8 or f.ndim != 1 or f.size != h*w*3//2 for f in source):
        raise ValueError('Invalid native YUV420 samples.')
    chroma_samples = [np.stack([planes(f,w,h)[plane][chroma] for f in source[lo:hi+1]]).astype(np.int16)
                      for plane in (1,2)]
    samples = np.stack([planes(f, w, h)[0][selected] for f in source[lo:hi+1]]).astype(np.int16)
    means = samples.mean(axis=1)
    if np.ptp(means) < MIN_LUMA_RANGE:
        raise ValueError('Insufficient selected luminance variation for periodic retiming.')
    # Test selected luma and supporting chroma pixels, not just region mean. Repetition is bounded
    # to this supplied interval and does not establish semantic equivalence.
    scores = []
    for period in range(2, min(MAX_PERIOD, len(samples)//MIN_CYCLES)+1):
        differences = [np.abs(v[period:] - v[:-period]) for v in [samples, *chroma_samples]]
        score = max(float(d.mean(axis=1).max()) for d in differences)
        sample_max = max(int(d.max()) for d in differences)
        scores.append({'period_frames': period, 'max_repeat_plane_frame_mae': score, 'max_repeat_sample_error': sample_max})
        if score <= MAX_REPEAT_FRAME_MAE and sample_max <= MAX_REPEAT_SAMPLE_ERROR:
            return {'period_frames': period, 'complete_cycles_observed': len(samples)//period,
                    'max_repeat_plane_frame_mae': score, 'max_repeat_sample_error': sample_max, 'gate_version': 'bounded-native-recurrence-v2', 'luma_mean_range': float(np.ptp(means)),
                    'thresholds': {'max_period': MAX_PERIOD, 'min_cycles': MIN_CYCLES,
                    'max_repeat_plane_frame_mae': MAX_REPEAT_FRAME_MAE, 'max_repeat_sample_error': MAX_REPEAT_SAMPLE_ERROR, 'min_luma_range': MIN_LUMA_RANGE},
                    'scores': scores}
    raise ValueError('No repeated selected-pixel cycle passes the bounded periodicity gate.')


def frame_map(count, lo, hi, period, factor):
    if type(factor) is not int or not 2 <= factor <= 10:
        raise ValueError('Slowdown factor must be an integer from 2 to 10.')
    if not 0 <= lo < hi < count or not 2 <= period <= MAX_PERIOD:
        raise ValueError('Invalid retiming extent or period.')
    if period*factor > hi-lo+1:
        raise ValueError('The interval cannot show one full slowed cycle.')
    mapping = np.arange(count)
    mapping[lo:hi+1] = lo + (np.arange(hi-lo+1)//factor) % period
    return mapping


def retimed_frames(source, mask, mapping):
    if len(mapping) != len(source) or np.any(mapping < 0) or np.any(mapping >= len(source)):
        raise ValueError('Invalid source frame mapping.')
    h, w = mask.shape
    ym, cm = support_masks(mask)
    for index, source_index in enumerate(mapping):
        result = source[index].copy()
        for dst, src, support in zip(planes(result,w,h), planes(source[source_index],w,h), (ym,cm,cm)):
            dst[support] = src[support]
        yield result
