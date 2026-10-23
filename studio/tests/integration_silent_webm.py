"""A silent VP8 input must prepare to the actual admitted chroma profile.

Wholly authored transport regression. This is not natural-repair evidence.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,threading,time,urllib.request
STUDIO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(STUDIO));import run as studio
out=Path(sys.argv[1]);out.mkdir(exist_ok=False);source=out/'authored-silent-center.webm'
subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i','testsrc2=size=320x180:rate=15:duration=2',
                '-an','-c:v','libvpx','-b:v','300k','-threads','1','-pix_fmt','yuv420p','-chroma_sample_location','center',str(source)],check=True)
def probe(path):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']
source_chroma=probe(source)[0].get('chroma_location','unspecified')
assert source_chroma in ('unspecified','center')
server=studio.make_studio_server(0,out/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token='';record={'complete':False,'scope':'Wholly authored silent VP8 transport/profile regression, not natural footage or impact.'}
def req(path,data=None,headers=None,raw=False):
    headers=dict(headers or {})
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=45) as r:body=r.read()
    return body if raw else json.loads(body)
try:
    token=req('/api/profile')['csrf_token']
    job=req('/api/imports',source.read_bytes(),headers={'X-Filename':source.name,'X-Clip-Start':'0','X-Clip-Duration':'2'})
    until=time.monotonic()+120
    while job['status'] in ('queued','analyzing') and time.monotonic()<until:time.sleep(.2);job=req('/api/jobs/'+job['id'])
    assert job['status']=='review',job
    folder=out/'jobs'/job['id'];streams=probe(folder/'input.mp4')
    assert len(streams)==1 and streams[0]['codec_type']=='video' and streams[0]['chroma_location']=='left'
    assert job['preparation']['source']['chroma_location']==source_chroma
    assert job['preparation']['prepared']['chroma_location']=='left'
    final=req('/api/jobs/'+job['id']+'/decline',{});assert final['status']=='declined'
    assert hashlib.sha256(req('/api/jobs/'+job['id']+'/intake/upload',raw=True)).hexdigest()==hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(req('/api/jobs/'+job['id']+'/intake/prepared',raw=True)).hexdigest()==job['preparation']['prepared_sha256']
    record.update(complete=True,input_chroma_location=source_chroma,prepared_h264_left=True,silent_track_absence_exact=True,source_downloads_exact=True,profile_accepted_by_actual_engine=True,preparation=job['preparation'])
    print('Silent VP8 -> H.264 left accepted by actual analysis; source recovery exact',flush=True)
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close();(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
