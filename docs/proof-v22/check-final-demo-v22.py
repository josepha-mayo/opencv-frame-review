from pathlib import Path
import subprocess,json,hashlib
from PIL import Image,ImageDraw,ImageFont,ImageOps
W=Path(__file__).resolve().parent;O=W.parent/'outputs/final-demo-v22';v=O/'Frame-Review-Creator-Demo.mp4'
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-f','null','-'],check=True)
r=json.loads((O/'video-receipt.json').read_text());assert r['video_sha256']==hashlib.sha256(v.read_bytes()).hexdigest()
canvas=Image.new('RGB',(1280,9*205),'#ddd');d=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
timeline=json.loads((O/'timeline.json').read_text())
for i,row in enumerate(timeline['chapters']):
 t=(row['start']+row['end'])/2;out=O/('qc-'+row['scene']+'.png');subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(v),'-frames:v','1',str(out)],check=True)
 im=ImageOps.contain(Image.open(out),(640,180));x=(i%2)*640;y=(i//2)*205;canvas.paste(im,(x,y));d.text((x+8,y+181),f'{t:.1f}s  {row["scene"]}',font=font,fill='black')
canvas.save(O/'contact-sheet.png');r['full_av_decode_passed']=True;r['qc_frames']=len(timeline['chapters']);(O/'video-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('Full A/V decode passed; 17 actual encoded scene frames extracted for visual inspection.')
