"""Actual authored-lesson HTTP export plus independent decoded video/audio checks."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import numpy as np

STUDIO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STUDIO))
import run as studio
sys.path.insert(0,str(studio.APP))
import engine
from native_yuv import support_masks
from server import make_server

OUT=Path(sys.argv[1]);OUT.mkdir(exist_ok=False)
SOURCE=STUDIO/'fixtures/lesson.mp4'
AREAS=[{'label':'Equation','xywh':[20,55,245,52]},
       {'label':'Explanation','xywh':[20,112,255,105]},
       {'label':'Graph','xywh':[300,45,330,200]},
       {'label':'Step counter','xywh':[20,250,205,36]}]
server=make_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1])

def req(path,data=None,expect=200,raw=False):
    headers={}
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=20) as response:status,body=response.status,response.read()
    except urllib.error.HTTPError as error:status,body=error.code,error.read()
    assert status==expect,(status,body)
    return body if raw else json.loads(body)

def poll(jid):
    until=time.monotonic()+250
    while time.monotonic()<until:
        job=req('/api/jobs/'+jid)
        if job['status'] not in ('queued','analyzing','exporting'):return job
        time.sleep(.3)
    raise TimeoutError(jid)

def command(*args):return subprocess.check_output(list(args))

def native(path):
    data=command('/usr/bin/ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-pix_fmt','yuv420p','-f','rawvideo','pipe:1')
    assert len(data)==360*640*360*3//2
    return np.frombuffer(data,np.uint8).reshape(360,-1)

def audio(path):
    packets=json.loads(command('/usr/bin/ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_streams','-show_data_hash','sha256','-show_entries','stream=codec_name,profile,sample_rate,channels,channel_layout,time_base,start_pts,duration_ts,extradata_hash:packet=pts,dts,duration,size,flags,data_hash,side_data_list','-of','json',str(path)))
    pcm=command('/usr/bin/ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1')
    return packets,hashlib.sha256(pcm).hexdigest(),len(pcm)

def video_times(path):
    return json.loads(command('/usr/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp,pkt_duration','-of','json',str(path)))

try:
    token=req('/api/profile')['csrf_token']
    job=poll(req('/api/jobs',SOURCE.read_bytes(),202)['id'])
    assert job['status']=='review' and job['candidates'],job
    jid=job['id'];folder=OUT/'jobs'/jid
    candidate=next(c for c in job['candidates'] if c['bbox'][0]>=530)
    body={'candidate_id':candidate['id'],'prediction_sha256':job['prediction_sha256'],'export_mode':'periodic-local-retime-v2','protected_regions':AREAS}
    plan=req('/api/jobs/'+jid+'/plan',body)
    assert not (folder/'approval.json').exists()
    req('/api/jobs/'+jid+'/approve',{**body,'approve':False,'recipe_sha256':plan['recipe_sha256']},400)
    req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':plan['recipe_sha256']},202)
    job=poll(jid);assert job['status']=='complete',job
    assert job['summary']['protected_content']['passed']
    assert len(job['summary']['protected_content']['regions'])==4
    assert len(job['frame_review']['rows'])==4
    for row in job['frame_review']['rows']:
        for asset in row['images'].values():
            data=req(asset['url'],raw=True)
            assert hashlib.sha256(data).hexdigest()==asset['sha256']
    edited=req('/api/jobs/'+jid+'/download/edited.mp4',raw=True)
    output=OUT/'edited.mp4';output.write_bytes(edited)
    report=req('/api/jobs/'+jid+'/download/report.json')
    assert hashlib.sha256(edited).hexdigest()==report['output_hashes']['edited']
    original=native(SOURCE);result=native(output);control=native(folder/'control.mp4')
    assert np.array_equal(original,control)
    prediction=json.loads((folder/'prediction.json').read_text())
    component=prediction['components'][int(candidate['id'])]
    engine.W,engine.H=640,360
    mask=engine.unpack_mask(component['mask_rle'],[360,640]);ym,cm=support_masks(mask)
    support=np.concatenate([ym.ravel(),cm.ravel(),cm.ravel()]).astype(bool)
    decision=json.loads((folder/'result.json').read_text())
    mapping=np.array(decision['recipe']['mapping'])
    assert np.array_equal(original[:,~support],result[:,~support])
    assert np.array_equal(original[mapping][:,support],result[:,support])
    assert not np.array_equal(original,result)
    assert audio(SOURCE)==audio(output)==audio(folder/'control.mp4')
    assert video_times(SOURCE)==video_times(output)==video_times(folder/'control.mp4')
    # An independent frame-stream comparison protects the actual equation,
    # explanatory text, changing graph marker and changing step counter.
    decoders=[subprocess.Popen(['/usr/bin/ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE) for path in (SOURCE,output)]
    for t in range(360):
        frames=[np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3) for p in decoders]
        for area in AREAS:
            x,y,w,h=area['xywh'];assert np.array_equal(frames[0][y:y+h,x:x+w],frames[1][y:y+h,x:x+w]),(area['label'],t)
    assert all(p.wait()==0 for p in decoders)
    receipt={'fixture':'Authored 12-second math lesson with neural narration','input_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'edited_sha256':hashlib.sha256(edited).hexdigest(),'protected_regions':AREAS,'all_360_frames_protected_rgb_exact':True,'independent_native_mapping_exact':True,'outside_native_pixels_exact':True,'audio_packets_pcm_timing_exact':True,'video_timestamps_exact':True,'all_12_comparison_png_hashes_exact':True,'summary':job['summary']}
    (OUT/'result.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps({key:value for key,value in receipt.items() if key!='summary'}),flush=True)
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close()
