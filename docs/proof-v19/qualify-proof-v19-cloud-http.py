from pathlib import Path
import datetime,hashlib,http.cookiejar,io,json,time,urllib.request,urllib.error,zipfile
from verify_offline_page import verify
W=Path(__file__).resolve().parent;O=W.parent/'outputs/proof-v19';B='https://le-d72c965de52749b08fd72a2513bccce1.ecs.us-east-1.on.aws';H=lambda b:hashlib.sha256(b).hexdigest()
record={'complete':False,'scope':'Real HTTPS API original upload, reviewed plan, explicit approval, complete artifact download and native media/PNG byte comparison. API test; not a browser save-dialog completion claim.','cases':[]}
receipt=W/'proof-v19-cloud-http-verified.json';assert not receipt.exists(),'Inspect prior receipt before replay'
def save():receipt.write_text(json.dumps(record,indent=2)+'\n')
try:
 deployment=json.load(urllib.request.urlopen(B+'/api/deployment',timeout=20));assert deployment['source_manifest_sha256']=='65436e94f8a550315076bfec4fd0d452483e433c971fe068aa5fdc1eed5a9acf';record['deployment']=deployment
 for name in ('upload-assistant','joomla','gentoo'):
  c=json.loads((W/('marking-v9-gentoo-adjusted-case.json' if name=='gentoo' else 'offline-v11-'+name+'-case.json')).read_text());Q=json.loads((O/'native'/name/'results.json').read_text());assert Q['complete']
  jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));token=''
  def req(path,data=None,expected=200,raw=False,headers=None):
   hs={'Origin':B,**(headers or{})}
   if data is not None:hs['X-App-Token']=token
   if isinstance(data,dict):data=json.dumps(data).encode();hs['Content-Type']='application/json'
   try:
    with opener.open(urllib.request.Request(B+path,data=data,headers=hs),timeout=60)as r:code=r.status;body=r.read()
   except urllib.error.HTTPError as e:code=e.code;body=e.read()
   assert code==expected,(code,body[:300]);return body if raw else json.loads(body)
  def poll(jid):
   until=time.monotonic()+300
   while time.monotonic()<until:
    j=req('/api/jobs/'+jid)
    if j['status']not in ('queued','analyzing','exporting'):return j
    time.sleep(2)
   raise TimeoutError(jid)
  token=req('/api/profile')['csrf_token'];source=W/('natural-v10-originals/upload-assistant.ogv'if name=='upload-assistant'else 'natural-v5-shell-originals/gentoo-equery.webm' if name=='gentoo' else 'natural-v9c-originals/joomla-install.ogv')
  row={'case':name,'complete':False};record['cases'].append(row);save()
  j=req('/api/imports',source.read_bytes(),202,headers={'X-Filename':source.name,'X-Clip-Start':str(c['start']),'X-Clip-Duration':'12'});jid=j['id'];row['job_id']=jid;save();j=poll(jid);assert j['status']=='review',j
  assert j['workflow']['route']=='request_human_review' and not j['workflow']['human_control']['source_bound_generation_approval']
  cand=next(x for x in j['candidates']if x.get('bbox')==c['bbox']);body={'candidate_id':cand['id'],'prediction_sha256':j['prediction_sha256'],'export_mode':'steady-detail-v1','protected_regions':c['protected_regions']}
  req('/api/jobs/'+jid+'/plan',{**body,'protected_regions':[]},400);p=req('/api/jobs/'+jid+'/plan',body)
  req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':'0'*64},409);req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':p['recipe_sha256']},202)
  final=poll(jid);assert final['status']=='complete',final
  workflow=req('/api/jobs/'+jid+'/workflow.json');assert workflow==final['workflow'] and workflow['route']=='inspect_comparison' and workflow['human_control']['source_bound_generation_approval'];row['workflow']=workflow
  packed=req('/api/jobs/'+jid+'/rescue-pack.zip',raw=True);offline=verify(packed)
  with zipfile.ZipFile(io.BytesIO(packed))as z:
   assert z.testzip()is None;m=json.loads(z.read('manifest.json'));assert m['binding']['job_id']==jid and m['binding']['source_manifest_sha256']==deployment['source_manifest_sha256']
   for n,e in m['files'].items():
    data=z.read(n);assert H(data)==e['sha256']and len(data)==e['bytes']
    if n.endswith(('.mp4','.ogv','.png')):assert e==Q['rescue_pack']['file_hashes'][n],n
   assert json.loads(z.read('vision-workflow.json'))==workflow
   report=json.loads(z.read('report.json'));assert all(report['summary']['checks'].values())and report['summary']['checks']==Q['summary']['checks']
   assert report['summary']['stationary_detail']['activity']==Q['summary']['stationary_detail']['activity']
   target=O/(name+'-AWS-Rescue-Pack.zip');target.write_bytes(packed)
   for n in z.namelist():
    assert '/' not in n and '\\' not in n and n not in ('.','..')
    folder=O/(name+'-aws');folder.mkdir(exist_ok=True);(folder/n).write_bytes(z.read(n))
  unowned={}
  for suffix in ('','/workflow.json','/rescue-pack.zip','/intake/upload','/download/edited.mp4'):
   try:urllib.request.urlopen(B+'/api/jobs/'+jid+suffix,timeout=20);code=200
   except urllib.error.HTTPError as e:code=e.code
   unowned[suffix or '/']=code
  assert all(x==404 for x in unowned.values())
  row.update(complete=True,pack_path=str(target),bytes=len(packed),sha256=H(packed),members=len(m['files'])+1,all_manifest_hashes_exact=True,all_native_media_and_png_bytes_identical=True,all_encoded_checks_pass=True,offline_page=offline,unowned_statuses=unowned,source_sha256=H(source.read_bytes()),summary=report['summary']);save();print(name,'API and artifact qualification passed',len(m['files'])+1,'members',flush=True)
 record.update(complete=True,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),browser_download_completion_claimed=False);save()
except BaseException as e:
 record['error']=repr(e);save();raise
