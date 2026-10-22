"""Owned length fixtures and actual HTTP approval/export/download plus independent bytes."""
import hashlib,json,pathlib,sys,threading,time,urllib.request,urllib.error,subprocess
import numpy as np
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from server import make_server
OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(exist_ok=False)
F=OUT/'fixtures';F.mkdir()
CASES=[(320,180,30,False),(320,180,123,True),(320,180,360,True),(640,360,72,False),(640,360,270,True),(640,360,360,True)]
def run(args,**kw):return subprocess.run(args,check=True,stdout=subprocess.PIPE,**kw).stdout
for w,h,n,audio in CASES:
 name=f'{w}-{n}';video=F/(name+'-silent.mp4')
 args=['/usr/bin/ffmpeg','-v','error','-n','-threads','1','-filter_threads','1','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate','30','-i','pipe:0','-vf','scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=pc:out_range=tv:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-an','-c:v','libx264','-preset','veryfast','-qp','18','-aq-mode','0','-psy','0','-rc-lookahead','0','-bf','0','-g','30','-keyint_min','30','-sc_threshold','0','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-chroma_sample_location','left','-fps_mode','passthrough','-video_track_timescale','15360','-frames:v',str(n),str(video)]
 p=subprocess.Popen(args,stdin=subprocess.PIPE)
 for t in range(n):
  f=np.full((h,w,3),50,np.uint8);f[10:30,10:90]=180
  f[h//2:h//2+32,w*3//4:w*3//4+32]=230 if 3<=t and ((t-3)//2)%2==0 else 50
  p.stdin.write(f.tobytes())
 p.stdin.close();assert p.wait()==0
 if audio:run(['/usr/bin/ffmpeg','-v','error','-n','-i',str(video),'-f','lavfi','-i',f'sine=frequency=440:sample_rate=48000:duration={n/30}','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','96k','-video_track_timescale','15360',str(F/(name+'.mp4'))])
 else:(F/(name+'.mp4')).write_bytes(video.read_bytes())
server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_address[1]}'
def req(path,data=None,expect=200,raw=False):
 h={}
 if data is not None:h['X-App-Token']=token
 if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers=h),timeout=20) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 assert status==expect,(status,body)
 return body if raw else json.loads(body)
def poll(jid):
 until=time.monotonic()+250
 while time.monotonic()<until:
  j=req('/api/jobs/'+jid)
  if j['status'] not in ('queued','analyzing','exporting'):return j
  time.sleep(.2)
 raise TimeoutError(jid)
def decode(path,w,h,n):
 raw=run(['/usr/bin/ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-pix_fmt','yuv420p','-f','rawvideo','pipe:1'])
 assert len(raw)==n*w*h*3//2
 return np.frombuffer(raw,np.uint8).reshape(n,-1)
def audio_data(path):
 packets=json.loads(run(['/usr/bin/ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_streams','-show_data_hash','sha256','-show_entries','stream=codec_name,profile,sample_rate,channels,channel_layout,time_base,start_pts,duration_ts,extradata_hash:packet=pts,dts,duration,size,flags,data_hash,side_data_list','-of','json',str(path)]))
 pcm=run(['/usr/bin/ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1'])
 return packets,hashlib.sha256(pcm).hexdigest(),len(pcm)
results=[]
try:
 token=req('/api/profile')['csrf_token']
 for w,h,n,audio in CASES:
  source=F/f'{w}-{n}.mp4';j=poll(req('/api/jobs',source.read_bytes(),202)['id']);assert j['status']=='review' and j['candidates'],j
  jid=j['id'];folder=OUT/'jobs'/jid
  assert not (folder/'approval.json').exists() and not (folder/'edited.mp4').exists()
  body={'candidate_id':'0','prediction_sha256':j['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':[{'label':'Static title','xywh':[10,10,80,20]}]}
  plan=req(f'/api/jobs/{jid}/plan',body);assert plan['recipe']['input_profile']['frames']==n
  req(f'/api/jobs/{jid}/approve',{**body,'approve':False,'recipe_sha256':plan['recipe_sha256']},400)
  req(f'/api/jobs/{jid}/approve',{**body,'approve':True,'recipe_sha256':'0'*64},409)
  req(f'/api/jobs/{jid}/approve',{**body,'approve':True,'recipe_sha256':plan['recipe_sha256']},202)
  j=poll(jid);assert j['status']=='complete',j
  assert 'frame_review_error' not in j,j.get('frame_review_error')
  assert len(j['frame_review']['rows'])==4
  for row in j['frame_review']['rows']:
   assert 0<=row['frame']<n
   for asset in row['images'].values():
    png=req(asset['url'],raw=True)
    assert png.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(png).hexdigest()==asset['sha256']
  data=req(f'/api/jobs/{jid}/download/edited.mp4',raw=True);download=OUT/f'{w}-{n}-download.mp4';download.write_bytes(data)
  report=req(f'/api/jobs/{jid}/download/report.json');decision=json.loads((folder/'result.json').read_text());assert decision['acceptance']['status']=='accepted_experiment'
  a=decode(source,w,h,n);b=decode(download,w,h,n);c=decode(folder/'control.mp4',w,h,n);assert np.array_equal(a,c)
  pred=json.loads((folder/'prediction.json').read_text())['components'][0]
  import engine
  engine.W,engine.H=w,h
  from engine import unpack_mask
  from native_yuv import support_masks
  mask=unpack_mask(pred['mask_rle'],[h,w]);ym,cm=support_masks(mask);support=np.concatenate([ym.ravel(),cm.ravel(),cm.ravel()]).astype(bool)
  mapping=np.array(decision['recipe']['mapping']);assert len(mapping)==n
  assert np.array_equal(a[:,~support],b[:,~support]);assert np.array_equal(a[mapping][:,support],b[:,support]);assert not np.array_equal(a,b)
  lo,hi=plan['recipe']['frame_bounds_inclusive'];assert np.array_equal(a[:lo],b[:lo]) and np.array_equal(a[hi+1:],b[hi+1:])
  audio_record=None
  if audio:
   original=audio_data(source);assert audio_data(download)==original==audio_data(folder/'control.mp4');audio_record={'packets':len(original[0]['packets']),'pcm_sha256':original[1],'pcm_bytes':original[2]}
  resources=json.loads((folder/'export.resources.json').read_text())['resources']
  result={'width':w,'height':h,'frames':n,'seconds':n/30,'audio':audio_record,'job_id':jid,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(data).hexdigest(),'decoded_output_sha256':hashlib.sha256(b.tobytes()).hexdigest(),'all_12_boundary_png_responses_hash_exact':True,'independent_native_mapping_and_outside_exact':True,'protected_regions_exact':j['summary']['protected_content']['passed'],'resources':resources}
  results.append(result);(OUT/'result.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
finally:server.shutdown();thread.join();server.manager.close();server.server_close()
