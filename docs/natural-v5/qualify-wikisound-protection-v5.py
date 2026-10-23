"""Real new-source instructional-control refusal, not a repair success."""
from pathlib import Path
import hashlib,json,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/app/studio');import run as studio
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
source=Path('/new/wikisound-recording.webm')
server=studio.make_studio_server(0,out/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token=''
def req(path,data=None,headers=None,raw=False,expected=200):
    headers=dict(headers or {})
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=55) as r:status=r.status;body=r.read()
    except urllib.error.HTTPError as error:status=error.code;body=error.read()
    assert status==expected,(status,body[:300]);return body if raw else json.loads(body)
record={'complete':False,'source':'wikisound-recording','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'start_seconds':159,'authored_defect':False,'scope':'Follow-up of the preselected cohort outcome. Moving Audacity control/readout text was reviewed as lesson content and protected. This is a refusal/source-recovery test, not a distraction removal, independent new source, or human impact trial.'}
try:
    token=req('/api/profile')['csrf_token']
    job=req('/api/imports',source.read_bytes(),headers={'X-Filename':source.name,'X-Clip-Start':'159','X-Clip-Duration':'12'},expected=202)
    deadline=time.monotonic()+300
    while job['status'] in ('queued','analyzing') and time.monotonic()<deadline:
        time.sleep(.3);job=req('/api/jobs/'+job['id'])
    assert job['status']=='review' and len(job['candidates'])==2
    jid=job['id'];stem='/api/jobs/'+jid
    areas=[{'label':'Audacity control and readout text','xywh':[0,300,640,60]}]
    errors=[]
    for candidate in job['candidates']:
        error=req(stem+'/plan',{'candidate_id':candidate['id'],'prediction_sha256':job['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':areas},expected=400)
        assert 'overlap' in error['error'].lower(),error
        errors.append(error)
    assert not (out/'jobs'/jid/'approval.json').exists()
    final=req(stem+'/decline',{});assert final['status']=='declined'
    receipt=req(stem+'/intake/receipt');decision=req(stem+'/intake/decision')
    assert hashlib.sha256(req(stem+'/intake/upload',raw=True)).hexdigest()==record['source_sha256']==receipt['uploaded_sha256']
    assert hashlib.sha256(req(stem+'/intake/prepared',raw=True)).hexdigest()==receipt['prepared_sha256']
    req(stem+'/download/edited.mp4',expected=409)
    assert not decision['edited_export_accepted']
    record.update(complete=True,candidates=job['candidates'],protected_regions=areas,plan_refusals=errors,decision=decision,original_and_prepared_http_hashes_exact=True,edited_download_withheld=True,runtime_manifest_sha256=hashlib.sha256((studio.ROOT/'BUILD_HASHES.json').read_bytes()).hexdigest())
    print('BOTH REAL AUDACITY CONTROL CANDIDATES REFUSED; EXACT SOURCES RECOVERED',flush=True)
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close();(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
