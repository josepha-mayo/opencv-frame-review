"""Targeted negative cases from original footage, using the actual HTTP workflow."""
from pathlib import Path
import hashlib,json,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/app/studio');import run as studio
OUT=Path(sys.argv[1]);SOURCES=Path(sys.argv[2]);OUT.mkdir(exist_ok=False)
records=[];studio.check_source();studio.check_runtime()
server=studio.make_studio_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token=''
def req(path,body=None,headers=None,raw=False):
    h=dict(headers or {})
    if body is not None:h['X-App-Token']=token
    if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=h),timeout=30) as response:
            payload=response.read()
            return response.status,payload if raw else json.loads(payload)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
def poll(jid):
    until=time.monotonic()+300
    while time.monotonic()<until:
        status,job=req('/api/jobs/'+jid);assert status==200
        if job['status'] not in ('queued','analyzing','exporting'):return job
        time.sleep(.3)
    raise TimeoutError(jid)
def save(): (OUT/'results.json').write_text(json.dumps({'runtime_manifest_sha256':hashlib.sha256(Path('/app/studio/BUILD_HASHES.json').read_bytes()).hexdigest(),'records':records},indent=2)+'\n')
try:
    token=req('/api/profile')[1]['csrf_token']
    for filename,start in [('blender.webm',68),('lecture-hall-light-1080p.webm',4),('lecture-hall-light-1080p.webm',16)]:
        data=(SOURCES/filename).read_bytes()
        status,initial=req('/api/imports',data,{'X-Filename':filename,'X-Clip-Start':str(start),'X-Clip-Duration':'12'});assert status==202
        job=poll(initial['id']);assert job['status']=='review',job
        candidate=max(job['candidates'],key=lambda c:c['pixels'])
        jid=job['id'];folder=OUT/'jobs'/jid
        record={'source':filename,'source_sha256':hashlib.sha256(data).hexdigest(),'start_seconds':start,'job_id':jid,'candidate_count':len(job['candidates']),'selector':'Largest detected support by pixel count, fixed before export outcome','candidate':candidate}
        records.append(record);save()
        body={'candidate_id':candidate['id'],'prediction_sha256':job['prediction_sha256'],'export_mode':'periodic-local-retime-v2',
              'protected_regions':[{'label':'Blender settings are teaching content','xywh':[560,0,80,360]}] if filename=='blender.webm' else [{'label':'Unselected dark column','xywh':[320,80,40,240]}]}
        status,plan=req('/api/jobs/'+jid+'/plan',body)
        record['plan_http_status']=status
        if status!=200:
            record['plan_refusal']=plan
            assert filename=='blender.webm' and status==400,plan
            record['no_approval_record']=not (folder/'approval.json').exists()
            req('/api/jobs/'+jid+'/decline',{});record['outcome']='teaching-overlap-refused'
        else:
            assert req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':plan['recipe_sha256']})[0]==202
            final=poll(jid);record['outcome']=final['status'];record['error']=final.get('error')
            record['artifacts']=final.get('artifacts',{})
            record['edited_file_exists']=(folder/'edited.mp4').exists()
            if (folder/'retime-rejection.json').exists():record['recurrence_rejection']=json.loads((folder/'retime-rejection.json').read_text())
            if final['status']=='failed':
                assert not record['edited_file_exists']
                assert set(record['artifacts'])=={'Prepared lesson clip','Uploaded original','Preparation receipt','Lesson decision record'}
                status,original=req('/api/jobs/'+jid+'/intake/upload',raw=True);assert status==200 and hashlib.sha256(original).hexdigest()==hashlib.sha256(data).hexdigest()
                status,prepared=req('/api/jobs/'+jid+'/intake/prepared',raw=True);assert status==200 and hashlib.sha256(prepared).hexdigest()==job['preparation']['prepared_sha256']
                status,decision=req('/api/jobs/'+jid+'/intake/decision');assert status==200 and decision['decision']=='failed' and not decision['edited_export_accepted'] and decision['failure_reason']==final['error']
                assert req('/api/jobs/'+jid+'/download/edited.mp4')[0]==409
                record['retained_sources_verified']=True
                record['failure_decision_verified']=True
            if final['status']=='complete':record['independent_output_verification']='pending; do not count as qualified natural repair'
        save();print(filename,start,record['outcome'],record.get('error'),flush=True)
finally:server.shutdown();thread.join();server.manager.close();server.server_close();save()
