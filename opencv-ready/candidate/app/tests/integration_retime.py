"""Actual loopback HTTP + bounded worker exercise. No browser claim."""
import hashlib,json,pathlib,sys,threading,time,urllib.request,urllib.error
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from server import make_server
BASE=APP.parents[1];FIXTURES=BASE/'opencv-recovery/rerun'
OUT=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else APP.parent/'api-integration-v1';OUT.mkdir(exist_ok=False)
server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_address[1]}'
checks=[]

def check(name,value):
    checks.append({'check':name,'passed':bool(value)})
    if not value:raise AssertionError(name)

def req(path,data=None,headers=None,expect=200,raw=False):
    h=dict(headers or {})
    if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
    if data is not None:h.setdefault('X-App-Token',token)
    request=urllib.request.Request(url+path,data=data,headers=h)
    try:
        with urllib.request.urlopen(request,timeout=15) as response:status=response.status;body=response.read()
    except urllib.error.HTTPError as error:status=error.code;body=error.read()
    check(f'{path} returns {expect}',status==expect)
    return body if raw else json.loads(body)

def poll(jid):
    until=time.monotonic()+90
    while time.monotonic()<until:
        result=req('/api/jobs/'+jid)
        if result['status'] not in ('queued','analyzing','exporting'):return result
        time.sleep(.2)
    raise TimeoutError(jid)

try:
    token=req('/api/profile')['csrf_token']
    req('/api/jobs',b'x',{'X-App-Token':'wrong'},expect=403)
    req('/api/profile',headers={'Host':'attacker.example'},expect=400)
    req('/api/jobs',b'x',{'Origin':'https://attacker.example'},expect=400)
    outcomes={}
    for fixture in ('p2','workshop'):
        source=FIXTURES/fixture;job=req('/api/jobs',(source/'input.mp4').read_bytes(),{'X-Filename':fixture+'.mp4'},expect=202);jid=job['id'];job=poll(jid)
        check(fixture+' analyzed',job['status']=='review' and bool(job['candidates']))
        recipe=json.loads((source/'recipe.json').read_text())
        body={'candidate_id':'0','prediction_sha256':job['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':recipe['protected_regions']}
        plan=req('/api/jobs/'+jid+'/plan',body)
        check('recipe binds v2 pointwise gate',plan['recipe']['edit']['cycle_policy']['max_repeat_sample_error']==32)
        check('protected criteria exact',all(v==0 for v in plan['recipe']['protected_criteria'].values()))
        req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':'0'*64},expect=409)
        request={**body,'approve':True,'recipe_sha256':plan['recipe_sha256']}
        req('/api/jobs/'+jid+'/approve',request,expect=202)
        req('/api/jobs/'+jid+'/approve',request,expect=409)
        job=poll(jid);check(fixture+' accepted processing',job['status']=='complete')
        check('acceptance surfaced',job['summary']['acceptance']['status']=='accepted_experiment')
        edited=req('/api/jobs/'+jid+'/download/edited.mp4',raw=True)
        expected=hashlib.sha256((APP.parent/f'release-{fixture}/retimed-master.mp4').read_bytes()).hexdigest()
        check(fixture+' output agrees with isolated golden',hashlib.sha256(edited).hexdigest()==expected)
        check('four bound static rows',len(job['frame_review']['rows'])==4)
        report=req('/api/jobs/'+jid+'/download/report.json')
        check('source comparator accurately named','original source' in report['summary']['protected_content']['scope'])
        target=OUT/'jobs'/jid/'edited.mp4';target.write_bytes(edited+b'corrupt')
        req('/api/jobs/'+jid+'/download/edited.mp4',expect=400)
        target.write_bytes(edited)
        outcomes[fixture]={'job_id':jid,'summary':job['summary'],'edited_sha256':expected}
    # Unsupported input is a real failed job, not accepted with an empty artifact.
    bad=req('/api/jobs',b'not an mp4',expect=202);failed=poll(bad['id'])
    check('unsupported input rejected',failed['status']=='failed' and not failed['artifacts'])
    req('/api/jobs/'+bad['id']+'/download/edited.mp4',expect=409)
    # Inject an actual output policy failure at the worker boundary in a separate
    # controlled test by reusing the pure acceptance regression; never alter app
    # policy or the original golden fixtures here.
    result={'url_tested':url,'checks':checks,'outcomes':outcomes,'browser_qa':'not performed','scope':'real loopback HTTP and actual media workers on two owned fixtures'}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':len(checks),'all_passed':all(x['passed'] for x in checks),'results':str(OUT/'result.json')}))
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close()
    (OUT/'checks-partial.json').write_text(json.dumps(checks,indent=2)+'\n')
