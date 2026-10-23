"""The decoded boundary gate must reject the previous real fixed-window hold.

Uses the licensed bundled Jupyter excerpt with its natural blink. The intentionally
bad encoded output is a regression artifact, never an accepted product repair.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np
STUDIO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STUDIO));import steady_detail,steady_boundaries
sys.path.insert(0,str(STUDIO.parent/'opencv-ready/candidate/app'));import engine,cv2
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
source=STUDIO/'fixtures/natural-jupyter.mp4'
raw=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(source),'-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
candidate=next(c for c in steady_detail.detect_native(raw,640,360,cv2,np)['candidates'] if c['bbox']==[116,148,2,8])
lo,hi=candidate['interval_frames'];ref=candidate['reference_frame'];assert [lo,hi]==[0,119]
x,y,w,h=candidate['bbox'];ix,iy,iw,ih=candidate['influence_xywh']
edited=raw.copy()
for offset,pw,ph,px,py,bw,bh in [(0,640,360,x,y,w,h),(640*360,320,180,x//2,y//2,w//2,h//2),(640*360+320*180,320,180,x//2,y//2,w//2,h//2)]:
    planes=edited[:,offset:offset+pw*ph].reshape(360,ph,pw)
    planes[lo:hi+1,py:py+bh,px:px+bw]=planes[ref,py:py+bh,px:px+bw].copy()
target=out/'known-bad-fixed-window.mp4'
command=['ffmpeg','-v','error','-threads','1','-f','rawvideo','-pixel_format','yuv420p','-video_size','640x360','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-qp','0','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-chroma_sample_location','left',str(target)]
subprocess.run(command,input=edited.tobytes(),check=True)
samples={t:{} for t in (0,119,120,359)}
for role,path in [('source',source),('edited',target)]:
    p=subprocess.Popen(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(path),'-an','-vf',engine.DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)
    for t in range(360):
        frame=np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3)
        if t in samples:samples[t][role]={'selected':frame[y:y+h,x:x+w].copy(),'influence':frame[iy:iy+ih,ix:ix+iw].copy()}
    assert p.wait()==0
measured=steady_boundaries.encoded_measurements(samples,lo,hi,360,np)
assert measured['passed'] is False
assert measured['measurements']['exit']['selected']['passed'] is False
assert measured['measurements']['loop_seam']['selected']['passed'] is False
record={'complete':True,'purpose':'Real encoded negative regression: prior fixed-window Jupyter hold must fail new boundary acceptance. No human-benefit claim.','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bad_output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'candidate':candidate,'encoded_boundary_checks':measured,'bad_output_rejected':True}
(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
print('REAL FIXED-WINDOW BOUNDARY REGRESSION REJECTED',flush=True)
