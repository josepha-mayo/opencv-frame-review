"""One fixed spatial-blur reference, not a complete editor or user study."""
from pathlib import Path
import sys,json,subprocess,hashlib,time
sys.path.insert(0,'/app/studio');import run as studio
sys.path.insert(0,str(studio.APP));import engine as e
from native_yuv import decode_yuv,encode_yuv,planes
import audio_preserve
qualification_path=Path(sys.argv[1]);qualification=json.loads(qualification_path.read_text())
source=qualification_path.parent/'jobs'/qualification['job_id']/'input.mp4';out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
bounds=e.Bounds(out,'export');e.BOUNDS=bounds
try:
    e.verify_runtime();timestamps=e.probe(source,'export_source')
    candidate=qualification['candidate']
    lo,hi=candidate['interval_frames'];x,y,w,h=candidate['bbox']
    def blur(frames):
        for t,frame in enumerate(frames):
            output=frame.copy()
            if lo<=t<=hi:
                source_y=planes(frame,e.W,e.H)[0]
                filtered=e.cv2.GaussianBlur(source_y,(5,5),2,borderType=e.cv2.BORDER_REFLECT_101)
                planes(output,e.W,e.H)[0][y:y+h,x:x+w]=filtered[y:y+h,x:x+w]
            yield output
    target=out/'blur-baseline.mp4'
    encode_yuv(e,target,blur(decode_yuv(e,source,'baseline_source')),'blur_reference')
    has_audio=audio_preserve.validate_streams(e.read_json(out/'export_source.probe.json')['metadata'],e.N/30)
    if has_audio:
        audio_preserve.mux(e,source,target,'blur_audio')
        expected_audio=audio_preserve.evidence(e,source,'source_audio')
        actual_audio=audio_preserve.evidence(e,target,'blur_audio_verify')
        audio_check=audio_preserve.compare(expected_audio,actual_audio)
        assert all(v is True for v in audio_check.values())
    else:
        audio_check={'audio_absence_exact':True}
    assert e.probe(target,'baseline_verify',output_codec='h264')==timestamps
    traces={};outside_exact=True;native_exact=True
    source_values=[];blur_values=[];reference_contrasts={}
    for t,(a,b) in enumerate(zip(e.decode(source,'baseline_rgb_source'),e.decode(target,'baseline_rgb_edited'))):
        if lo<=t<=hi:
            source_values.append(float(a[y:y+h,x:x+w].mean()));blur_values.append(float(b[y:y+h,x:x+w].mean()))
        ix,iy,iw,ih=candidate['influence_xywh']
        if t==candidate['reference_frame']:
            ring=e.np.ones((ih,iw),bool);ring[y-iy:y+h-iy,x-ix:x+w-ix]=False
            for label,image in [('source',a),('spatial_blur',b)]:
                context=image[iy:iy+ih,ix:ix+iw].astype(e.np.float64);background=e.np.median(context[ring],axis=0)
                reference_contrasts[label]=float(e.np.abs(image[y:y+h,x:x+w].astype(e.np.float64)-background).mean())
        mask=e.np.ones((e.H,e.W),bool);mask[iy:iy+ih,ix:ix+iw]=False
        outside_exact &= bool(e.np.array_equal(a[mask],b[mask]))
        if not lo<=t<=hi:outside_exact &= bool(e.np.array_equal(a,b))
    for expected,actual in zip(blur(decode_yuv(e,source,'intended_source')),decode_yuv(e,target,'encoded_verify')):
        native_exact &= bool(e.np.array_equal(expected,actual))
    assert outside_exact and native_exact
    for name,values in [('source',source_values),('spatial_blur',blur_values)]:
        traces[name]={'adjacent_roi_mean_changes_at_least_8_rgb_codes':int((e.np.abs(e.np.diff(values))>=8).sum()),'roi_mean_rgb_codes':values,'roi_mean_peak_to_peak':float(e.np.ptp(values)),'adjacent_roi_mean_rms':float(e.np.sqrt(e.np.mean(e.np.diff(values)**2)))}
    record={'schema':'spatial-blur-reference-v1','source_sha256':e.sha(source),'output_sha256':e.sha(target),
            'candidate':candidate,'reference_rgb_contrast_against_ring':reference_contrasts,'parameters':{'gaussian_kernel':[5,5],'sigma':2,'border':'REFLECT_101','apply':'luma only, selected native box and interval; source chroma retained'},
            'traces':traces,'all_outside_influence_rgb_and_outside_interval_frames_exact':outside_exact,
            'native_output_matches_declared_blur':native_exact,'prepared_audio_checks':audio_check,
            'meaning':'A single declared spatial-blur reference. Not optimized, not a professional editor comparison, no user or learning benefit measured.'}
    (out/'results.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v['adjacent_roi_mean_changes_at_least_8_rgb_codes'] for k,v in traces.items()}),flush=True)
finally:
    resources=bounds.close();(out/'resources.json').write_text(json.dumps(resources,indent=2))
