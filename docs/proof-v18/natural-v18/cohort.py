"""Preselected real originals through actual HTTP preparation and source recovery.

Review candidates are recorded, never automatically treated as distractions.
Creator protection/export qualification is a separate, explicit later experiment.
"""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys,threading,time,urllib.request,urllib.error,shutil
sys.path.insert(0,'/app/studio');import run as studio
import cv2,numpy as np
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
sources=json.loads(Path('/audit/natural-v18-sources.json').read_text());assert len(sources)==2,'All selected source downloads must finish before this baseline screen'
plan=Path('/audit/natural-v18-selection-plan.json')
record={'complete':False,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'selection_plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'runtime_manifest_sha256':hashlib.sha256((studio.ROOT/'BUILD_HASHES.json').read_bytes()).hexdigest(),'scope':'Fourteen preselected windows from two drawing instructional recordings, selected after the first cohort. Exploratory follow-up. Real original HTTP intake, analysis, exact source recovery and withheld edits; proposal presence does not establish useful repair.','cases':[]}
if (out/'results.json').exists():
    previous=json.loads((out/'results.json').read_text())
    assert previous['runtime_manifest_sha256']==record['runtime_manifest_sha256'] and previous['selection_plan_sha256']==record['selection_plan_sha256']
    assert not previous['complete'],'Cohort already complete; refusing to repeat outcomes'
    record=previous
completed={(row['source'],row['start_seconds']) for row in record['cases']}
server=None;thread=None;base='';token='';jobs_root=None
def close_batch():
    global server,thread
    if server is not None:
        server.shutdown();thread.join();server.manager.close();server.server_close();server=None;thread=None
def new_batch():
    global server,thread,base,token,jobs_root
    close_batch()
    jobs_root=out/('jobs-batch-'+str(len(list(out.glob('jobs*')))))
    server=studio.make_studio_server(0,jobs_root);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_address[1]);token=req('/api/profile')['csrf_token']
def req(path,data=None,headers=None,raw=False,expected=200):
    headers=dict(headers or {})
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=55) as r:status=r.status;body=r.read()
    except urllib.error.HTTPError as error:status=error.code;body=error.read()
    assert status==expected,(status,body[:300])
    return body if raw else json.loads(body)
try:
    for source in sources:
        path=Path('/new')/source['filename'];data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==source['sha256']
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(path)]))
        duration=float(probe['format']['duration']);starts=[max(0,int(min(duration-12,600)*q)) for q in (.10,.25,.35,.50,.65,.75,.90)]
        for start in starts:
            if (source['id'],start) in completed:continue
            # The app intentionally caps a data directory at eight jobs.
            # Retain earlier batches on disk; never loosen that production cap.
            if server is None or len(server.manager.jobs)>=6:new_batch()
            started=time.monotonic()
            job=req('/api/imports',data,headers={'X-Filename':path.name,'X-Clip-Start':str(start),'X-Clip-Duration':'12'},expected=202)
            deadline=time.monotonic()+300
            while job['status'] in ('queued','analyzing') and time.monotonic()<deadline:
                time.sleep(.3);job=req('/api/jobs/'+job['id'])
            stem='/api/jobs/'+job['id']
            row={'source':source['id'],'original_sha256':source['sha256'],'start_seconds':start,'duration_seconds':12,'job_id':job['id'],'job_directory_relative':str(jobs_root.relative_to(out)/job['id']),'status':job['status'],'analysis_seconds':time.monotonic()-started,'candidates':job.get('candidates',[]),'error':job.get('error'),'authored_defect':False}
            if job['status']=='review':
                row['steady_analysis']=json.loads((jobs_root/job['id']/'steady-analysis.json').read_text())
                folder=jobs_root/job['id'];review=out/'review'/(source['id']+'-'+str(start));review.mkdir(parents=True,exist_ok=True)
                video=cv2.VideoCapture(str(folder/'input.mp4'));tiles=[]
                for frame_number in (0,120,240,359):
                    video.set(cv2.CAP_PROP_POS_FRAMES,frame_number);ok,frame=video.read();assert ok
                    for candidate in job.get('candidates',[]):
                        x,y,w,h=candidate['bbox'];cv2.rectangle(frame,(x,y),(x+w,y+h),(0,0,255),1)
                    cv2.putText(frame,str(frame_number),(8,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),1);tiles.append(frame)
                video.release();cv2.imwrite(str(review/'contact.png'),np.vstack([np.hstack(tiles[:2]),np.hstack(tiles[2:])]))
                for png in folder.rglob('*.png'):
                    if 'preview' in png.name or 'reference' in png.name or 'alternate' in png.name:shutil.copyfile(png,review/png.name)
                (review/'job.json').write_text(json.dumps(job,indent=2)+'\n')
                final=req(stem+'/decline',{});assert final['status']=='declined'
                receipt=req(stem+'/intake/receipt');decision=req(stem+'/intake/decision')
                assert hashlib.sha256(req(stem+'/intake/upload',raw=True)).hexdigest()==source['sha256']==receipt['uploaded_sha256']
                assert hashlib.sha256(req(stem+'/intake/prepared',raw=True)).hexdigest()==receipt['prepared_sha256']
                req(stem+'/download/edited.mp4',expected=409)
                assert decision['decision']=='declined' and not decision['edited_export_accepted']
                row.update(original_and_prepared_http_hashes_exact=True,edited_download_withheld=True,prepared_sha256=receipt['prepared_sha256'],preparation=receipt)
            record['cases'].append(row);(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
            print(source['id'],start,job['status'],'proposals',len(row['candidates']),'recovered',row.get('original_and_prepared_http_hashes_exact',False),flush=True)
    record.update(complete=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
finally:
    close_batch()
