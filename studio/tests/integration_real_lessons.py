"""Real, licensed lesson intake over HTTP, plus an explicitly augmented edit challenge."""
from pathlib import Path
import hashlib,json,sys,subprocess,threading,time,urllib.request,urllib.error
import numpy as np
STUDIO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STUDIO));import run as studio
sys.path.insert(0,str(studio.APP));from common import validate_probe
from native_yuv import support_masks
import engine
OUT=Path(sys.argv[1]);OUT.mkdir(exist_ok=False)
LESSONS=Path(sys.argv[2]) if len(sys.argv)>2 else STUDIO/'fixtures'
server=studio.make_studio_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token=''
def req(path,data=None,expect=200,raw=False,headers=None):
 h=dict(headers or {})
 if data is not None:h['X-App-Token']=token
 if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=h),timeout=30) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 assert status==expect,(status,body[:500]);return body if raw else json.loads(body)
def poll(jid):
 until=time.monotonic()+300
 while time.monotonic()<until:
  j=req('/api/jobs/'+jid)
  if j['status'] not in ('queued','analyzing','exporting'):return j
  time.sleep(.3)
 raise TimeoutError(jid)
def cmd(args):return subprocess.check_output(args)
def pcm(path,start=None):
 args=['ffmpeg','-v','error','-threads','1']
 if start is not None:args+=['-ss',str(start)]
 return np.frombuffer(cmd(args+['-i',str(path),'-t','12','-map','0:a:0','-ac','1','-ar','48000','-f','f32le','pipe:1']),np.float32)
def audio_correlation(a,b):
 a=a[::6].astype(np.float64);b=b[::6].astype(np.float64);best=(-1,None)
 for lag in range(-80,81):
  x,y=(a[-lag:],b[:len(b)+lag]) if lag<0 else (a[:len(a)-lag],b[lag:])
  n=min(len(x),len(y));x=x[:n]-x[:n].mean();y=y[:n]-y[:n].mean()
  c=float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-15))
  if c>best[0]:best=(c,lag/8000)
 return {'correlation':best[0],'lag_seconds':best[1]}
def upload(path,start=40):
 return poll(req('/api/imports',path.read_bytes(),202,headers={'X-Filename':path.name,'X-Clip-Start':str(start),'X-Clip-Duration':'12'})['id'])
records=[]
try:
 token=req('/api/profile')['csrf_token']
 req('/api/imports',b'#EXTM3U\nhttps://example.com/video',400)
 refused=poll(req('/api/imports',b'\x1aE\xdf\xa3invalid',202,headers={'X-Clip-Duration':'12'})['id'])
 assert refused['status']=='failed' and not refused['artifacts']
 print('Malformed WebM refused without export',flush=True)
 names=['real-teacher.webm'] if not (LESSONS/'ittt-present-simple.webm').exists() else ['ittt-present-simple.webm']
 if (LESSONS/'wiki-citations.webm').exists():names.append('wiki-citations.webm')
 for name in names:
  original=LESSONS/name;j=upload(original);print(name,j['status'],len(j.get('candidates',[])),j.get('error'),flush=True)
  assert j['status']=='review',j
  jid=j['id'];folder=OUT/'jobs'/jid
  meta=json.loads(cmd(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(folder/'input.mp4')]))
  validate_probe(meta)
  correlation=audio_correlation(pcm(original,40),pcm(folder/'input.mp4'));assert correlation['correlation']>.98,correlation
  assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/upload',raw=True)).hexdigest()==hashlib.sha256(original.read_bytes()).hexdigest()
  assert req('/api/jobs/'+jid+'/intake/preview',raw=True).startswith(b'\x89PNG')
  assert not (folder/'approval.json').exists()
  if j['candidates']:
   candidate=j['candidates'][0];body={'candidate_id':candidate['id'],'prediction_sha256':j['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':[]}
   p=req('/api/jobs/'+jid+'/plan',body)
   req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':p['recipe_sha256']},202)
   final=poll(jid);print('natural candidate outcome',final['status'],final.get('error'),flush=True)
  else:
   final=req('/api/jobs/'+jid+'/decline',{},200);final=poll(jid)
   prepared=req('/api/jobs/'+jid+'/download/original.mp4',raw=True)
   assert hashlib.sha256(prepared).hexdigest()==j['preparation']['prepared_sha256']
   assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/upload',raw=True)).hexdigest()==j['preparation']['uploaded_sha256']
  record={'source':name,'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'preparation':j['preparation'],'candidates':len(j['candidates']),'outcome':final['status'],'error':final.get('error'),'audio_preparation_correlation':correlation,'uploaded_original_download_exact':True,'no_approval_from_preparation':True}
  records.append(record)
  if name in ('real-teacher.webm','ittt-present-simple.webm'):teacher=folder/'input.mp4'
 # Add a disclosed flashing corner to existing black letterbox. The lesson and
 # narration are real; this artifact is controlled and is not a natural defect.
 challenge=OUT/'real-teacher-controlled-decoration.mp4'
 cmd(['ffmpeg','-v','error','-y','-threads','1','-filter_threads','1','-i',str(teacher),'-vf',"drawbox=x=588:y=260:w=32:h=32:color=0xededed:t=fill:enable='between(n,30,329)*lt(mod(n,6),3)'",'-c:v','libx264','-qp','0','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-chroma_sample_location','left','-video_track_timescale','15360','-c:a','copy',str(challenge)])
 j=upload(challenge,0);print('augmented challenge',j['status'],[(c['id'],c['bbox']) for c in j.get('candidates',[])],flush=True);assert j['status']=='review',j
 candidate=next(c for c in j['candidates'] if c['bbox'][0]>=580)
 jid=j['id'];folder=OUT/'jobs'/jid
 areas=[{'label':'Real teacher and whiteboard','xywh':[80,0,480,360]}]
 body={'candidate_id':candidate['id'],'prediction_sha256':j['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':areas}
 plan=req('/api/jobs/'+jid+'/plan',body);req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':plan['recipe_sha256']},202)
 final=poll(jid);print('challenge final',final['status'],final.get('error'),flush=True);assert final['status']=='complete',final
 output=OUT/'edited-real-teacher.mp4';output.write_bytes(req('/api/jobs/'+jid+'/download/edited.mp4',raw=True));report=req('/api/jobs/'+jid+'/download/report.json')
 assert hashlib.sha256(output.read_bytes()).hexdigest()==report['output_hashes']['edited']
 def native(path):return np.frombuffer(cmd(['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
 original=native(folder/'input.mp4');edited=native(output)
 prediction=json.loads((folder/'prediction.json').read_text());component=prediction['components'][int(candidate['id'])]
 engine.W,engine.H=640,360;mask=engine.unpack_mask(component['mask_rle'],[360,640]);ym,cm=support_masks(mask);support=np.concatenate([ym.ravel(),cm.ravel(),cm.ravel()]).astype(bool)
 mapping=np.array(json.loads((folder/'result.json').read_text())['recipe']['mapping'])
 assert np.array_equal(original[:,~support],edited[:,~support]);assert np.array_equal(original[mapping][:,support],edited[:,support])
 assert np.array_equal(pcm(folder/'input.mp4'),pcm(output))
 decoders=[subprocess.Popen(['ffmpeg','-v','error','-threads','1','-i',str(p),'-map','0:v:0','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE) for p in [folder/'input.mp4',output]]
 for t in range(360):
  frames=[np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3) for p in decoders]
  assert np.array_equal(frames[0][:,80:560],frames[1][:,80:560]),t
 assert all(p.wait()==0 for p in decoders)
 for row in final['frame_review']['rows']:
  for asset in row['images'].values():assert hashlib.sha256(req(asset['url'],raw=True)).hexdigest()==asset['sha256']
 records.append({'source':'Real ITTT teacher + explicitly added controlled flashing corner','scope':'Augmented real-footage challenge; defect is authored, lesson and narration are real','outcome':'complete','independent_outside_native_exact':True,'independent_native_mapping_exact':True,'all_360_real_teacher_whiteboard_frames_rgb_exact':True,'human_audio_pcm_exact_vs_prepared_source':True,'all_12_crop_response_hashes_exact':True,'output_sha256':report['output_hashes']['edited'],'preparation':j['preparation'],'summary':final['summary']})
 (OUT/'results.json').write_text(json.dumps(records,indent=2));print('REAL LESSON WORKFLOW COMPLETE',flush=True)
finally:server.shutdown();thread.join();server.manager.close();server.server_close();(OUT/'partial-results.json').write_text(json.dumps(records,indent=2))
