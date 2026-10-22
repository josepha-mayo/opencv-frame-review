"""Owned synthetic fixture rejection via actual loopback workers."""
import json,pathlib,sys,threading,time,urllib.request,urllib.error,subprocess
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from server import make_server
OUT=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else APP.parent/'api-audio-rejections-v1';OUT.mkdir(exist_ok=False)
source=APP.parent/'fixtures/p2-audio.mp4'
fixtures={}
for name,args in {'stereo':['-map','0:v','-map','0:a','-c:v','copy','-c:a','aac','-ac','2'], 'extra-track':['-map','0:v','-map','0:a','-map','0:a','-c','copy'], 'offset':['-map','0:v','-map','0:a','-c','copy','-output_ts_offset','0.1']}.items():
 p=OUT/(name+'.mp4');subprocess.run(['/usr/bin/ffmpeg','-v','error','-n','-i',str(source)]+args+['-video_track_timescale','15360',str(p)],check=True);fixtures[name]=p
server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_address[1]}'
def req(path,data=None,expect=200):
 h={}
 if data is not None:h['X-App-Token']=token
 if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers=h),timeout=15) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 assert status==expect,(status,body)
 return json.loads(body)
def poll(jid):
 for _ in range(300):
  j=req('/api/jobs/'+jid)
  if j['status'] not in ('queued','analyzing','exporting'):return j
  time.sleep(.2)
 raise TimeoutError(jid)
results={}
try:
 token=req('/api/profile')['csrf_token']
 for name,p in fixtures.items():
  j=poll(req('/api/jobs',p.read_bytes(),202)['id']);assert j['status']=='failed' and not j['artifacts'],j
  req('/api/jobs/'+j['id']+'/download/edited.mp4',expect=409);results[name]=j
 j=poll(req('/api/jobs',source.read_bytes(),202)['id']);assert j['status']=='review',j
 for mode in ('legacy','native-yuv-whole-clip-v9'):
  results[mode]=req('/api/jobs/'+j['id']+'/plan',{'candidate_id':'0','prediction_sha256':j['prediction_sha256'],'export_mode':mode,'protected_regions':[]},400)
 (OUT/'result.json').write_text(json.dumps(results,indent=2));print('All actual audio rejection paths passed')
finally:server.shutdown();thread.join();server.manager.close();server.server_close()
