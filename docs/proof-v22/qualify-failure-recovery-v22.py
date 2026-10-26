"""Retain a real twelve-second region-cap refusal, then explicitly test four seconds."""
from pathlib import Path
import hashlib,json,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/app/studio');import run as studio
O=Path(sys.argv[1]);O.mkdir(exist_ok=False);source=Path(sys.argv[2]);raw=source.read_bytes();original=hashlib.sha256(raw).hexdigest()
server=studio.make_studio_server(0,O/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1]);token=''
record={'complete':False,'scope':'Same untouched jEdit original at95s; two explicit native HTTP uploads, duration12 and4 seconds. Not a UI click, human benefit or automatically repeated action. Retain every outcome.','original_sha256':original,'cases':[]}
def save():(O/'results.json').write_text(json.dumps(record,indent=2)+'\n')
def req(path,data=None,headers=None,expected=200,raw=False):
 hs=dict(headers or{})
 if data is not None:hs['X-App-Token']=token
 if isinstance(data,dict):data=json.dumps(data).encode();hs['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=hs),timeout=60)as r:code=r.status;body=r.read()
 except urllib.error.HTTPError as e:code=e.code;body=e.read()
 assert code==expected,(code,body[:300]);return body if raw else json.loads(body)
try:
 token=req('/api/profile')['csrf_token']
 for length in(12,4):
  j=req('/api/imports',raw,{'X-Filename':source.name,'X-Clip-Start':'95','X-Clip-Duration':str(length)},202);deadline=time.monotonic()+300
  while j['status']in('queued','analyzing')and time.monotonic()<deadline:time.sleep(.3);j=req('/api/jobs/'+j['id'])
  if length==12:assert j['status']=='failed'and j['error']=='More than 16 regions; this review interface cannot admit the clip.'
  else:assert j['status']in('review','failed'),j
  assert not j['workflow']['human_control']['source_bound_generation_approval']
  receipt=req('/api/jobs/'+j['id']+'/intake/receipt');assert receipt['start_seconds']==95 and receipt['duration_seconds']==length
  assert hashlib.sha256(req('/api/jobs/'+j['id']+'/intake/upload',raw=True)).hexdigest()==original==receipt['uploaded_sha256']
  assert hashlib.sha256(req('/api/jobs/'+j['id']+'/intake/prepared',raw=True)).hexdigest()==receipt['prepared_sha256']
  req('/api/jobs/'+j['id']+'/download/edited.mp4',expected=409)
  record['cases'].append({'duration_seconds':length,'job':j,'original_and_prepared_recovered_exact':True,'edited_output_withheld':True,'approval_never_granted':True});save();print(length,j['status'],len(j['candidates']),j.get('error'),flush=True)
 record['complete']=True;save()
finally:server.shutdown();thread.join();server.manager.close();server.server_close()
