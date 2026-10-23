"""Actual encoded traces and reference-state images; no user benefit inference."""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np,cv2
sys.path.insert(0,'/app/opencv-ready/candidate/app');import engine
root=Path('/evidence');out=root/'comparisons';out.mkdir(exist_ok=False)
records=[]
for name in ('jupyter','npm-packages','npm-basics','wikilink','wiki-citations','terminal'):
    folder=root/'originals'/name
    qualified=json.loads((folder/'results.json').read_text());assert qualified['complete']
    baseline=json.loads((root/'blur-references'/name/'results.json').read_text())
    c=qualified['candidate'];lo,hi=c['interval_frames'];x,y,w,h=c['bbox'];ix,iy,iw,ih=c['influence_xywh']
    paths={'source':folder/'jobs'/qualified['job_id']/'input.mp4','spatial_blur':root/'blur-references'/name/'blur-baseline.mp4','observed_state_hold':folder/'edited-natural.mp4'}
    traces={};contrast={}
    for label,file in paths.items():
        command=['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(file),'-an','-vf',engine.DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1']
        raw=np.frombuffer(subprocess.check_output(command),np.uint8).reshape(360,360,640,3)
        values=raw[lo:hi+1,y:y+h,x:x+w].mean(axis=(1,2,3))
        traces[label]={'roi_mean_rgb_codes':values.tolist(),'adjacent_changes_at_least_8_rgb_codes':int((np.abs(np.diff(values))>=8).sum()),'peak_to_peak_rgb_codes':float(np.ptp(values)),'adjacent_rms_rgb_codes':float(np.sqrt(np.mean(np.diff(values)**2)))}
        image=raw[c['reference_frame']];context=image[iy:iy+ih,ix:ix+iw].astype(float)
        ring=np.ones((ih,iw),bool);ring[y-iy:y+h-iy,x-ix:x+w-ix]=False
        background=np.median(context[ring],axis=0)
        contrast[label]=float(np.abs(image[y:y+h,x:x+w].astype(float)-background).mean())
        if label=='source':
            cv2.imwrite(str(out/(name+'-reference.png')),image[:,:,::-1])
            cv2.imwrite(str(out/(name+'-alternate.png')),raw[c['alternate_frame'],:,:,::-1])
    expected=qualified['summary']['stationary_detail']['activity']
    assert traces['source']['adjacent_changes_at_least_8_rgb_codes']==expected['source']
    assert traces['observed_state_hold']['adjacent_changes_at_least_8_rgb_codes']==expected['edited']==0
    assert traces['spatial_blur']['adjacent_changes_at_least_8_rgb_codes']==baseline['traces']['spatial_blur']['adjacent_roi_mean_changes_at_least_8_rgb_codes']
    row={'case':name,'candidate':c,'prepared_sha256':qualified['preparation']['prepared_sha256'],'output_sha256':qualified['output_sha256'],'interval_interior_only':True,'times_seconds':(np.arange(lo,hi+1)/30).tolist(),'traces':traces,'reference_rgb_contrast_against_ring':contrast,'boundaries':qualified['summary']['boundary']}
    records.append(row);(out/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n')
    print(name,{key:value['adjacent_changes_at_least_8_rgb_codes'] for key,value in traces.items()},flush=True)
(out/'results.json').write_text(json.dumps({'complete':True,'scope':'Six selected four-second intervals, no added defect. Interval-interior activity and reference-state contrast, not attention, comprehension, safety or time-saving evidence.','cases':records},indent=2)+'\n')
