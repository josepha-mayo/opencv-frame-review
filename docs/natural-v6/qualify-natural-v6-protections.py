"""Observed teaching content must survive even when a detector proposes a hold."""
from pathlib import Path
import hashlib,json,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/app/studio');import run as studio
out=Path(sys.argv[1]);out.mkdir(exist_ok=False);records=[]
cases=[('toybox-implementation',246,[{'label':'Configuration commands and selection','xywh':[10,45,480,285]}]),('libreoffice-writer',450,[{'label':'Document title and first letter','xywh':[96,120,315,35]}]),('libreoffice-import',36,[{'label':'Schedule dataset and first characters','xywh':[100,124,190,70]}])]
if len(sys.argv)>2:cases=[c for c in cases if c[0]==sys.argv[2]]
for name,start,areas in cases:
    folder=out/(name+'-'+str(start));folder.mkdir();source=Path('/new')/(name+'.webm');record={'complete':False,'source':name,'start':start,'authored_defect':False,'scope':'Follow-up of preselected v5 screen. Actual teaching content protected. Refusal, not a repaired distraction.'}
    server=studio.make_studio_server(0,folder/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1]);token=''
    def req(path,data=None,headers=None,raw=False,expected=200):
        headers=dict(headers or {})
        if data is not None:headers['X-App-Token']=token
        if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
        try:
            with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=55) as r:status=r.status;body=r.read()
        except urllib.error.HTTPError as error:status=error.code;body=error.read()
        assert status==expected,(status,body[:300]);return body if raw else json.loads(body)
    try:
        token=req('/api/profile')['csrf_token'];job=req('/api/imports',source.read_bytes(),headers={'X-Filename':source.name,'X-Clip-Start':str(start),'X-Clip-Duration':'12'},expected=202)
        deadline=time.monotonic()+300
        while job['status'] in ('queued','analyzing') and time.monotonic()<deadline:time.sleep(.3);job=req('/api/jobs/'+job['id'])
        assert job['status']=='review';candidates=[c for c in job['candidates'] if c['action']=='steady-detail-v1'];assert len(candidates)==1
        jid=job['id'];stem='/api/jobs/'+jid;errors=[]
        for c in candidates:
            error=req(stem+'/plan',{'candidate_id':c['id'],'prediction_sha256':job['prediction_sha256'],'export_mode':c['action'],'protected_regions':areas},expected=400);assert 'overlap' in error['error'].lower(),error;errors.append(error)
        assert not (folder/'jobs'/jid/'approval.json').exists()
        final=req(stem+'/decline',{});assert final['status']=='declined'
        receipt=req(stem+'/intake/receipt');decision=req(stem+'/intake/decision')
        sha=hashlib.sha256(source.read_bytes()).hexdigest();assert hashlib.sha256(req(stem+'/intake/upload',raw=True)).hexdigest()==sha==receipt['uploaded_sha256']
        assert hashlib.sha256(req(stem+'/intake/prepared',raw=True)).hexdigest()==receipt['prepared_sha256'];req(stem+'/download/edited.mp4',expected=409)
        assert not decision['edited_export_accepted']
        record.update(complete=True,source_sha256=sha,candidates=candidates,protected_regions=areas,plan_refusals=errors,decision=decision,original_and_prepared_http_hashes_exact=True,edited_download_withheld=True,runtime_manifest_sha256=hashlib.sha256((studio.ROOT/'BUILD_HASHES.json').read_bytes()).hexdigest())
        print(name,start,'instructional candidate refused, exact sources recovered',flush=True)
    finally:
        server.shutdown();thread.join();server.manager.close();server.server_close();(folder/'results.json').write_text(json.dumps(record,indent=2)+'\n');records.append(record);(out/'results.json').write_text(json.dumps({'complete':all(r['complete'] for r in records) and len(records)==len(cases),'cases':records},indent=2)+'\n')
