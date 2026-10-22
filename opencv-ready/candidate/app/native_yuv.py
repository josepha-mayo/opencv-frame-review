"""v9 reconstruction: explicit whole-clip native YUV hold, not recovered v7/v8."""
import hashlib
import numpy as np


def planes(frame, width, height):
    size = width * height
    return (frame[:size].reshape(height, width),
            frame[size:size + size // 4].reshape(height // 2, width // 2),
            frame[size + size // 4:].reshape(height // 2, width // 2))


def support_masks(mask):
    """YUV420 chroma is shared by a 2x2 block; include every touched block."""
    h, w = mask.shape
    if h % 2 or w % 2:
        raise ValueError("Native YUV420 requires even dimensions.")
    luma = mask != 0
    chroma = luma.reshape(h // 2, 2, w // 2, 2).any(axis=(1, 3))
    return luma, chroma


def hold_frames(source, mask):
    """Keep source frame zero's selected samples throughout the clip."""
    h, w = mask.shape
    ymask, cmask = support_masks(mask)
    reference = planes(source[0], w, h)
    for raw in source:
        output = raw.copy()
        for edited, original, selected in zip(planes(output, w, h),
                                               reference, (ymask, cmask, cmask)):
            edited[selected] = original[selected]
        yield output


def decode_yuv(e, path, label):
    args = ['/usr/bin/ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-threads', '1', '-filter_threads', '1'] + e.INPUT_FLAGS + [
            '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn',
            '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f',
            'rawvideo', '-threads', '1', 'pipe:1']
    p, log = e.BOUNDS.begin(args, label + '_native_decode')
    size = e.W * e.H * 3 // 2
    try:
        for _ in range(e.N):
            b = p.stdout.read(size)
            if len(b) != size:
                raise ValueError('Native decoded frame count/size mismatch.')
            e.guard()
            yield np.frombuffer(b, np.uint8).copy()
        if p.stdout.read(1):
            raise ValueError('Extra native decoded frames.')
        p.stdout.close()
        e.BOUNDS.end(p, log)
    except BaseException:
        if not log.closed:
            e.BOUNDS.abort(p, log)
        raise


def encode_yuv(e, path, frames, label):
    args = ['/usr/bin/ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-n', '-threads', '1', '-filter_threads', '1', '-f', 'rawvideo',
            '-pixel_format', 'yuv420p', '-video_size', f'{e.W}x{e.H}',
            '-framerate', '30', '-i', 'pipe:0', '-an',
            '-vf', 'setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709', '-c:v', 'libx264',
            '-qp', '0', '-preset', 'fast', '-threads', '1', '-pix_fmt', 'yuv420p',
            '-color_range', 'tv', '-colorspace', 'bt709', '-color_trc', 'bt709',
            '-color_primaries', 'bt709', '-chroma_sample_location', 'left',
            '-fps_mode', 'passthrough', '-video_track_timescale', '15360',
            '-frames:v', str(e.N), str(path)]
    p, log = e.BOUNDS.begin(args, label + '_native_encode', True)
    try:
        count = 0
        for frame in frames:
            p.stdin.write(frame.tobytes())
            count += 1
            e.guard()
        if count != e.N:
            raise ValueError('Native encode frame count mismatch.')
        p.stdin.close()
        e.BOUNDS.end(p, log)
    except BaseException:
        if not log.closed:
            e.BOUNDS.abort(p, log)
        raise


def export(e, job, sourcepath, recipe, component, approval, current_input,
           current_prediction, timestamps):
    mask = e.unpack_mask(component['mask_rle'], component['mask_shape'])
    original = list(decode_yuv(e, sourcepath, 'source'))
    encode_yuv(e, job / 'control.mp4', iter(original), 'control')
    encode_yuv(e, job / 'edited.mp4', hold_frames(original, mask), 'edited')
    for name in ('control', 'edited'):
        if e.probe(job / (name + '.mp4'), name, output_codec='h264') != timestamps:
            raise ValueError('Native export timestamps changed.')
    exact = {'control_native_yuv_exact': True, 'edit_native_yuv_exact': True}
    expected = hold_frames(original, mask)
    for source, intended, control, edited in zip(
            original, expected, decode_yuv(e, job / 'control.mp4', 'control_verify'),
            decode_yuv(e, job / 'edited.mp4', 'edited_verify')):
        exact['control_native_yuv_exact'] &= bool(np.array_equal(source, control))
        exact['edit_native_yuv_exact'] &= bool(np.array_equal(intended, edited))
    if not all(exact.values()):
        raise ValueError('Lossless native-YUV roundtrip failed.')
    del original
    source = list(e.decode(sourcepath, 'source_rgb'))
    lo, hi = [round(x * e.FPS) for x in component['interval']]
    review = e.ReviewFrames(job, mask, lo, hi, timestamps, e.guard)
    protected = e.RegionMeasure(recipe['protected_regions'], e.np, e.cv2)
    outside = e.cv2.bitwise_not(mask)
    histogram = np.zeros(256, np.int64)
    control_rgb_exact = True
    edited_frames = []
    control_frames = []
    # Store only one decoded output at a time after collecting measurements.
    for t, (a, b, c) in enumerate(zip(source,
            e.decode(job / 'control.mp4', 'control_rgb'),
            e.decode(job / 'edited.mp4', 'edited_rgb'))):
        review.capture(t, a, b, c)
        protected.add(b, c)
        control_rgb_exact &= bool(np.array_equal(a, b))
        d = e.cv2.absdiff(b, c)
        for ch in range(3):
            histogram += e.cv2.calcHist([d], [ch], outside, [256], [0, 256]).ravel().astype(np.int64)
        e.guard()
    traces = {'source': e.trace(source, mask, lo, hi)}
    del source
    for name in ('control', 'edited'):
        traces[name] = e.trace(e.decode(job / (name + '.mp4'), name + '_trace'), mask, lo, hi)
    measured = protected.result()
    outside_error = e.hist_summary(histogram)
    checks = {**exact, 'control_rgb_exact': control_rgb_exact,
              'output_metadata_and_timing': True,
              'selected_rolling_count_at_most_6': traces['edited']['middle_cycle_max_count'] <= 6,
              'outside_mean_at_most_1': outside_error['mean_rgb_code_error'] <= 1,
              'outside_p99_at_most_3': outside_error['p99_rgb_code_error'] <= 3}
    if measured['declared']:
        checks['creator_protected_content'] = measured['passed']
    boundary = {key: {'control_delta': traces['control'][field],
                      'edited_delta': traces['edited'][field]}
                for key, field in [('entry', 'entry_delta'), ('exit', 'exit_delta'),
                                   ('loop_seam', 'seam_absolute_delta')]}
    summary = {
        'protected_content': measured,
        'review_status': 'needs_creator_review' if all(checks.values()) else 'checks_failed',
        'selected_trigger_count': {'control': traces['control']['middle_cycle_max_count'],
                                   'edited': traces['edited']['middle_cycle_max_count'], 'criterion_max': 6},
        'outside_mask_error': outside_error, 'boundary': boundary, 'checks': checks,
        'export_mode': 'native-yuv-whole-clip-v9',
        'codec': 'H.264 lossless in MP4, YUV420 BT.709; High 4:4:4 Predictive profile, playback compatibility unverified',
        'warnings': [
            'The selected decoration is frozen for the entire clip, not only its detected interval.',
            'Native chroma samples are shared by 2x2 pixels. RGB interpolation may change adjacent pixels.',
            'Passing these measurements does not establish safety, conformance, readability or artistic acceptance.',
            'This is a newly reconstructed v9 implementation, not the missing v7/v8 source.'],
        'scope': 'Owned synthetic development fixture; no general-video or creator-benefit claim.'}
    hashes = {n: e.sha(job / (n + '.mp4')) for n in ('control', 'edited')}
    binding = {'input_sha256': current_input, 'prediction_sha256': current_prediction,
               'recipe_sha256': approval['recipe_sha256'], 'output_hashes': hashes}
    frames = review.finish(binding, {'newly_timed': False,
        'edited_delta': boundary['exit']['edited_delta'],
        'control_delta': boundary['exit']['control_delta'], 'criterion': .1})
    labels = ['Before detected interval', 'Detected interval starts',
              'Detected interval ends', 'After detected interval']
    for row, label in zip(frames['rows'], labels):
        row['label'] = label
    frames['notice'] = 'Static samples around the detected interval. Native hold applies to the WHOLE clip. No autoplay.'
    e.write_json(job / 'frame-review.json', frames)
    report = {'profile': e.CURRENT_PROFILE['id'], 'summary': summary, 'approval': approval,
              **binding, 'frame_review': frames, 'quality': {'all_outside_histogram': histogram.tolist(),
              'protected_content': measured}, 'selected_traces': traces,
              'versions': e.PROFILE['versions'], 'limitations': e.LIMITATIONS}
    e.write_json(job / 'report.json', report)
    e.write_json(job / 'recipe.json', recipe)
    (job / 'report.txt').write_text('Frame review v9 reconstructed native export\n\n' +
        e.json.dumps(summary, indent=2) + '\n\nNo safety or publication clearance is implied.\n')
    return {'summary': summary, 'output_hashes': hashes,
            'frame_review_sha256': e.sha(job / 'frame-review.json')}
