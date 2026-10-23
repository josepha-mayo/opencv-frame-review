"""Decode the actual AWS browser downloads; do not assume cross-host byte identity."""
from pathlib import Path
import hashlib,json,subprocess,sys,struct
import numpy as np,cv2
sys.path.insert(0,'/app/studio');import run as studio
sys.path.insert(0,str(studio.APP));from native_yuv import support_masks
from engine import DECODE_FILTER
config=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
source=Path(config['prepared']);edited=Path(config['edited']);report=json.loads(Path(config['report']).read_text());recipe=json.loads(Path(config['recipe']).read_text());candidate=recipe['proposal'];lo,hi=candidate['interval_frames'];ref=candidate['reference_frame'];areas=recipe['protected_regions']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
record={'complete':False,'case':config['case'],'prepared_sha256':sha(source),'edited_sha256':sha(edited),'scope':'Independent decoding of actual AWS browser downloads against their own prepared reference. Cross-host preparation identity is measured separately, not assumed.'}
def decode(path,fmt):return subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:v:0','-an','-pix_fmt',fmt,'-f','rawvideo','pipe:1'])
def packets(path,stream):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams',stream,'-show_packets','-show_data_hash','sha256','-of','json',str(path)]))['packets']
def audio(path):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    if not any(s['codec_type']=='audio' for s in info['streams']):return None
    return subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','pipe:1'])
try:
    assert record['prepared_sha256']==report['input_sha256'] and record['edited_sha256']==report['output_hashes']['edited'];assert all(report['summary']['checks'].values())
    a=np.frombuffer(decode(source,'yuv420p'),np.uint8).reshape(360,-1);b=np.frombuffer(decode(edited,'yuv420p'),np.uint8).reshape(360,-1)
    x,y,w,h=candidate['bbox'];mask=np.zeros((360,640),np.uint8);mask[y:y+h,x:x+w]=255;ym,cm=support_masks(mask);support=np.concatenate([ym.ravel(),cm.ravel(),cm.ravel()]);assert np.array_equal(a[:,~support],b[:,~support]);assert np.array_equal(a[:lo],b[:lo]) and np.array_equal(a[hi+1:],b[hi+1:]);assert all(np.array_equal(b[t,support],a[ref,support]) for t in range(lo,hi+1))
    record.update(native_outside_box_exact=True,outside_interval_exact=True,observed_reference_mapping_exact=True)
    source_audio=audio(source);assert source_audio==audio(edited)
    ap=packets(source,'a:0');bp=packets(edited,'a:0');keys=('pts','dts','duration','data_hash','side_data_list');assert [{k:p.get(k) for k in keys} for p in ap]==[{k:p.get(k) for k in keys} for p in bp]
    assert [{k:p.get(k) for k in ('pts','dts','duration')} for p in packets(source,'v:0')]==[{k:p.get(k) for k in ('pts','dts','duration')} for p in packets(edited,'v:0')]
    record.update(prepared_audio_pcm_packets_timing_exact=True,video_timestamps_exact=True,audio_present=source_audio is not None)
    local=Path(config['local_prepared']);local_audio=audio(local);record['cross_host_preparation']={'prepared_files_identical':sha(local)==sha(source),'video_packet_payloads_identical':[p['data_hash'] for p in packets(local,'v:0')]==[p['data_hash'] for p in packets(source,'v:0')],'audio_packet_payloads_identical':[p['data_hash'] for p in packets(local,'a:0')]==[p['data_hash'] for p in ap],'decoded_prepared_pcm_identical':local_audio==source_audio,'native_yuv_identical':np.array_equal(a,np.frombuffer(decode(local,'yuv420p'),np.uint8).reshape(360,-1))}
    del a,b
    sequences=[{'source':hashlib.sha256(),'edited':hashlib.sha256()} for area in areas];changes=[{'source':0,'edited':0} for area in areas];previous=[{}for area in areas];patches=[[],[]];cuts={};teaching_checks=[]
    proof_images={}
    for region in report['teaching_review']['regions']:
        for moment in region['moments']:
            for role,asset in moment['images'].items():
                image_path=Path(config['teaching_files'][asset['filename']]);assert sha(image_path)==asset['sha256'];image=cv2.cvtColor(cv2.imdecode(np.frombuffer(image_path.read_bytes(),np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB);assert hashlib.sha256(image.tobytes()).hexdigest()==asset['decoded_rgb_sha256'];proof_images[(region['label'],moment['frame'],role)]=image
    processes=[subprocess.Popen(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(p),'-map','0:v:0','-an','-vf',DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE) for p in (source,edited)]
    ix,iy,iw,ih=candidate['influence_xywh'];outside=np.ones((360,640),bool);outside[iy:iy+ih,ix:ix+iw]=False
    for t in range(360):
        frames=[]
        for process in processes:
            raw=process.stdout.read(640*360*3);assert len(raw)==640*360*3;frames.append(np.frombuffer(raw,np.uint8).reshape(360,640,3))
        assert np.array_equal(frames[0][outside],frames[1][outside])
        for i,area in enumerate(areas):
            px,py,pw,ph=area['xywh'];pair=[np.ascontiguousarray(f[py:py+ph,px:px+pw])for f in frames];assert np.array_equal(*pair)
            for role,crop in zip(('source','edited'),pair):
                sequences[i][role].update(struct.pack('>I',t));sequences[i][role].update(crop.tobytes())
                if lo<t<=hi and role in previous[i]:changes[i][role]+=int(not np.array_equal(previous[i][role],crop))
                previous[i][role]=crop.copy();image=proof_images.get((area['label'],t,role))
                if image is not None:assert np.array_equal(image,crop)
        for i,f in enumerate(frames):patches[i].append(f[y:y+h,x:x+w].copy())
        if t in {lo-1,lo,hi,hi+1,0,359}:cuts[t]=[{'selected':f[y:y+h,x:x+w].copy(),'influence':f[iy:iy+ih,ix:ix+iw].copy()}for f in frames]
    for process in processes:assert not process.stdout.read(1) and process.wait()==0
    for i,area in enumerate(areas):
        measured=report['summary']['teaching_motion']['regions'][i];digests={role:d.hexdigest()for role,d in sequences[i].items()};assert digests==measured['ordered_rgb_sequence_sha256'] and changes[i]==measured['changed_pairs_inside_hold'];teaching_checks.append({'label':area['label'],'frames':360,'ordered_rgb_sequence_sha256':digests,'changed_pairs_inside_hold':changes[i],'all_source_edit_samples_exact':True})
    boundaries={}
    for name,first,last in [('entry',lo-1,lo),('exit',hi,hi+1),('loop_seam',359,0)]:
        boundaries[name]={}
        for region in ('selected','influence'):
            values=[]
            for role in (0,1):
                delta=cuts[first][role][region].astype(float)-cuts[last][role][region].astype(float);values.append({'mean_absolute_rgb_codes':float(abs(delta).mean()),'rms_rgb_codes':float(np.sqrt((delta**2).mean())),'maximum_rgb_codes':float(abs(delta).max())})
            assert all(values[1][key]<=values[0][key]+1e-12 for key in values[0]);reported=report['summary']['encoded_boundary_checks']['measurements'][name][region];assert values[0]==reported['source'] and values[1]==reported['edited'];boundaries[name][region]={'source':values[0],'edited':values[1],'passed':True}
    events=[abs(np.diff(np.stack(p).astype(float).mean(axis=(1,2,3))))>=8 for p in patches];assert events[1].sum()<events[0].sum() and not(events[1]&~events[0]).any()
    record.update(complete=True,all_360_teaching_rgb_frames_exact=True,all_rgb_outside_influence_exact=True,teaching=teaching_checks,actual_teaching_pngs_independently_decoded=len(proof_images),boundaries=boundaries,whole_excerpt_activity={'source':int(events[0].sum()),'edited':int(events[1].sum()),'new_events':int((events[1]&~events[0]).sum())})
    print(json.dumps({'complete':True,'case':config['case'],'cross_host_preparation':record['cross_host_preparation'],'whole_excerpt_activity':record['whole_excerpt_activity']}),flush=True)
finally:(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
