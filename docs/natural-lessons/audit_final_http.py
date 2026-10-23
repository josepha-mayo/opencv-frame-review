"""Exploratory originals-only HTTP audit; never automatically approves a candidate.

Run inside the qualified image with plan, original media and a fresh output folder.
This evidence harness does not modify the runtime or its frozen detector.
"""
from pathlib import Path
import hashlib, json, subprocess, sys, threading, time, urllib.error, urllib.request
import numpy as np
sys.path.insert(0,'/app/studio')
import run as studio
PLAN=Path(sys.argv[1]);SOURCES=Path(sys.argv[2]);OUT=Path(sys.argv[3])
plan=json.loads(PLAN.read_text());OUT.mkdir(exist_ok=False)
records=[]
receipt={'schema':'natural-lesson-observations-v1','plan_sha256':hashlib.sha256(PLAN.read_bytes()).hexdigest(),
         'runtime_manifest_sha256':hashlib.sha256(Path('/app/studio/BUILD_HASHES.json').read_bytes()).hexdigest(),
         'source_check':studio.check_source(),'complete':False,'records':records,
         'scope':'Original, unaugmented excerpts. Candidate detection is not semantic distraction identification. No candidate is approved in this audit.'}
studio.check_runtime()
def save(): (OUT/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
def sha(data): return hashlib.sha256(data).hexdigest()
def command(args): return subprocess.check_output(args,stderr=subprocess.PIPE)
def pcm(path,start=0):
    return np.frombuffer(command(['ffmpeg','-v','error','-threads','1','-ss',str(start),'-i',str(path),'-t','12','-map','0:a:0','-ac','1','-ar','8000','-f','f32le','pipe:1']),np.float32).astype(np.float64)
def correlation(a,b):
    best=(-1,None)
    for lag in range(-80,81):
        x,y=(a[-lag:],b[:len(b)+lag]) if lag<0 else (a[:len(a)-lag],b[lag:])
        n=min(len(x),len(y));x=x[:n]-x[:n].mean();y=y[:n]-y[:n].mean()
        c=float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-15))
        if c>best[0]:best=c,lag/8000
    return {'max_normalized_correlation_within_10ms':best[0],'lag_seconds':best[1], 'meaning':'Lossy preparation check, not original audio identity or a listening test.'}
save()
for source in plan['sources']:
    original=SOURCES/source['filename'];data=original.read_bytes()
    metadata=json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(original)]))
    (OUT/(source['id']+'-probe.json')).write_text(json.dumps(metadata,indent=2))
    server=studio.make_studio_server(0,OUT/(source['id']+'-jobs'))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_address[1]);token=''
    def req(path,body=None,headers=None,raw=False):
        h=dict(headers or {})
        if body is not None:h['X-App-Token']=token
        if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
        with urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=h),timeout=30) as response:
            payload=response.read()
        return payload if raw else json.loads(payload)
    def poll(jid):
        end=time.monotonic()+180
        while time.monotonic()<end:
            j=req('/api/jobs/'+jid)
            if j['status'] not in ('queued','analyzing','exporting'):return j
            time.sleep(.25)
        raise TimeoutError(jid)
    try:
        token=req('/api/profile')['csrf_token']
        for start in plan['excerpt_policy']['starts_seconds']:
            label=source['id']+'-'+str(start);clip=OUT/label;clip.mkdir()
            record={'source_id':source['id'],'source_sha256':sha(data),'source_bytes':len(data),
                    'start_seconds':start,'duration_seconds':12,'authored_defect':False,'outcome':'pending'}
            records.append(record);save()
            try:
                begin=time.monotonic()
                job=poll(req('/api/imports',data,headers={'X-Filename':source['filename'],'X-Clip-Start':str(start),'X-Clip-Duration':'12'})['id'])
                record.update(analysis_seconds=round(time.monotonic()-begin,3),outcome=job['status'],error=job.get('error'),candidates=job.get('candidates',[]))
                (clip/'analysis-response.json').write_text(json.dumps(job,indent=2))
                assert job['status']=='review',job
                jid=job['id'];folder=server.manager.root/jid;prepared=folder/'input.mp4'
                record['preparation']=job['preparation']
                record['no_approval_after_preparation']=not (folder/'approval.json').exists()
                assert record['no_approval_after_preparation']
                assert sha(req('/api/jobs/'+jid+'/intake/upload',raw=True))==sha(data)
                record['uploaded_original_download_exact']=True
                for candidate in job['candidates']:
                    image=req(candidate['overlay_url'],raw=True)
                    (clip/('candidate-'+str(candidate['id'])+'.png')).write_bytes(image)
                command(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(prepared),'-vf',
                         'select=eq(n\\,0)+eq(n\\,90)+eq(n\\,180)+eq(n\\,270),scale=320:180,tile=4x1',
                         '-frames:v','1','-threads','1',str(clip/'contact.png')])
                audio=job['preparation']['source'].get('audio_codec')
                if audio:record['audio_preparation']=correlation(pcm(original,start),pcm(prepared))
                # Retain/reject every candidate until a human context review is recorded.
                req('/api/jobs/'+jid+'/decline',{})
                final=poll(jid)
                record.update(outcome=final['status'],decision='declined without approval; semantic review is separate',
                              prepared_download_exact=sha(req('/api/jobs/'+jid+'/download/original.mp4',raw=True))==sha(prepared.read_bytes()),
                              no_edited_artifact=not (folder/'edited.mp4').exists())
                assert record['prepared_download_exact'] and record['no_edited_artifact']
                decision=req('/api/jobs/'+jid+'/intake/decision')
                assert decision['decision']=='declined' and not decision['edited_export_accepted']
                assert decision['uploaded_sha256']==sha(data) and decision['prepared_sha256']==sha(prepared.read_bytes())
                record['decision_record_verified']=True
                (clip/'decision.json').write_text(json.dumps(decision,indent=2))
                print(label,record['outcome'],'candidates',len(record['candidates']),flush=True)
            except Exception as error:
                record.update(outcome='audit-failed',audit_error=repr(error));print(label,'FAILED',repr(error),flush=True)
            save()
    finally:
        server.shutdown();thread.join();server.manager.close();server.server_close()
receipt['complete']=len(records)==len(plan['sources'])*len(plan['excerpt_policy']['starts_seconds'])
receipt['all_workflows_passed']=receipt['complete'] and all(r['outcome']=='declined' for r in records)
save()
print('NATURAL COHORT COMPLETE',receipt['all_workflows_passed'],flush=True)
