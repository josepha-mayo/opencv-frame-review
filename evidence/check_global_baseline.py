"""A controlled whole-clip slowdown comparison, not a manual-editor or user study."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path('/demo/02-source.mp4'))
parser.add_argument('--edited',type=Path,default=Path('/demo/06-edited.mp4'))
parser.add_argument('--output-directory',type=Path,default=Path('/demo'))
args=parser.parse_args()
D=args.output_directory;D.mkdir(parents=True,exist_ok=True)
source=args.source;local=args.edited;glob=D/'whole-clip-5x.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-threads','1','-i',str(source),'-vf','setpts=5*PTS,tpad=stop_mode=clone:stop_duration=0.2,fps=fps=30:round=down','-af','atempo=0.5,atempo=0.5,atempo=0.8,apad,atrim=duration=60','-c:v','libx264','-qp','0','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-chroma_sample_location','left','-r','30','-fps_mode','cfr','-t','60','-c:a','aac','-ac','1','-ar','48000','-b:a','96k','-video_track_timescale','15360',str(glob)],check=True)
def info(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,duration,nb_read_frames:format=duration','-of','json',str(path)]))
def patch(path,frame):
    return subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),crop=205:36:20:250','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
a,b,c=info(source),info(local),info(glob)
assert float(a['format']['duration'])==12 and float(b['format']['duration'])==12 and float(c['format']['duration'])==60
assert int(next(s for s in c['streams'] if s['codec_type']=='video')['nb_read_frames'])==1800
old=patch(source,89);new=patch(source,90);assert old!=new
assert patch(local,89)==old and patch(local,90)==new
assert patch(glob,449)==old and patch(glob,450)==new
record={'scope':'Controlled whole-clip baseline on one authored fixture; no user, time-savings or manual-editor comparison','source_duration_seconds':12,'local_edit_duration_seconds':12,'whole_clip_5x_duration_seconds':60,'first_step_counter_change_seconds':{'source':3,'local_edit':3,'whole_clip_5x':15},'counter_patch_bytes_match_at_compared_frames':True,'whole_clip_baseline_video_frames':1800,'whole_clip_baseline_sha256':hashlib.sha256(glob.read_bytes()).hexdigest()}
(D/'global-baseline.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
