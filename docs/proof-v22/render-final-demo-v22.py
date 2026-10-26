"""Compose actual app captures and measured video masters around creator audio."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime,hashlib,json,subprocess
from PIL import Image,ImageOps,ImageDraw,ImageFont
W=Path(__file__).resolve().parent;O=W.parent/'outputs/final-demo-v22';SCREEN=O/'screens';P=W.parent/'outputs/proof-v22/native'
timeline=json.loads((O/'timeline.json').read_text());build=json.loads((W/'proof-v22-build-verified.json').read_text());assert build['complete']
if not any(x['scene']=='pack'for x in timeline['chapters']):
 i=next(i for i,x in enumerate(timeline['chapters'])if x['scene']=='inspect');end=timeline['chapters'][i]['end'];timeline['chapters'][i]['end']=116.0;timeline['chapters'].insert(i+1,{'scene':'pack','start':116.0,'end':end});(O/'timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
assert json.loads((W/'proof-v22-rollout.json').read_text())['complete']
def fit(im,box):
 image=Image.open(im).convert('RGB');image=ImageOps.contain(image,(box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS);return image,(box[0]+(box[2]-box[0]-image.width)//2,box[1]+(box[3]-box[1]-image.height)//2)
def combine(base,shot,target,box,crop=None):
 im=Image.open(O/(base+'.png')).convert('RGB');source=Image.open(SCREEN/shot).convert('RGB')
 if crop:source=source.crop(crop)
 image=ImageOps.contain(source,(box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS);xy=(box[0]+(box[2]-box[0]-image.width)//2,box[1]+(box[3]-box[1]-image.height)//2);im.paste(image,xy);im.save(O/(target+'.png'))
combine('01-title','home.png','title-live',(906,410,1794,848))
for target,shot,crop in [('timestamp','timestamp.png',(390,250,810,900)),('states','states.png',(844,100,1450,880)),('plan','plan.png',(840,0,1450,950))]:combine('03-workflow',shot,target+'-live',(821,341,1818,968),crop)
combine('05-inspect','teaching-desk.png','inspect-live',(772,350,1818,969),(410,110,1430,670))
combine('05-inspect','offline-proof.png','offline-live',(772,350,1818,969))
combine('05-inspect','pack-checked.png','pack-live',(772,350,1818,969),(400,305,1445,810))
combine('09-recovery','recovery.png','recovery-live',(850,395,1818,970))
im=Image.open(O/'recovery-live.png');d=ImageDraw.Draw(im);d.rectangle((65,1021,1850,1070),fill='#f4f5ef');d.text((72,1032),'Actual V21 SMW recovery card (cropped to own UI); current V22 native jEdit recovery separately verified.',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22),fill='#566b60');im.save(O/'recovery-live.png')
im=Image.open(O/'08-architecture.png').convert('RGB');d=ImageDraw.Draw(im);d.rectangle((65,330,1850,985),fill='#f4f5ef');bold=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',50);regular=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',30)
d.text((90,365),'14 Linux stages passed',font=bold,fill='#245941');d.text((90,470),'137 backend tests  •  139 studio tests (one platform skip)\n76 focused UI / compatibility checks\n3 untouched-original native/export regressions\n108 media / PNG members unchanged from V21',font=regular,fill='#193b30',spacing=30)
d.text((90,770),'CodeBuild: '+json.loads((W/'proof-v22-codebuild-start.json').read_text())['build']['id'].split(':')[-1],font=regular,fill='#566b60');d.text((90,835),'Pinned image: '+build['image_digest'],font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23),fill='#566b60');d.text((90,900),'Receipts and retained failures are included with the source.',font=regular,fill='#245941');im.save(O/'cloud-proof.png')

scene_cards={'title':'title-live','problem':'02-problem','real-source':'02-problem','timestamp':'timestamp-live','states':'states-live','plan':'plan-live','preservation':'04-preservation','inspect':'inspect-live','pack':'pack-live','offline':'offline-live','counterfactual':'06-counterfactual','results':'07-results','architecture':'08-architecture','cloud-proof':'cloud-proof','recovery':'recovery-live','negative-screen':'10-limits','limits':'10-limits','close':'11-close'}
for f in('prepared-lesson.mp4','edited.mp4'):
 assert (P/'gentoo/rescue-pack.zip').is_file()
import zipfile
with zipfile.ZipFile(P/'gentoo/rescue-pack.zip')as z:
 for f in('prepared-lesson.mp4','edited.mp4'):
  data=z.read(f);(O/('gentoo-'+f)).write_bytes(data)
french=W.parent/'outputs/workflow-v12/ablation/upload-assistant'
asset_hashes={str(p.relative_to(W.parent)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [O/'gentoo-prepared-lesson.mp4',O/'gentoo-edited.mp4',french/'prepared-lesson.mp4',french/'edited.mp4',french/'COUNTERFACTUAL-whole-frame-hold-video-only.mp4']}
def render(row):
 scene=row['scene'];duration=row['end']-row['start'];frames=round(duration*30);target=O/(scene+'.mp4');card=O/(scene_cards[scene]+'.png')
 args=['ffmpeg','-v','error','-y','-filter_complex_threads','1','-loop','1','-framerate','30','-i',str(card)]
 graph='[0:v]format=yuv420p[v]'
 if scene in('problem','real-source'):
  args+=['-stream_loop','-1','-i',str(O/'gentoo-prepared-lesson.mp4')]
  graph="[1:v]split=2[full][zoom];[full]scale=1200:675:flags=neighbor[clip];[zoom]crop=120:42:290:314,scale=720:252:flags=neighbor[detail];[0:v][clip]overlay=620:330:shortest=1[x];[x][detail]overlay=1080:735:shortest=1,drawbox=x=1074:y=704:w=732:h=31:color=white:t=fill,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Enlarged source pixels - progress and caret':fontsize=24:fontcolor=0x193b30:x=1082:y=707,format=yuv420p[v]"
 if scene=='counterfactual':
  for f in('prepared-lesson.mp4','edited.mp4','COUNTERFACTUAL-whole-frame-hold-video-only.mp4'):args+=['-stream_loop','-1','-i',str(french/f)]
  graph='[1:v]scale=540:304:flags=neighbor[a];[2:v]scale=540:304:flags=neighbor[b];[3:v]scale=540:304:flags=neighbor[c];[0:v][a]overlay=73:394[x];[x][b]overlay=690:394[y];[y][c]overlay=1307:394,format=yuv420p[v]'
 args+=['-filter_complex',graph,'-map','[v]','-an','-frames:v',str(frames),'-r','30','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(target)]
 with(O/(scene+'.render.log')).open('w')as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('Rendered',scene,frames,'frames',flush=True);return target
with ThreadPoolExecutor(max_workers=2)as pool:
 for future in as_completed([pool.submit(render,row)for row in timeline['chapters']]):future.result()
concat=O/'concat.txt';concat.write_text(''.join("file '"+str((O/(r['scene']+'.mp4')).resolve()).replace('\\','/')+"'\n"for r in timeline['chapters']),encoding='utf-8')
silent=O/'picture-track.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(silent)],check=True)
final=O/'Frame-Review-Creator-Demo.mp4';subprocess.run(['ffmpeg','-v','error','-y','-i',str(silent),'-i',str(O/'Joseph-normalized.wav'),'-filter_complex','[1:a]apad[a]','-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k','-ar','48000','-ac','1','-t',str(timeline['final_seconds']),'-movflags','+faststart',str(final)],check=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,r_frame_rate,duration','-of','json',str(final)]))
assert float(meta['format']['duration'])<300
record={'complete':True,'scope':'Creator-provided continuous narration at original speed, loudness-normalized; actual AWS/Brave screenshots, exact measured video masters played outside static UI, labelled diagrams/results and historical counterfactual. Presentation re-encoding is not media qualification.','narration_sha256':json.loads((O/'voice-and-captions-receipt.json').read_text())['source_audio_sha256'],'source_manifest_sha256':build['source_manifest_sha256'],'video_sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'bytes':final.stat().st_size,'format':meta,'scene_count':len(timeline['chapters']),'asset_hashes':asset_hashes,'rendered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(O/'video-receipt.json').write_text(json.dumps(record,indent=2)+'\n');print('Final demo',final,meta['format'],flush=True)
