"""Observed-state holds with bounded, source-compared boundary selection.

Prediction selects a reviewed plan. Independently decoded encoded frames remain
authoritative: a prediction never grants permission to publish a worse boundary.
"""
import copy
import steady_detail as steady

POLICY = {'version':'steady-boundaries-v1','maximum_trim_frames_per_end':30,
          'minimum_hold_frames':60,'minimum_removed_mean_changes':4,
          'maximum_reference_samples':33,'activity_threshold_rgb_codes':8,
          'boundary_tolerance':1e-12,
          'selection':'Minimize worst predicted boundary RGB RMS, then sum, then maximize held duration. Observed references stay in the originally kept appearance class. Trim only; never extend the detected interval. Preserve first and last clip frames.'}


def metrics(a,b,np):
    delta=a.astype(np.float64)-b.astype(np.float64)
    return {'mean_absolute_rgb_codes':float(np.abs(delta).mean()),
            'rms_rgb_codes':float(np.sqrt(np.mean(delta*delta))),
            'maximum_rgb_codes':float(np.abs(delta).max())}


def not_worse(source,edited):
    return all(edited[k]<=source[k]+POLICY['boundary_tolerance'] for k in source)


def selected_linear(e,frame,bbox):
    # Keep the full-width transform: OpenCV SIMD/scalar dispatch can round a
    # narrow crop differently. Reuse already decoded frames, not a new decode.
    x,y,w,h=bbox
    linear=e.cv2.transform(e.cv2.LUT(frame,e.LUT),e.WEIGHTS)
    return float(e.cv2.mean(linear[y:y+h,x:x+w])[0])


def trace_from_values(e,values,lo,hi):
    # Keep the frozen temporal algorithm and cyclic diagnostic convention.
    n=len(values);r=e.alg.temporal(e.np.tile(values,3),e.np.arange(n*3))
    events=[dict(event,frame_in_cycle=event['frame']-n) for event in r['events'] if n<=event['frame']<n*2]
    return {'trace':values,'middle_cycle_max_count':max(r['counts'][n:n*2]),'middle_cycle_counts':r['counts'][n:n*2],'middle_cycle_events':events,'seam_absolute_delta':abs(values[0]-values[-1]),'entry_delta':abs(values[lo]-values[lo-1]) if lo else abs(values[0]-values[-1]),'exit_delta':abs(values[hi+1]-values[hi]) if hi+1<n else abs(values[0]-values[-1])}


def select(candidate,rgb,linear,native,np,guard=lambda:None):
    """Pure selection over all decoded frames of one bounded spatial region."""
    c=copy.deepcopy(candidate);lo,hi=c['interval_frames'];original_ref=c['reference_frame'];alt=c['alternate_frame']
    n=len(rgb);x,y,w,h=c['bbox'];area=w*h
    near=np.abs(rgb.astype(np.int16)-rgb[original_ref]).mean(axis=(1,2,3))
    far=np.abs(rgb.astype(np.int16)-rgb[alt]).mean(axis=(1,2,3))
    eligible=np.flatnonzero((near<=far)&(np.arange(n)>=lo)&(np.arange(n)<=hi))
    if not len(eligible):return None
    refs=sorted(set([original_ref]+eligible[np.linspace(0,len(eligible)-1,min(POLICY['maximum_reference_samples']-1,len(eligible))).round().astype(int)].tolist()))
    prefix=np.r_[0,np.cumsum(np.abs(np.diff(rgb.mean(axis=(1,2,3))))>=POLICY['activity_threshold_rgb_codes'])]
    original_luma=native[:, :area].astype(np.int16)
    # A new reference must represent the same admitted native appearance, and
    # meet the original chroma bounds against every frame of the source window.
    visible=np.abs(original_luma-original_luma[original_ref]).mean(axis=1)<=np.abs(original_luma-original_luma[alt]).mean(axis=1)
    visible[:lo]=False;visible[hi+1:]=False
    best=None
    for ref in refs:
        le=np.abs(original_luma[visible]-original_luma[ref])
        if le.mean(axis=1).max()>c['state_mean_error_limit'] or le.max()>steady.POLICY['state_sample_error_max']:continue
        chroma=[]
        for offset in (area,area+area//4):
            error=np.abs(native[lo:hi+1,offset:offset+area//4].astype(np.int16)-native[ref,offset:offset+area//4])
            chroma.append({'maximum_frame_mean':float(error.mean(axis=1).max()),'maximum_sample':int(error.max())})
        if any(m['maximum_frame_mean']>2 or m['maximum_sample']>16 for m in chroma):continue
        starts=[];ends=[];trim=POLICY['maximum_trim_frames_per_end'];minimum=POLICY['minimum_hold_frames']
        for kind,points in [('entry',range(max(1,lo),min(lo+trim,hi-minimum+1)+1)),('exit',range(max(lo+minimum-1,hi-trim),min(hi,n-2)+1))]:
            for cut in points:
                outer,old=(cut-1,cut) if kind=='entry' else (cut+1,cut)
                source=metrics(rgb[outer],rgb[old],np);edited=metrics(rgb[outer],rgb[ref],np)
                sl=abs(float(linear[outer]-linear[old]));el=abs(float(linear[outer]-linear[ref]))
                if not not_worse(source,edited) or el>sl+POLICY['boundary_tolerance']:continue
                (starts if kind=='entry' else ends).append((cut,{'source':source,'edited':edited,'source_selected_mean_delta':sl,'edited_selected_mean_delta':el}))
        for a,entry in starts:
            for b,exit in ends:
                count=int(prefix[b]-prefix[a])
                if b-a+1<minimum or count<POLICY['minimum_removed_mean_changes']:continue
                key=(max(entry['edited']['rms_rgb_codes'],exit['edited']['rms_rgb_codes']),entry['edited']['rms_rgb_codes']+exit['edited']['rms_rgb_codes'],-(b-a+1),a,b,ref)
                if best is None or key<best[0]:best=(key,a,b,ref,count,entry,exit,chroma)
        guard()
    if best is None:return None
    _,a,b,ref,count,entry,exit,chroma=best
    c.update(interval_frames=[a,b],interval_seconds=[a/30,b/30],reference_frame=ref,chroma_stability=chroma,
             reference_selection='Observed frame in the originally kept appearance class, selected with the reviewed cut points to minimize predicted boundary RMS. No blended or invented pixels.',
             boundary_alignment={'policy':POLICY,'original_interval_frames':[lo,hi],'original_reference_frame':original_ref,'predicted_source_internal_changes':count,'predicted_entry':entry,'predicted_exit':exit,'scope':'Predicted selected-box RGB and selected-mean changes. Encoded selected/influence RGB and linear-mean checks independently decide acceptance.'})
    return c


def detect(e,path,source):
    found=steady.detect_native(source,e.W,e.H,e.cv2,e.np,e.guard)
    found['boundary_policy']=POLICY;found['boundary_refusals']=[]
    candidates=found['candidates']
    if not candidates:return found
    patches=[[] for _ in candidates];native=[]
    for c in candidates:
        x,y,w,h=c['bbox'];planes=[]
        for frame in source:
            row=[frame[:e.W*e.H].reshape(e.H,e.W)[y:y+h,x:x+w].ravel()]
            for plane in (1,2):
                offset=e.W*e.H+(plane-1)*e.W*e.H//4
                row.append(frame[offset:offset+e.W*e.H//4].reshape(e.H//2,e.W//2)[y//2:(y+h)//2,x//2:(x+w)//2].ravel())
            planes.append(e.np.concatenate(row))
        native.append(e.np.stack(planes))
    for frame in e.decode(path,'steady_boundary_source'):
        for i,c in enumerate(candidates):
            x,y,w,h=c['bbox'];patches[i].append(frame[y:y+h,x:x+w].copy())
    accepted=[]
    for i,c in enumerate(candidates):
        rgb=e.np.stack(patches[i]);linear=e.np.array([float(e.cv2.mean(e.cv2.transform(e.cv2.LUT(p,e.LUT),e.WEIGHTS))[0]) for p in rgb])
        aligned=select(c,rgb,linear,native[i],e.np,e.guard)
        if aligned is None:found['boundary_refusals'].append({'id':c['id'],'bbox':c['bbox'],'interval_frames':c['interval_frames'],'reason':'No same-appearance observed reference and bounded cuts satisfy predicted non-worsening boundaries plus the minimum useful hold.'})
        else:accepted.append(aligned)
    found['candidates']=accepted
    return found


def encoded_measurements(samples,lo,hi,n,np):
    result={}
    for name,a,b in [('entry',(lo-1)%n,lo),('exit',hi,(hi+1)%n),('loop_seam',n-1,0)]:
        result[name]={}
        for region in ('selected','influence'):
            source=metrics(samples[a]['source'][region],samples[b]['source'][region],np)
            edited=metrics(samples[a]['edited'][region],samples[b]['edited'][region],np)
            result[name][region]={'source':source,'edited':edited,'passed':not_worse(source,edited)}
    return {'policy':POLICY,'measurements':result,'passed':all(v['passed'] for r in result.values() for v in r.values()),'scope':'Entry, return and clip-loop boundary; selected and influence boxes; mean absolute, RMS and maximum decoded RGB differences must each be no greater than source (1e-12 floating comparison tolerance, no perceptual budget). This is not a safety or human-benefit measure.'}
