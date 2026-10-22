"""Actual refusal on new-length and presentation adversaries; never relaxed gates."""
import json,pathlib,sys,threading,time,urllib.request,urllib.error,subprocess,struct
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from server import make_server
OUT=pathlib.Path(sys.argv[1]);OUT.mkdir(exist_ok=False)
source=pathlib.Path(sys.argv[2]);fixtures={}
for n in (29,31,363):
 p=OUT/f'frames-{n}.mp4';subprocess.run(['/usr/bin/ffmpeg','-v','error','-n','-stream_loop','-1','-i',str(source),'-map','0:v:0','-an','-c','copy','-frames:v',str(n),str(p)],check=True);fixtures[f'frames-{n}']=p
raw=source.read_bytes()
# Alter the 12s canonical audio edit-list rate and audio track volume independently.
old=struct.pack('>IIIiHH',0,1,12000,1024,1,0);assert raw.count(old)==1
p=OUT/'rate-2.mp4';p.write_bytes(raw.replace(old,struct.pack('>IIIiHH',0,1,12000,1024,2,0)));fixtures['rate-2']=p
pos=raw.find(b'tkhd',raw.find(b'tkhd')+4);assert pos>0
b=bytearray(raw);assert b[pos+4+36:pos+4+38]==b'\x01\x00';b[pos+4+36:pos+4+38]=b'\x00\x80'
p=OUT/'volume-half.mp4';p.write_bytes(b);fixtures['volume-half']=p
server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_address[1]}'
def req(path,data=None,expect=200):
 h={'X-App-Token':token} if data is not None else {}
 try:
  with urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers=h),timeout=15) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 assert status==expect,(status,body)
 return json.loads(body)
results={}
try:
 token=req('/api/profile')['csrf_token']
 for name,p in fixtures.items():
  jid=req('/api/jobs',p.read_bytes(),202)['id'];until=time.monotonic()+130
  while time.monotonic()<until:
   j=req('/api/jobs/'+jid)
   if j['status'] not in ('queued','analyzing','exporting'):break
   time.sleep(.2)
  assert j['status']=='failed' and not j['artifacts'],j
  assert not (OUT/'jobs'/jid/'edited.mp4').exists()
  req('/api/jobs/'+jid+'/download/edited.mp4',expect=409);results[name]=j
 (OUT/'result.json').write_text(json.dumps(results,indent=2));print('All new duration/header adversaries refused with no accepted output')
finally:server.shutdown();thread.join();server.manager.close();server.server_close()
