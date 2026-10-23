"""Actual natural-source HTTP qualification; independent encoded measurements."""
from pathlib import Path
import hashlib,json,sys,subprocess,threading,time,urllib.request,urllib.error,struct
import numpy as np
sys.path.insert(0,'/app/studio');import run as studio
sys.path.insert(0,str(studio.APP));from native_yuv import support_masks
OUT=Path(sys.argv[1]);OUT.mkdir(exist_ok=False)
source=Path(sys.argv[2]);start=float(sys.argv[3]);case=json.loads(Path(sys.argv[4]).read_text())
server=studio.make_studio_server(0,OUT/'jobs');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base='http://127.0.0.1:'+str(server.server_address[1]);token=''
def req(path,data=None,expect=200,raw=False,headers=None):
    headers=dict(headers or {})
    if data is not None:headers['X-App-Token']=token
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=45) as response:code=response.status;body=response.read()
    except urllib.error.HTTPError as error:code=error.code;body=error.read()
    assert code==expect,(code,body[:500]);return body if raw else json.loads(body)
def poll(jid):
    until=time.monotonic()+300
    while time.monotonic()<until:
        job=req('/api/jobs/'+jid)
        if job['status'] not in ('queued','analyzing','exporting'):return job
        time.sleep(.3)
    raise TimeoutError(jid)
def native(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
def pcm(path):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    if not any(s['codec_type']=='audio' for s in info['streams']):return None
    return subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','pipe:1'])
record={'complete':False,'source_name':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'start_seconds':start,'authored_defect':False,'selection':case['selection'],'case':case}
try:
    token=req('/api/profile')['csrf_token']
    job=poll(req('/api/imports',source.read_bytes(),202,headers={'X-Filename':source.name,'X-Clip-Start':str(start),'X-Clip-Duration':'12'})['id'])
    print('Prepared',job['status'],job.get('error'),[(c['id'],c['bbox'],c['interval_frames']) for c in job['candidates']],flush=True)
    assert job['status']=='review',job
    candidate=next(c for c in job['candidates'] if c.get('action')=='steady-detail-v1' and (not case.get('bbox') or c['bbox']==case['bbox']))
    jid=job['id'];folder=OUT/'jobs'/jid
    record.update(job_id=jid,preparation=job['preparation'],candidate=candidate)
    x,y,w,h=candidate['influence_xywh']
    # The tutorial's main explanation and command text above this detail.
    areas=case['protected_regions']
    body={'candidate_id':candidate['id'],'prediction_sha256':job['prediction_sha256'],'export_mode':'steady-detail-v1','protected_regions':areas}
    req('/api/jobs/'+jid+'/plan',{**body,'protected_regions':[]},400)
    req('/api/jobs/'+jid+'/plan',{**body,'protected_regions':[{'label':'Overlap','xywh':[x,y,1,1]}]},400)
    planned=req('/api/jobs/'+jid+'/plan',body)
    req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':'0'*64},409)
    assert not (folder/'approval.json').exists()
    req('/api/jobs/'+jid+'/approve',{**body,'approve':True,'recipe_sha256':planned['recipe_sha256']},202)
    final=poll(jid);print('Export',final['status'],final.get('error'),flush=True)
    assert final['status']=='complete',final
    output=OUT/'edited-natural.mp4';output.write_bytes(req('/api/jobs/'+jid+'/download/edited.mp4',raw=True))
    report=req('/api/jobs/'+jid+'/download/report.json')
    decision=req('/api/jobs/'+jid+'/intake/decision')
    source_raw,edited=native(folder/'input.mp4'),native(output)
    bx,by,bw,bh=candidate['bbox'];mask=np.zeros((360,640),np.uint8);mask[by:by+bh,bx:bx+bw]=255
    ym,cm=support_masks(mask);support=np.concatenate([ym.ravel(),cm.ravel(),cm.ravel()])
    lo,hi=candidate['interval_frames'];ref=candidate['reference_frame']
    assert np.array_equal(source_raw[:,~support],edited[:,~support])
    assert np.array_equal(source_raw[:lo],edited[:lo]) and np.array_equal(source_raw[hi+1:],edited[hi+1:])
    for t in range(lo,hi+1):assert np.array_equal(edited[t,support],source_raw[ref,support]),t
    source_pcm=pcm(folder/'input.mp4');output_pcm=pcm(output)
    assert source_pcm==output_pcm
    record['audio_present']=source_pcm is not None
    record.update(independent_native_outside_box_exact=True,independent_all_outside_interval_frames_exact=True,
                  independent_observed_state_mapping_exact=True,independent_decoded_prepared_audio_exact=True,
                  output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),output_bytes=output.stat().st_size,
                  summary=report['summary'],decision=decision)
    assert record['output_sha256']==report['output_hashes']['edited']
    assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/upload',raw=True)).hexdigest()==record['source_sha256']
    assert hashlib.sha256(req('/api/jobs/'+jid+'/intake/prepared',raw=True)).hexdigest()==job['preparation']['prepared_sha256']
    record['original_and_prepared_http_downloads_exact']=True
    for row in final['frame_review']['rows']:
        for asset in row['images'].values():assert hashlib.sha256(req(asset['url'],raw=True)).hexdigest()==asset['sha256']
    record['all_twelve_boundary_http_hashes_exact']=True
    assert 'teaching_review' in final and not final.get('teaching_review_error'),final.get('teaching_review_error')
    teaching_proof=final['teaching_review'];assert teaching_proof['recipe_sha256']==report['recipe_sha256']
    teaching_images={};teacher_dir=OUT/'teaching-images';teacher_dir.mkdir()
    for region in teaching_proof['regions']:
        for moment in region['moments']:
            for role,asset in moment['images'].items():
                payload=req(asset['url'],raw=True);assert hashlib.sha256(payload).hexdigest()==asset['sha256']
                (teacher_dir/asset['filename']).write_bytes(payload)
                image=__import__('cv2').cvtColor(__import__('cv2').imdecode(np.frombuffer(payload,np.uint8),__import__('cv2').IMREAD_COLOR),__import__('cv2').COLOR_BGR2RGB)
                assert hashlib.sha256(image.tobytes()).hexdigest()==asset['decoded_rgb_sha256']
                teaching_images[(region['label'],moment['frame'],role)]=image
    teacher_sequences=[{'source':hashlib.sha256(),'edited':hashlib.sha256()} for a in areas]
    teacher_previous=[{} for a in areas];teacher_changes=[{'source':0,'edited':0} for a in areas]
    record['all_actual_teaching_png_download_hashes_exact']=True
    record['teaching_png_count']=len(teaching_images)
    # Independently verify every protected RGB sample and outside influence.
    def rgb(path):
        return subprocess.Popen(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(path),'-map','0:v:0','-an','-vf',__import__('engine').DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)
    pipes=[rgb(p) for p in (folder/'input.mp4',output)]
    outside=np.ones((360,640),bool);outside[y:y+h,x:x+w]=False
    all_patches=[[],[]];cut_samples={}
    for t in range(360):
        frames=[np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3) for p in pipes]
        for role,frame in enumerate(frames):all_patches[role].append(frame[by:by+bh,bx:bx+bw].copy())
        if t in (0,359,lo-1,lo,hi,hi+1):cut_samples[t]=[{'selected':f[by:by+bh,bx:bx+bw].copy(),'influence':f[y:y+h,x:x+w].copy()} for f in frames]
        assert np.array_equal(frames[0][outside],frames[1][outside]),t
        for i,area in enumerate(areas):
            ax,ay,aw,ah=area['xywh'];assert np.array_equal(frames[0][ay:ay+ah,ax:ax+aw],frames[1][ay:ay+ah,ax:ax+aw]),t
            for role,frame in zip(('source','edited'),frames):
                patch=np.ascontiguousarray(frame[ay:ay+ah,ax:ax+aw]);teacher_sequences[i][role].update(struct.pack('>I',t));teacher_sequences[i][role].update(patch.tobytes())
                if lo<t<=hi and role in teacher_previous[i]:teacher_changes[i][role]+=int(not np.array_equal(patch,teacher_previous[i][role]))
                teacher_previous[i][role]=patch.copy()
                key=(area['label'],t,role)
                if key in teaching_images:assert np.array_equal(teaching_images[key],patch),key
    assert all(p.wait()==0 for p in pipes)

    teacher_records=[]
    for i,area in enumerate(areas):
        reported=report['summary']['teaching_motion']['regions'][i]
        digests={k:v.hexdigest() for k,v in teacher_sequences[i].items()}
        assert digests==reported['ordered_rgb_sequence_sha256'] and digests['source']==digests['edited']
        assert teacher_changes[i]==reported['changed_pairs_inside_hold']
        teacher_records.append({'label':area['label'],'xywh':area['xywh'],'ordered_rgb_sequence_sha256':digests,'changed_pairs_inside_hold':teacher_changes[i],'all_selected_source_and_edited_pngs_match_actual_decoded_frames':True})
    record['independent_teaching_motion']=teacher_records
    first_asset=teaching_proof['regions'][0]['moments'][0]['images']['source'];image_path=folder/first_asset['filename'];original_image=image_path.read_bytes()
    try:
        image_path.write_bytes(original_image+b'tamper');req(first_asset['url'],expect=400)
        changed=req('/api/jobs/'+jid);assert changed.get('teaching_review_error') and 'teaching_review' not in changed
    finally:image_path.write_bytes(original_image)
    assert hashlib.sha256(req(first_asset['url'],raw=True)).hexdigest()==first_asset['sha256']
    record['changed_teaching_png_refused_and_restored']=True
    proof_path=folder/'teaching-review.json';original_proof=proof_path.read_bytes()
    try:
        proof_path.write_bytes(original_proof+b' ');req(first_asset['url'],expect=400)
    finally:proof_path.write_bytes(original_proof)
    assert req('/api/jobs/'+jid)['teaching_review']['recipe_sha256']==report['recipe_sha256']
    record['changed_teaching_review_receipt_refused_and_restored']=True

    # Independent calculation, over decoded source/edit bytes; never calls
    # the proposal selector or the export boundary-measurement implementation.
    independent={}
    for name,a,b in [('entry',lo-1,lo),('exit',hi,hi+1),('loop_seam',359,0)]:
        independent[name]={}
        for region in ('selected','influence'):
            values=[]
            for role in (0,1):
                delta=cut_samples[a][role][region].astype(float)-cut_samples[b][role][region].astype(float)
                values.append({'mean_absolute_rgb_codes':float(abs(delta).mean()),'rms_rgb_codes':float(np.sqrt((delta**2).mean())),'maximum_rgb_codes':float(abs(delta).max())})
            assert all(values[1][k]<=values[0][k]+1e-12 for k in values[0]),(name,region,values)
            reported=report['summary']['encoded_boundary_checks']['measurements'][name][region]
            assert values[0]==reported['source'] and values[1]==reported['edited']
            independent[name][region]={'source':values[0],'edited':values[1],'passed':True}
    temporal=[];events=[]
    for seq in all_patches:
        array=np.stack(seq).astype(float);delta=np.diff(array,axis=0)
        means=array.mean(axis=(1,2,3));crossings=abs(np.diff(means))>=8;events.append(crossings)
        temporal.append({'whole_clip_activity':int(crossings.sum()),'temporal_mean_absolute_sum':float(abs(delta).mean(axis=(1,2,3)).sum()),'temporal_pixel_mse_sum':float((delta**2).mean(axis=(1,2,3)).sum()),'roi_mean_trace':means.tolist()})
    assert temporal[1]['whole_clip_activity']<temporal[0]['whole_clip_activity']
    assert temporal[1]['temporal_pixel_mse_sum']<=temporal[0]['temporal_pixel_mse_sum']+1e-12
    assert not (events[1] & ~events[0]).any()
    record.update(independent_encoded_boundary_checks=independent,independent_whole_clip_temporal={'source':temporal[0],'edited':temporal[1],'new_activity_events':int((events[1]&~events[0]).sum())},independent_boundaries_not_worse=True)

    record.update(independent_all_360_teaching_rgb_frames_exact=True,independent_all_rgb_outside_influence_exact=True,
                  complete=True,runtime_manifest_sha256=hashlib.sha256((studio.ROOT/'BUILD_HASHES.json').read_bytes()).hexdigest())
    print('NATURAL STEADY REPAIR QUALIFIED',record['output_sha256'],record['summary']['stationary_detail']['activity'],flush=True)
finally:
    server.shutdown();thread.join();server.manager.close();server.server_close()
    (OUT/'results.json').write_text(json.dumps(record,indent=2))
