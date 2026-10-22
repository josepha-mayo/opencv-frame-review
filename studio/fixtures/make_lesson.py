"""Generate an authored 12-second lesson; supply the documented neural narration MP3.

Run inside the pinned image: python studio/fixtures/make_lesson.py /path/narration.mp3 /path/lesson.mp4
The prepared fixture is synthetic educational media, not a real teacher study.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import cv2
import numpy as np

W, H, N = 640, 360, 360

def text(frame, value, x, y, scale=.55, color=(222, 230, 237), thickness=1):
    cv2.putText(frame, value, (x,y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def frame_at(t):
    f = np.full((H,W,3), (16,26,39), np.uint8)
    text(f,'A LINE, ONE STEP AT A TIME',26,34,.57,(106,220,183),1)
    text(f,'y = -2x + 1',26,94,1.05,(245,247,243),2)
    text(f,'Start at (0, 1)',27,139,.54)
    text(f,'Right 1. Down 2.',27,171,.54)
    text(f,'Slope = -2',27,203,.54,(106,220,183))
    # Fixed instructional graph; only its step marker and counter change.
    ox, oy, unit = 416,161,37
    for gx in range(305,602,unit): cv2.line(f,(gx,64),(gx,240),(32,47,60),1)
    for gy in range(87,241,unit): cv2.line(f,(305,gy),(601,gy),(32,47,60),1)
    cv2.line(f,(305,oy),(605,oy),(139,160,175),1)
    cv2.line(f,(ox,64),(ox,244),(139,160,175),1)
    text(f,'x',607,166,.45); text(f,'y',411,59,.45)
    cv2.line(f,(379,50),(453,198),(106,220,183),2)
    step=min(3,t//90)
    if step>=1: cv2.circle(f,(ox,oy-unit),5,(242,218,124),-1)
    if step>=2:
        cv2.line(f,(ox,oy-unit),(ox+unit,oy-unit),(242,218,124),2)
        cv2.line(f,(ox+unit,oy-unit),(ox+unit,oy+unit),(242,218,124),2)
        cv2.circle(f,(ox+unit,oy+unit),5,(242,218,124),-1)
    text(f,'STEP '+str(step+1)+' / 4',27,276,.6,(242,218,124),1)
    text(f,'Authored demo | neural narration',27,326,.43,(151,168,179))
    text(f,'DECORATION',520,247,.36,(151,168,179))
    # Deliberately distracting decoration: an exactly repeating observed cycle,
    # separate from every instructional area. At 5x retime its cycle slows.
    level=230 if 33<=t<=330 and (t-33)%6<3 else 50
    f[260:300,548:588]=level
    return f

def main():
    narration, output = map(Path,sys.argv[1:])
    if output.exists(): raise RuntimeError('Refusing to overwrite a fixture')
    duration=float(json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_entries','format=duration','-of','json',str(narration)]))['format']['duration'])
    if duration>12: raise ValueError('Narration would be truncated; shorten it before generation')
    with tempfile.TemporaryDirectory() as temp:
        silent=Path(temp)/'silent.mp4'
        cmd=['/usr/bin/ffmpeg','-v','error','-n','-threads','1','-filter_threads','1','-f','rawvideo','-pixel_format','rgb24','-video_size','640x360','-framerate','30','-i','pipe:0','-vf','scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=pc:out_range=tv:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-an','-c:v','libx264','-preset','veryfast','-qp','18','-aq-mode','0','-psy','0','-rc-lookahead','0','-bf','0','-g','30','-keyint_min','30','-sc_threshold','0','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-chroma_sample_location','left','-fps_mode','passthrough','-video_track_timescale','15360','-frames:v',str(N),str(silent)]
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        for t in range(N): p.stdin.write(frame_at(t).tobytes())
        p.stdin.close()
        if p.wait(): raise RuntimeError('Lesson video encoding failed')
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-n','-i',str(silent),'-i',str(narration),'-map','0:v','-map','1:a','-c:v','copy','-af','aresample=48000,apad,atrim=duration=12','-ac','1','-c:a','aac','-b:a','96k','-video_track_timescale','15360',str(output)],check=True)
    print('Created an authored synthetic math lesson. Creator benefit is not established.')

if __name__=='__main__': main()
