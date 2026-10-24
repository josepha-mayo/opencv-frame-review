"""Reproduce the number-pixel comparison from the included hash-bound test clips.

Mount this document folder at /audit in the current pinned runtime and run
python /audit/verify-number-media.py. No network, original download or playback.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np
sys.path.insert(0,'/app/studio');import run
run.check_source();run.check_runtime()
sys.path.insert(0,str(run.APP));import engine
root=Path(__file__).resolve().parent/'media';files=json.loads((root/'files.json').read_text())
names=['prepared-reference.mp4','rejected-previous-mapping.mp4','current-observed-luma.mp4']
for name in names:
    data=(root/name).read_bytes();assert len(data)==files[name]['bytes']and hashlib.sha256(data).hexdigest()==files[name]['sha256']
pipes=[subprocess.Popen(['ffmpeg','-v','error','-nostdin','-threads','1','-filter_threads','1','-protocol_whitelist','file,pipe','-i',str(root/name),'-map','0:v:0','-an','-vf',engine.DECODE_FILTER,'-frames:v','360','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)for name in names]
stats=[{'changed_frames':0,'changed_pixel_frames':0,'maximum_rgb_code_error':0,'first_changed_frame':None}for _ in range(2)]
for frame in range(360):
    images=[]
    for pipe in pipes:
        data=pipe.stdout.read(640*360*3);assert len(data)==640*360*3
        images.append(np.frombuffer(data,np.uint8).reshape(360,640,3)[254:276,180:194].astype(np.int16))
    for stat,image in zip(stats,images[1:]):
        delta=np.abs(image-images[0]);changed=int((delta.max(axis=2)>0).sum())
        stat['changed_frames']+=int(changed>0);stat['changed_pixel_frames']+=changed;stat['maximum_rgb_code_error']=max(stat['maximum_rgb_code_error'],int(delta.max()))
        if changed and stat['first_changed_frame']is None:stat['first_changed_frame']=frame
assert all(p.wait(timeout=20)==0 for p in pipes)
assert stats[0]['changed_frames']>0 and stats[1]['changed_frames']==0
print(json.dumps({'scope':'All360 decoded number-ROI frames, prepared reference versus included rejected/current artifacts. RGB sample differences, not semantic-number or human-benefit evidence.','xywh':[180,254,14,22],'previous':stats[0],'current':stats[1]},indent=2))
