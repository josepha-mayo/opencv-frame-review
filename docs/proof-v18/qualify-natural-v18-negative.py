from pathlib import Path
import datetime,hashlib,http.cookiejar,json,time,urllib.request,urllib.error
W=Path(__file__).resolve().parent;B='https://le-d72c965de52749b08fd72a2513bccce1.ecs.us-east-1.on.aws';receipt=W/'natural-v18-negative-live.json';assert not receipt.exists(),'Inspect existing receipt before replay'
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));token=''
record={'complete':False,'scope':'Previously screened symbol drawing lesson at181s. Agent visual inspection identifies all four rapid-change candidates as lesson shape/status changes to keep; this tests protected-area refusal and source recovery, not a useful repair or detector accuracy.','authored_defect':False,'cases':[]}
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
 token=req('/api/profile')['csrf_token'];source=W/'natural-v18-originals/inkscape-symbol.webm';data=source.read_bytes();record['original_sha256']=hashlib.sha256(data).hexdigest();save()
 j=req('/api/imports',data,{'X-Filename':source.name,'X-Clip-Start':'181','X-Clip-Duration':'12'},202);jid=j['id'];record['job_id']=jid;save()
 deadline=time.monotonic()+300
 while j['status']in('queued','analyzing')and time.monotonic()<deadline:time.sleep(1);j=req('/api/jobs/'+jid)
 assert j['status']=='review' and len(j['candidates'])==4
 for candidate in j['candidates']:
  body={'candidate_id':candidate['id'],'prediction_sha256':j['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':[{'label':'Drawing and interface explanation','xywh':[0,0,640,360]}]}
  refusal=req('/api/jobs/'+jid+'/plan',body,expected=400);assert 'overlap'in refusal['error'].lower(),refusal
  record['cases'].append({'candidate':candidate,'plan_status':400,'response':refusal});save()
 current=req('/api/jobs/'+jid);assert current['status']=='review' and not current['workflow']['human_control']['source_bound_generation_approval']
 final=req('/api/jobs/'+jid+'/decline',{});assert final['status']=='declined'
 prep=req('/api/jobs/'+jid+'/intake/receipt');assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/upload',raw=True)).hexdigest()==record['original_sha256']==prep['uploaded_sha256']
 assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/prepared',raw=True)).hexdigest()==prep['prepared_sha256']
 req('/api/jobs/'+jid+'/download/edited.mp4',expected=409)
 record.update(complete=True,original_and_prepared_recovered_exact=True,edited_export_withheld=True,approval_never_granted=True,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save();print('All four meaningful-motion candidates refused; sources recovered exactly.')
except BaseException as e:record['error']=repr(e);save();raise
