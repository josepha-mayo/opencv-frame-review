"""Fixed whole-excerpt comparison, including old cuts and negative tradeoffs."""
from pathlib import Path
import json,hashlib,subprocess,sys
import numpy as np,cv2
sys.path.insert(0,'/app/opencv-ready/candidate/app');import engine
root=Path('/evidence');old=Path('/old');out=root/'comparisons';out.mkdir(exist_ok=False)
rows=[]
for name in ('jupyter','npm-packages','npm-basics','wikilink','wiki-citations','terminal'):
    folder=root/'originals'/name;q=json.loads((folder/'results.json').read_text());assert q['complete']
    prior=json.loads((old/'originals'/name/'results.json').read_text());assert prior['complete']
    assert q['preparation']['prepared_sha256']==prior['preparation']['prepared_sha256']
    c=q['candidate'];x,y,w,h=c['bbox'];lo,hi=c['interval_frames'];ix,iy,iw,ih=c['influence_xywh']
    paths={'source':folder/'jobs'/q['job_id']/'input.mp4','spatial_blur':root/'blur-references'/name/'blur-baseline.mp4','matched_hold':folder/'edited-natural.mp4','prior_fixed_hold':old/'originals'/name/'edited-natural.mp4'}
    traces={};source_events=None
    for label,path in paths.items():
        raw=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(path),'-an','-vf',engine.DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(360,360,640,3)
        roi=raw[:,y:y+h,x:x+w].astype(float);values=roi.mean(axis=(1,2,3));delta=np.abs(np.diff(values));events=set((np.where(delta>=8)[0]+1).tolist())
        if label=='source':source_events=events
        contrast_frame=max(lo,min(hi,c['reference_frame']));context=raw[contrast_frame,iy:iy+ih,ix:ix+iw].astype(float);ring=np.ones((ih,iw),bool);ring[y-iy:y+h-iy,x-ix:x+w-ix]=False
        contrast=float(np.abs(roi[contrast_frame]-np.median(context[ring],axis=0)).mean())
        traces[label]={'roi_mean_rgb_codes':values.tolist(),'whole_excerpt_changes':len(events),'event_frames':sorted(events),'new_event_frames':sorted(events-source_events),'interior_changes':int((np.abs(np.diff(values[lo:hi+1]))>=8).sum()),'pixel_temporal_mae':float(np.abs(np.diff(roi,axis=0)).mean()),'pixel_temporal_mse':float((np.diff(roi,axis=0)**2).mean()),'contrast_frame':contrast_frame,'contrast_against_ring':contrast}
        if label=='source':
            cv2.imwrite(str(out/(name+'-reference.png')),raw[c['reference_frame'],:,:,::-1]);cv2.imwrite(str(out/(name+'-alternate.png')),raw[c['alternate_frame'],:,:,::-1])
        del raw,roi
    assert not traces['matched_hold']['new_event_frames']
    assert traces['matched_hold']['whole_excerpt_changes']<traces['source']['whole_excerpt_changes']
    assert traces['matched_hold']['interior_changes']==0
    row={'case':name,'candidate':c,'prior_candidate':prior['candidate'],'prepared_sha256':q['preparation']['prepared_sha256'],'edited_sha256':q['output_sha256'],'times_seconds':(np.arange(360)/30).tolist(),'traces':traces,'boundary':q['summary']['boundary'],'independent_boundaries':q.get('independent_boundaries_not_worse'),'scope':'Same full 12 seconds and selected ROI; old hold used different, longer cuts. Eight-code ROI-mean changes are an engineering proxy, not measured attention or learning.'}
    rows.append(row);(out/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n');print(name,{k:(v['whole_excerpt_changes'],len(v['new_event_frames'])) for k,v in traces.items()},flush=True)
totals={k:sum(r['traces'][k]['whole_excerpt_changes'] for r in rows) for k in paths}
(out/'results.json').write_text(json.dumps({'complete':True,'runtime_manifest_sha256':hashlib.sha256(Path('/app/studio/BUILD_HASHES.json').read_bytes()).hexdigest(),'fixed_exposure_seconds':72,'totals':totals,'held_seconds':sum(r['candidate']['interval_frames'][1]-r['candidate']['interval_frames'][0]+1 for r in rows)/30,'cases':rows},indent=2)+'\n')
