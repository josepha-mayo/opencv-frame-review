"""Actual encoded protected-pixel failure and sparse-input refusal over HTTP."""
import hashlib,json,pathlib,sys,threading,time,urllib.request,urllib.error
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP));from server import make_server
OUT=APP.parent/'api-rejections-v1';OUT.mkdir(exist_ok=False);server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_address[1]}'
checks=[]
def check(name,value):
 checks.append({'check':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def req(path,data=None,expect=200):
 h={}
 if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
 if data is not None:h['X-App-Token']=token
 try:
  with urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers=h),timeout=15) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as r:status=r.code;body=r.read()
 check(path+' returns '+str(expect),status==expect);return json.loads(body)
def poll(jid):
 end=time.monotonic()+90
 while time.monotonic()<end:
  r=req('/api/jobs/'+jid)
  if r['status'] not in ('queued','analyzing','exporting'):return r
  time.sleep(.2)
 raise TimeoutError(jid)
try:
 token=req('/api/profile')['csrf_token'];outcomes={}
 cases=[('protected-pixel',APP.parents[1]/'opencv-recovery/rerun/workshop/input.mp4',[{'label':'Adjacent edge pixel','xywh':[492,145,1,1]}]),('sparse-nonperiodic',APP.parent/'adversarial-input-v1/sparse-nonperiodic.mp4',[])]
 for label,path,regions in cases:
  j=req('/api/jobs',path.read_bytes(),202);jid=j['id'];j=poll(jid);check(label+' analyzed',j['status']=='review' and bool(j['candidates']))
  c=max(j['candidates'],key=lambda x:x.get('area',0))
  body={'candidate_id':c['id'],'prediction_sha256':j['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':regions}
  plan=req('/api/jobs/'+jid+'/plan',body);req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':plan['recipe_sha256']},202)
  j=poll(jid);check(label+' failed closed',j['status']=='failed' and not j['artifacts']);req('/api/jobs/'+jid+'/download/edited.mp4',expect=409)
  jobdir=OUT/'jobs'/jid;check('no accepted edited filename',not (jobdir/'edited.mp4').exists())
  if label=='protected-pixel':
   r=json.loads((jobdir/'result.json').read_text());check('pixel error really measured',r['protected']['regions'][0]['measurements']['max_rgb_code_error']>0);check('failed preservation gate',not r['acceptance']['checks']['protected_regions_exact_vs_source']);check('rejected diagnostic retained',(jobdir/'rejected-candidate.mp4').exists())
  else:
   r=json.loads((jobdir/'retime-rejection.json').read_text());check('recurrence refusal explicit',r['status']=='unsupported_recurrence')
  outcomes[label]={'job_id':jid,'error':j['error'],'diagnostic':r}
 (OUT/'result.json').write_text(json.dumps({'checks':checks,'outcomes':outcomes,'browser_qa':'not performed'},indent=2)+'\n');print(json.dumps({'all_passed':all(c['passed'] for c in checks),'results':str(OUT/'result.json')}))
finally:
 server.shutdown();thread.join();server.manager.close();server.server_close();(OUT/'checks-partial.json').write_text(json.dumps(checks,indent=2)+'\n')
