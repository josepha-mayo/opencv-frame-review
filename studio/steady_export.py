"""Lossless local hold of an observed small blink state, with encoded checks."""
import numpy as np
import audio_preserve
from native_yuv import decode_yuv, encode_yuv
from retime import retimed_frames
from protected_regions import validate_regions
import steady_detail as steady
import steady_boundaries as boundaries
from teaching_motion import TeachingMotion


def export(e, job):
    sourcepath = job/'input.mp4'
    analysis, approval = e.read_json(job/'analysis.json'), e.read_json(job/'approval.json')
    detection = e.read_json(job/'steady-analysis.json')
    planned = steady.plan(job, analysis, detection, approval, e.sha, validate_regions)
    if approval.get('approve') is not True or any(approval.get(k) != planned[k] for k in planned):
        raise ValueError('Approved steady-detail plan changed; export refused.')
    recipe, candidate = planned['recipe'], planned['recipe']['proposal']
    timestamps = e.probe(sourcepath, 'export_source')
    if analysis['input_profile'] != e.CURRENT_PROFILE:
        raise ValueError('Steady-detail source profile changed.')
    original = list(decode_yuv(e, sourcepath, 'steady_source'))
    fresh = boundaries.detect(e,sourcepath,original)
    if fresh != detection:
        raise ValueError('Fresh steady-detail analysis differs from the reviewed source.')
    mask = np.zeros((e.H,e.W), np.uint8)
    x,y,w,h = candidate['bbox']; mask[y:y+h,x:x+w] = 255
    influence = np.zeros_like(mask)
    ix,iy,iw,ih = candidate['influence_xywh']; influence[iy:iy+ih,ix:ix+iw] = 255
    lo,hi = candidate['interval_frames']
    mapping = np.arange(e.N)
    mapping[lo:hi+1] = candidate['reference_frame']
    has_audio = audio_preserve.validate_streams(e.read_json(job/'export_source.probe.json')['metadata'], e.N/30)
    source_audio = audio_preserve.evidence(e, sourcepath, 'steady_original_audio') if has_audio else None
    pending = job/'pending-candidate.mp4'
    encode_yuv(e, job/'control.mp4', iter(original), 'steady_control')
    encode_yuv(e, pending, retimed_frames(original,mask,mapping), 'steady_edited')
    audio_checks = {}
    if has_audio:
        for name,path in [('control',job/'control.mp4'),('edited',pending)]:
            audio_preserve.mux(e,sourcepath,path,'steady_'+name+'_audio')
            actual = audio_preserve.evidence(e,path,'steady_'+name+'_audio_verify')
            audio_checks[name] = audio_preserve.compare(source_audio,actual)
    control_ts = e.probe(job/'control.mp4','steady_control',output_codec='h264')
    edited_ts = e.probe(pending,'steady_edited',output_codec='h264')
    native_control = native_edit = True
    for expected,actual in zip(original,decode_yuv(e,job/'control.mp4','steady_control_verify')):
        native_control &= bool(np.array_equal(expected,actual))
    for expected,actual in zip(retimed_frames(original,mask,mapping),decode_yuv(e,pending,'steady_edited_verify')):
        native_edit &= bool(np.array_equal(expected,actual))
    del original
    protected = e.RegionMeasure(recipe['protected_regions'],np,e.cv2)
    teaching = TeachingMotion(recipe['protected_regions'],[lo,hi],e.N,np)
    review = e.ReviewFrames(job,mask,lo,hi,timestamps,e.guard)
    outside_histogram = np.zeros(256,np.int64)
    control_rgb = outside_interval = True
    patch_means = {'source':[], 'edited':[]}
    selected_constant = True
    reference_patch = None
    boundary_samples = {}
    full_means = {'source':[], 'edited':[]}
    linear_values = {'source':[], 'control':[], 'edited':[]}
    # First read the selected reference crop independently from the encoded edit.
    for t,rgb in enumerate(e.decode(sourcepath,'steady_reference')):
        if t == candidate['reference_frame']:
            reference_patch = rgb[y:y+h,x:x+w].copy()
    for t,(source,control,edited) in enumerate(zip(e.decode(sourcepath,'steady_source_rgb'),e.decode(job/'control.mp4','steady_control_rgb'),e.decode(pending,'steady_edited_rgb'))):
        control_rgb &= bool(np.array_equal(source,control))
        for name,frame in [('source',source),('control',control),('edited',edited)]:
            linear_values[name].append(boundaries.selected_linear(e,frame,candidate['bbox']))
        for name,frame in [('source',source),('edited',edited)]:
            full_means[name].append(float(frame[y:y+h,x:x+w].mean()))
        if t in (0,e.N-1,lo-1,lo,hi,hi+1):
            boundary_samples[t] = {name:{'selected':frame[y:y+h,x:x+w].copy(),'influence':frame[iy:iy+ih,ix:ix+iw].copy()} for name,frame in [('source',source),('edited',edited)]}
        if t < lo or t > hi:
            outside_interval &= bool(np.array_equal(source,edited))
        else:
            # YUV is authoritative for exact replacement; RGB patch-edge
            # interpolation can depend on neighbours. Measure it explicitly.
            selected_constant &= bool(np.array_equal(reference_patch,edited[y:y+h,x:x+w]))
            patch_means['source'].append(float(source[y:y+h,x:x+w].mean()))
            patch_means['edited'].append(float(edited[y:y+h,x:x+w].mean()))
        protected.add(source,edited)
        teaching.add(t,source,edited)
        review.capture(t,source,control,edited)
        difference=e.cv2.absdiff(source,edited)
        for channel in range(3):
            outside_histogram += e.cv2.calcHist([difference],[channel],e.cv2.bitwise_not(influence),[256],[0,256]).ravel().astype(np.int64)
        e.guard()
    measured = protected.result()
    teaching_result = teaching.result()
    measured['scope'] = 'Every decoded RGB frame versus prepared source. Fixed areas; creator judges meaning and readability.'
    for region in measured['regions']:
        region['criteria']={k:0 for k in region['measurements']}
        region['passed']=all(v==0 for v in region['measurements'].values())
    measured['passed']=bool(measured['regions']) and all(r['passed'] for r in measured['regions'])
    outside_error = e.hist_summary(outside_histogram)
    def transitions(values):
        # A separate encoded ROI-mean diagnostic, not the rapid-flash detector.
        return int((np.abs(np.diff(values))>=8).sum())
    activity = {k: transitions(v) for k,v in patch_means.items()}
    encoded_boundaries=boundaries.encoded_measurements(boundary_samples,lo,hi,e.N,np)
    traces = {name:boundaries.trace_from_values(e,values,lo,hi) for name,values in linear_values.items()}
    linear_boundaries={name:{'source':traces['source'][field],'edited':traces['edited'][field],'passed':traces['edited'][field]<=traces['source'][field]+boundaries.POLICY['boundary_tolerance']} for name,field in [('entry','entry_delta'),('exit','exit_delta'),('loop_seam','seam_absolute_delta')]}
    whole_activity={name:transitions(values) for name,values in full_means.items()}
    full_events={name:np.abs(np.diff(values))>=boundaries.POLICY['activity_threshold_rgb_codes'] for name,values in full_means.items()}
    new_events=int((full_events['edited'] & ~full_events['source']).sum())
    checks = {'fresh_stationary_two_state_proposal':True, 'approved_plan_bound':True,
              'native_control_exact':native_control, 'native_edit_matches_mapping':native_edit,
              'unchanged_control_rgb_exact':control_rgb,
              'all_timestamps_exact':control_ts==timestamps and edited_ts==timestamps,
              'all_frames_outside_interval_exact':outside_interval,
              'all_rgb_outside_influence_exact':outside_error['max_rgb_code_error']==0,
              'all_protected_teaching_rgb_exact':measured['passed'],
              'all_ordered_teaching_rgb_sequences_exact':teaching_result['all_ordered_rgb_sequences_exact'],
              'audio_exact':not has_audio or all(all(v is True for v in c.values()) for c in audio_checks.values()),
              'source_and_detection_unchanged':e.sha(sourcepath)==analysis['input_sha256'] and e.sha(job/'steady-analysis.json')==recipe['steady_analysis_sha256'],
              'selected_activity_reduced':activity['source']>=boundaries.POLICY['minimum_removed_mean_changes'] and activity['edited']==0,
              'encoded_boundary_rgb_not_worse':encoded_boundaries['passed'],
              'encoded_boundary_selected_mean_not_worse':all(r['passed'] for r in linear_boundaries.values()),
              'whole_clip_activity_reduced':whole_activity['edited']<whole_activity['source'],
              'whole_clip_no_new_activity_events':new_events==0}
    acceptance = {'status':'accepted_experiment' if all(checks.values()) else 'rejected_experiment', 'checks':checks,
                  'meaning':'Encoded preservation and activity measurements only. Creator review is required; no measured learning or accessibility benefit.'}
    decision={'schema':'steady-detail-export-v1','recipe':recipe,'mapping':mapping.tolist(),
              'activity':activity,'activity_threshold_rgb_codes':8,'protected':measured,
              'outside_rgb':outside_error,'rgb_selected_matches_reference':selected_constant,
              'encoded_boundary_checks':encoded_boundaries,'linear_boundary_checks':linear_boundaries,
              'whole_clip_activity':whole_activity,'new_activity_events':new_events,
              'teaching_motion':teaching_result,
              'acceptance':acceptance,'audio_preservation':{'present':has_audio,'checks':audio_checks}}
    e.write_json(job/'result.json',decision)
    pending.rename(job/('edited.mp4' if all(checks.values()) else 'rejected-candidate.mp4'))
    if not all(checks.values()):
        raise ValueError('Steady-detail encoded checks failed; no edited download is accepted.')
    hashes={name:e.sha(job/(name+'.mp4')) for name in ('control','edited')}
    binding={'input_sha256':analysis['input_sha256'],'prediction_sha256':analysis['prediction_sha256'],'recipe_sha256':approval['recipe_sha256'],'output_hashes':hashes}
    teaching_review=teaching.write_review(job,e.cv2,binding)
    e.write_json(job/'teaching-review.json',teaching_review)
    strong = {'newly_timed':traces['edited']['exit_delta']>=.1 and traces['control']['exit_delta']<.1,
              'edited_delta':traces['edited']['exit_delta'],'control_delta':traces['control']['exit_delta'],'criterion':.1}
    frames=review.finish(binding,strong)
    e.write_json(job/'frame-review.json',frames)
    warnings=['Holds the more contrasting observed state only during the shown interval; alternate blink phases are intentionally removed.',
              'A blinking detail may convey progress or position. Check both source states and the boundaries before using this edit.',
              'Native YUV outside the selected box and decoded RGB outside its four-pixel influence area are verified separately.',
              'Preparation resized/re-encoded the original. Exact edit checks reference the prepared clip.',
              'No learning, time-saving, medical, safety or compliance claim.']
    summary={'export_mode':steady.MODE,'review_status':'needs_creator_review','checks':checks,'acceptance':acceptance,
             'stationary_detail':{'proposal':candidate,'activity':activity,'whole_clip_activity':whole_activity,'new_activity_events':new_events,'metric':'Number of adjacent ROI-mean RGB changes >=8 codes. Interior and fixed whole-clip counts are separate; the latter includes both cut boundaries.'},
             'encoded_boundary_checks':encoded_boundaries,'linear_boundary_checks':linear_boundaries,
             'protected_content':measured,'outside_mask_error':outside_error,'audio_preservation':decision['audio_preservation'],
             'teaching_motion':teaching_result,
             'boundary':{name:{'control_delta':traces['control'][field],'edited_delta':traces['edited'][field]} for name,field in [('entry','entry_delta'),('exit','exit_delta'),('loop_seam','seam_absolute_delta')]},
             'codec':'Lossless H.264 High 4:4:4 Predictive, YUV420; verify browser playback separately','warnings':warnings}
    report={'profile':analysis['input_profile']['id'],'summary':summary,'approval':approval,**binding,
            'teaching_review':teaching_review,
            'frame_review':frames,'steady_detail':decision,'versions':e.PROFILE['versions'],'limitations':warnings}
    e.write_json(job/'report.json',report);e.write_json(job/'recipe.json',recipe)
    (job/'report.txt').write_text('Steady observed detail\n\n'+e.json.dumps(summary,indent=2)+'\n\nReview the original and edited clip before use.\n')
    return {'summary':summary,'output_hashes':hashes,'frame_review_sha256':e.sha(job/'frame-review.json'),'teaching_review_sha256':e.sha(job/'teaching-review.json')}
