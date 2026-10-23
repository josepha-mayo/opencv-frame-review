from pathlib import Path
import hashlib,json,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/app/studio');import run as studio
out=Path(sys.argv[1]);out.mkdir(exist_ok=False);source=Path('/new/cangjie.webm')
server=studio.make_studio_server(0,out/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token=''
def req(path,data=None,headers=None,raw=False,expected=200):
    headers=dict(headers or {})
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=50) as r:status=r.status;body=r.read()
    except urllib.error.HTTPError as e:status=e.code;body=e.read()
    assert status==expected,(status,body[:300]);return body if raw else json.loads(body)
record={'complete':False,'scope':'One preselected no-proposal excerpt; functional no-edit recovery, not a repair or recall measurement.','source':'cangjie','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'excerpt_start_seconds':139}
try:
    token=req('/api/profile')['csrf_token']
    job=req('/api/imports',source.read_bytes(),headers={'X-Filename':source.name,'X-Clip-Start':'139','X-Clip-Duration':'12'},expected=202)
    deadline=time.monotonic()+300
    while job['status'] in ('queued','analyzing') and time.monotonic()<deadline:
        time.sleep(.3);job=req('/api/jobs/'+job['id'])
    assert job['status']=='review' and not job['candidates'],job
    final=req('/api/jobs/'+job['id']+'/decline',{})
    assert final['status']=='declined'
    stem='/api/jobs/'+job['id'];receipt=req(stem+'/intake/receipt');decision=req(stem+'/intake/decision')
    assert hashlib.sha256(req(stem+'/intake/upload',raw=True)).hexdigest()==record['source_sha256']==receipt['uploaded_sha256']
    assert hashlib.sha256(req(stem+'/intake/prepared',raw=True)).hexdigest()==receipt['prepared_sha256']
    req(stem+'/download/edited.mp4',expected=409)
    assert decision['decision']=='declined' and decision['edited_export_accepted'] is False
    record.update(complete=True,preparation=receipt,decision=decision,original_and_prepared_downloads_exact=True,edited_download_withheld=True,manifest_sha256=hashlib.sha256((studio.ROOT/'BUILD_HASHES.json').read_bytes()).hexdigest())
    print('Unmodified no-proposal original: sources and decision recovered; edit withheld',flush=True)
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close();(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
