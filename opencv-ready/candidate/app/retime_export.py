"""Real protected export behind the existing bounded loopback workflow."""
import numpy as np
from native_yuv import decode_yuv, encode_yuv
from retime import detect_period, frame_map, retimed_frames
from acceptance import finalize_candidate
import audio_preserve


def export(e,job,sourcepath,recipe,component,approval,current_input,current_prediction,timestamps):
    mask=e.unpack_mask(component['mask_rle'],component['mask_shape'])
    lo,hi=recipe['frame_bounds_inclusive']
    fresh=e.alg.detector(e.decode(sourcepath,'fresh_localization'),timestamps)
    if fresh != e.read_json(job/'prediction.json'):
        raise ValueError('Fresh localization differs from the reviewed input; analyze again.')
    audio_meta=e.read_json(job/'export_source.probe.json')['metadata']
    has_audio=audio_preserve.validate_streams(audio_meta,e.N/30)
    audio_original=audio_preserve.evidence(e,sourcepath,'original_audio') if has_audio else None
    original=list(decode_yuv(e,sourcepath,'source'))
    try:detection=detect_period(original,mask,lo,hi)
    except ValueError as error:
        e.write_json(job/'retime-rejection.json',{'status':'unsupported_recurrence','reason':str(error),'scope':'Bounded appearance recurrence, not arbitrary periodic motion.'})
        raise ValueError('Local retiming unsupported: '+str(error)) from error
    mapping=frame_map(e.N,lo,hi,detection['period_frames'],recipe['edit']['factor'])
    pending=job/'pending-candidate.mp4'
    encode_yuv(e,job/'control.mp4',iter(original),'control')
    encode_yuv(e,pending,retimed_frames(original,mask,mapping),'retimed')
    if has_audio:
        audio_preserve.mux(e,sourcepath,job/'control.mp4','control_audio')
        audio_preserve.mux(e,sourcepath,pending,'edited_audio')
    audio_checks={}
    if has_audio:
        for name,path in [('control',job/'control.mp4'),('edited',pending)]:
            actual=audio_preserve.evidence(e,path,name+'_audio')
            audio_checks[name]=audio_preserve.compare(audio_original,actual)
            e.write_json(job/(name+'-audio-evidence.json'),actual)
        e.write_json(job/'source-audio-evidence.json',audio_original)
    control_timing=e.probe(job/'control.mp4','control',output_codec='h264')
    edited_timing=e.probe(pending,'retimed',output_codec='h264')
    native_control=True;native_edit=True
    for a,b in zip(original,decode_yuv(e,job/'control.mp4','control_verify')):
        native_control &= bool(np.array_equal(a,b))
    for a,b in zip(retimed_frames(original,mask,mapping),decode_yuv(e,pending,'retimed_verify')):
        native_edit &= bool(np.array_equal(a,b))
    del original
    review=e.ReviewFrames(job,mask,lo,hi,timestamps,e.guard)
    protected=e.RegionMeasure(recipe['protected_regions'],np,e.cv2)
    histogram=np.zeros(256,np.int64);outside=e.cv2.bitwise_not(mask)
    control_rgb_exact=True;outside_interval_exact=True
    for t,(source,control,edited) in enumerate(zip(e.decode(sourcepath,'source_rgb'),e.decode(job/'control.mp4','control_rgb'),e.decode(pending,'retimed_rgb'))):
        control_rgb_exact &= bool(np.array_equal(source,control))
        if t<lo or t>hi:outside_interval_exact &= bool(np.array_equal(source,edited))
        review.capture(t,source,control,edited);protected.add(source,edited)
        difference=e.cv2.absdiff(source,edited)
        for channel in range(3):histogram+=e.cv2.calcHist([difference],[channel],outside,[256],[0,256]).ravel().astype(np.int64)
        e.guard()
    measured=protected.result()
    measured['scope']='Fixed declared rectangles, every decoded frame, edited versus original source decode. No tracking, readability or meaning guarantee.'
    for region in measured['regions']:
        region['criteria']={k:0 for k in region['measurements']}
        region['passed']=all(v==0 for v in region['measurements'].values())
    measured['passed']=all(r['passed'] for r in measured['regions']) if measured['declared'] else None
    outside_error=e.hist_summary(histogram)
    traces={name:e.trace(e.decode(path,name+'_trace'),mask,lo,hi) for name,path in [('source',sourcepath),('control',job/'control.mp4'),('edited',pending)]}
    decision={'fresh_pixel_detection_matches':True,'native_output_exact':native_control and native_edit and control_rgb_exact,'timing_exact':control_timing==timestamps and edited_timing==timestamps,'masters_unchanged':e.sha(sourcepath)==current_input and e.sha(job/'prediction.json')==current_prediction,'outside_interval_frames_exact':outside_interval_exact,'protected':measured,'outside_rgb':outside_error,'detection':detection,'retained_cycle_phases':sorted(set((mapping[lo:hi+1]-lo).tolist())),'recipe':{'mapping':mapping.tolist(),'protected_regions':recipe['protected_regions']},'output_sha256':e.sha(pending)}
    decision['audio_preservation']={'present':has_audio,'checks':audio_checks,'policy':'copy-only AAC-LC mono 48 kHz; packet payload/timing/skip and decoded PCM exact'}
    if not finalize_candidate(decision,pending,job,accepted_name='edited.mp4'):
        raise ValueError('Encoded local retiming failed preservation checks. No edited download is available; diagnostic output was retained.')
    boundary={name:{'control_delta':traces['control'][field],'edited_delta':traces['edited'][field]} for name,field in [('entry','entry_delta'),('exit','exit_delta'),('loop_seam','seam_absolute_delta')]}
    summary={'audio_preservation':decision['audio_preservation'],'protected_content':measured,'review_status':'needs_creator_review','selected_trigger_count':{'control':traces['control']['middle_cycle_max_count'],'edited':traces['edited']['middle_cycle_max_count'],'criterion_max':6},'outside_mask_error':outside_error,'boundary':boundary,'checks':decision['acceptance']['checks'],'export_mode':'periodic-local-retime-v2','acceptance':decision['acceptance'],'detection':detection,'codec':'Lossless H.264 High 4:4:4 Predictive, YUV420; playback compatibility unverified','warnings':['Slows the observed decoration cycle 5× only inside the detected interval.','This repeats one observed cycle and may discard subtle variations; it does not synthesize smooth motion.','The mean and pointwise recurrence budgets do not guarantee semantic periodicity or reject every small nonperiodic change.','Entry remains abrupt; inspect the exact frame boundaries.','Shared chroma interpolation can alter adjacent pixels. Declared protected regions must remain exact.','No medical, photosensitivity, safety, compliance or publishing-clearance claim.'],'scope':'Bounded synthetic-development profile; real creator benefit and browser playback unverified.'}
    hashes={name:e.sha(job/(name+'.mp4')) for name in ('control','edited')}
    binding={'input_sha256':current_input,'prediction_sha256':current_prediction,'recipe_sha256':approval['recipe_sha256'],'output_hashes':hashes}
    strong={'newly_timed':boundary['exit']['edited_delta']>=.1 and boundary['exit']['control_delta']<.1,'edited_delta':boundary['exit']['edited_delta'],'control_delta':boundary['exit']['control_delta'],'criterion':.1}
    frames=review.finish(binding,strong)
    e.write_json(job/'frame-review.json',frames)
    report={'profile':e.CURRENT_PROFILE['id'],'summary':summary,'approval':approval,**binding,'frame_review':frames,'quality':{'all_outside_histogram':histogram.tolist(),'protected_content':measured},'selected_traces':traces,'periodic_retiming':decision,'versions':e.PROFILE['versions'],'limitations':summary['warnings']}
    e.write_json(job/'report.json',report);e.write_json(job/'recipe.json',recipe)
    (job/'report.txt').write_text('Local periodic-decoration retiming\n\n'+e.json.dumps(summary,indent=2)+'\n\nPassing preservation checks does not approve this edit for publication.\n')
    return {'summary':summary,'output_hashes':hashes,'frame_review_sha256':e.sha(job/'frame-review.json')}
