from pathlib import Path
import json,subprocess,sys
import numpy as np
sys.path.insert(0,'/app/studio');import run as studio
sys.path.insert(0,str(studio.APP));import engine
root=Path('/evidence');qualified=json.loads((root/'tamil/results.json').read_text())
baseline=json.loads((root/'blur-reference-final/results.json').read_text())
c=qualified['candidate'];x,y,w,h=c['bbox'];lo,hi=c['interval_frames']
path=root/'tamil/edited-natural.mp4'
process=subprocess.Popen(['ffmpeg','-v','error','-nostdin','-threads','1','-filter_threads','1','-i',str(path),'-an','-vf',engine.DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)
steady=[]
for t in range(360):
    frame=np.frombuffer(process.stdout.read(640*360*3),np.uint8).reshape(360,640,3)
    if lo<=t<=hi:steady.append(float(frame[y:y+h,x:x+w].mean()))
assert process.wait()==0
traces={k:v['roi_mean_rgb_codes'] for k,v in baseline['traces'].items()}
traces['observed_state_hold']=steady
record={'schema':'natural-reading-detail-comparison-v1','input_sha256':baseline['source_sha256'],
        'source_original_sha256':qualified['source_sha256'],'excerpt_start_seconds':qualified['start_seconds'],
        'frame_interval_inclusive':[lo,hi],'roi_xywh':c['bbox'],'times_in_excerpt_seconds':[t/30 for t in range(lo,hi+1)],
        'activity_threshold_rgb_codes':8,'traces':traces,
        'adjacent_roi_mean_change_counts':{k:int((np.abs(np.diff(v))>=8).sum()) for k,v in traces.items()},
        'output_sha256':{'spatial_blur':baseline['output_sha256'],'observed_state_hold':qualified['output_sha256']},
        'scope':'One targeted real lesson interval. Not a user study, prevalence benchmark, complete editor comparison or medical measurement. Entry/return excluded from this count; their separate reported values remain visible.'}
assert record['adjacent_roi_mean_change_counts']=={'source':6,'spatial_blur':6,'observed_state_hold':0}
(root/'comparison.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record['adjacent_roi_mean_change_counts']))
