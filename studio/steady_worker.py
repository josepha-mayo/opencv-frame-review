"""Isolated extension worker; the historical detector and retimer stay frozen."""
from pathlib import Path
import os
import sys
import time
START = time.monotonic()
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'opencv-ready/candidate/app'))
import engine as e
import steady_detail as steady
import steady_boundaries
from native_yuv import decode_yuv


def analyze(job):
    analysis = e.analyze(job)
    source = list(decode_yuv(e, job/'input.mp4', 'steady_source'))
    detection = steady_boundaries.detect(e,job/'input.mp4',source)
    del source
    e.write_json(job/'steady-analysis.json', detection)
    wanted = {c[k] for c in detection['candidates'] for k in ('reference_frame', 'alternate_frame')}
    if wanted:
        for index, rgb in enumerate(e.decode(job/'input.mp4', 'steady_previews')):
            if index not in wanted:
                continue
            for candidate in detection['candidates']:
                for role, key in [('reference', 'reference_frame'), ('alternate', 'alternate_frame')]:
                    if candidate[key] != index:
                        continue
                    image = rgb.copy()
                    x, y, w, h = candidate['bbox']
                    e.cv2.rectangle(image, (max(0,x-2),max(0,y-2)), (min(e.W-1,x+w+1),min(e.H-1,y+h+1)), (250,170,30), 1)
                    target = job/(candidate['id']+'-'+role+'.png')
                    if not e.cv2.imwrite(str(target), e.cv2.cvtColor(image, e.cv2.COLOR_RGB2BGR)):
                        raise ValueError('Steady-detail preview could not be written.')
    # Bind exact still bytes without changing the independent detector output.
    previews = {p.name: e.sha(p) for p in job.glob('steady-*-*.png')}
    e.write_json(job/'steady-previews.json', previews)
    return analysis


def main():
    mode, job = sys.argv[1], Path(sys.argv[2]).resolve()
    if mode not in ('analyze', 'export') or not job.is_dir() or not (job/'input.mp4').is_file():
        raise ValueError('Invalid studio worker request.')
    bounds = e.Bounds(job, mode, start=START)
    e.BOUNDS = bounds
    result = failure = None
    try:
        e.verify_runtime()
        if mode == 'analyze':
            result = analyze(job)
        else:
            from steady_export import export
            result = export(e, job)
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
    finally:
        resources = bounds.close()
        e.write_json(job/(mode+'.resources.json'), {'resources': resources, 'commands': bounds.commands})
    if failure:
        e.write_json(job/(mode+'.error.json'), failure)
        print(e.json.dumps(failure), flush=True)
        return 1
    result['resources'] = resources
    e.write_json(job/('analysis.json' if mode == 'analyze' else 'export.json'), result)
    if mode == 'export':
        report = e.read_json(job/'report.json')
        report.update(resources=resources, commands=bounds.commands)
        e.write_json(job/'report.json', report)
    print(e.json.dumps({'stage': mode, 'complete': True, 'resources': resources}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
