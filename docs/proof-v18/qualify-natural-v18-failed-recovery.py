from pathlib import Path
import datetime,hashlib,http.cookiejar,json,time,urllib.request,urllib.error
W=Path(__file__).resolve().parent;B='https://le-d72c965de52749b08fd72a2513bccce1.ecs.us-east-1.on.aws';receipt=W/'natural-v18-failed-recovery-live.json';assert not receipt.exists(),'Inspect existing receipt before replay'
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));token=''
record={'complete':False,'scope':'Both retained jEdit analysis refusals from the fixed-window screen: preserve the sixteen-region guard, verify visible failed status and original/prepared recovery, and withhold edited download. Not useful repairs.','cases':[]}
def save():receipt.write_text(json.dumps(record,indent=2)+'\n')
def req(path,data=None,headers=None,expected=200,raw=False):
 hs={'Origin':B,**(headers or{})}
 if data is not None:hs['X-App-Token']=token
 if isinstance(data,dict):data=json.dumps(data).encode();hs['Content-Type']='application/json'
 try:
  with opener.open(urllib.request.Request(B+path,data=data,headers=hs),timeout=90)as r:code=r.status;body=r.read()
 except urllib.error.HTTPError as e:code=e.code;body=e.read()
 assert code==expected,(code,body[:300]);return body if raw else json.loads(body)
try:
 record['deployment']=req('/api/deployment');assert record['deployment']['source_manifest_sha256']==json.loads((W/'proof-v18-cloud-build-plan.json').read_text())['source_manifest_sha256']
 token=req('/api/profile')['csrf_token'];source=W/'natural-v18c-originals/jedit-tamil.webm';data=source.read_bytes();original=hashlib.sha256(data).hexdigest()
 for start in (95,176):
  row={'start_seconds':start};record['cases'].append(row);save()
  j=req('/api/imports',data,{'X-Filename':source.name,'X-Clip-Start':str(start),'X-Clip-Duration':'12'},202);jid=j['id'];row['job_id']=jid;save();deadline=time.monotonic()+300
  while j['status']in('queued','analyzing')and time.monotonic()<deadline:time.sleep(1);j=req('/api/jobs/'+jid)
  assert j['status']=='failed' and j['error']=='More than 16 regions; this review interface cannot admit the clip.',j
  prep=req('/api/jobs/'+jid+'/intake/receipt');assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/upload',raw=True)).hexdigest()==original==prep['uploaded_sha256']
  assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/prepared',raw=True)).hexdigest()==prep['prepared_sha256']
  req('/api/jobs/'+jid+'/download/edited.mp4',expected=409)
  assert not j['workflow']['human_control']['source_bound_generation_approval']
  row.update(complete=True,status=j['status'],error=j['error'],workflow=j['workflow'],artifacts=j['artifacts'],original_and_prepared_recovered_exact=True,edited_export_withheld=True,approval_never_granted=True);save();print('Retained region-cap refusal and exact recovery:',start,flush=True)
 record.update(complete=True,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
except BaseException as e:record['error']=repr(e);save();raise
