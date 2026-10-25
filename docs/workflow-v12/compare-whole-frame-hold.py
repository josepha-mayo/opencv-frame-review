"""Independent encoded ablation on saved real-source packs; no human-impact claim."""
from pathlib import Path
import hashlib, json, shutil, struct, subprocess, zipfile, os
import numpy as np

W=Path(__file__).resolve().parent
O=Path(os.environ.get('FRAME_ABLATION_OUTPUT',str(W.parent/'outputs/workflow-v12/ablation')))
PACK_ROOT=Path(os.environ.get('FRAME_ABLATION_PACK_ROOT',str(W.parent/'outputs/offline-v11')))
O.mkdir(parents=True,exist_ok=True)
FF=shutil.which('ffmpeg')
assert FF
FILTER='scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=tv:out_range=pc:in_chroma_loc=left:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact+full_chroma_int,format=rgb24'
receipt={'complete':False,'scope':'Independent encoded video-only ablation on selected saved media. Not an app output, new source discovery, teacher trial or runtime qualification. Decoder teaching digests must match pinned Linux results before comparison.','ffmpeg_version':subprocess.check_output([FF,'-version'],text=True).splitlines()[0],'cases':[]}
def save(): (O/'results.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
save()
for name in ('upload-assistant','joomla'):
    row={'case':name,'complete':False};receipt['cases'].append(row);save()
    folder=O/name;folder.mkdir(exist_ok=False)
    pack=PACK_ROOT/(name+'-AWS-Rescue-Pack.zip')
    with zipfile.ZipFile(pack) as z:
        manifest=json.loads(z.read('manifest.json'))
        for member,info in manifest['files'].items():
            raw=z.read(member);assert len(raw)==info['bytes'] and hashlib.sha256(raw).hexdigest()==info['sha256']
        report=json.loads(z.read('report.json'));recipe=json.loads(z.read('recipe.json'))
        for member in ('prepared-lesson.mp4','edited.mp4'):(folder/member).write_bytes(z.read(member))
    source=folder/'prepared-lesson.mp4';edited=folder/'edited.mp4';proposal=recipe['proposal']
    lo,hi=proposal['interval_frames'];ref=proposal['reference_frame'];bx,by,bw,bh=proposal['bbox']
    raw=subprocess.check_output([FF,'-v','error','-threads','1','-i',str(source),'-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1'])
    native=np.frombuffer(raw,np.uint8).reshape(360,640*360*3//2)
    baseline=folder/'COUNTERFACTUAL-whole-frame-hold-video-only.mp4'
    command=[FF,'-v','error','-n','-threads','1','-f','rawvideo','-pixel_format','yuv420p','-video_size','640x360','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-threads','1','-preset','fast','-qp','0','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-chroma_sample_location','left',str(baseline)]
    command[command.index('-an')+1:command.index('-an')+1]=['-vf','setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709']
    encoder=subprocess.Popen(command,stdin=subprocess.PIPE)
    for t in range(360):encoder.stdin.write(native[ref if lo<=t<=hi else t].tobytes())
    encoder.stdin.close();assert encoder.wait()==0
    verified=np.frombuffer(subprocess.check_output([FF,'-v','error','-threads','1','-i',str(baseline),'-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
    assert all(np.array_equal(verified[t],native[ref if lo<=t<=hi else t]) for t in range(360)), 'Counterfactual native samples changed during encoding; exclude this baseline.'
    row['baseline_native_samples_exact']=True
    del raw,native,verified
    def rgb(path):return subprocess.Popen([FF,'-v','error','-threads','1','-filter_threads','1','-i',str(path),'-an','-vf',FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)
    regions=report['teaching_review']['regions']
    mask=np.zeros((360,640),bool)
    for region in regions:
        x,y,w,h=region['xywh'];mask[y:y+h,x:x+w]=True
    pipes=[rgb(p) for p in (source,edited,baseline)]
    digests=[{r['label']:hashlib.sha256() for r in regions} for role in range(3)]
    trace=[[] for role in range(3)];changed_frames=[0,0,0];changed_samples=[0,0,0]
    for t in range(360):
        frames=[np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3) for p in pipes]
        for role,frame in enumerate(frames):
            trace[role].append(float(frame[by:by+bh,bx:bx+bw].mean()))
            for region in regions:
                x,y,w,h=region['xywh'];patch=np.ascontiguousarray(frame[y:y+h,x:x+w]);d=digests[role][region['label']];d.update(struct.pack('>I',t));d.update(patch.tobytes())
            if lo<=t<=hi:
                mismatch=frame[mask]!=frames[0][mask]
                changed_frames[role]+=int(mismatch.any());changed_samples[role]+=int(mismatch.sum())
    assert all(p.wait()==0 for p in pipes)
    for role,key in [(0,'source'),(1,'edited')]:
        for region in regions:
            assert digests[role][region['label']].hexdigest()==region['ordered_rgb_sequence_sha256'][key],(name,role,region['label'])
    rows=[]
    for i,label in enumerate(('Keep source','Reviewed local hold','Whole-frame hold counterfactual')):
        values=np.asarray(trace[i]);inside=int((abs(np.diff(values[lo:hi+1]))>=8).sum());whole=int((abs(np.diff(values))>=8).sum())
        rows.append({'method':label,'inside_hold_activity':inside,'whole_excerpt_activity':whole,'held_teaching_frames_changed_from_source':changed_frames[i],'held_teaching_rgb_samples_changed_from_source':changed_samples[i]})
    assert rows[1]['held_teaching_frames_changed_from_source']==0
    assert rows[2]['held_teaching_frames_changed_from_source']>0
    assert rows[1]['inside_hold_activity']==rows[2]['inside_hold_activity']==0
    row.update(complete=True,source_pack_sha256=hashlib.sha256(pack.read_bytes()).hexdigest(),prepared_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),edited_sha256=hashlib.sha256(edited.read_bytes()).hexdigest(),counterfactual_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),source_and_local_all_teaching_digests_match_pinned_linux=True,hold_frames=hi-lo+1,reference_frame=ref,activity_definition='Adjacent selected-mean RGB changes >=8 codes; not semantic events.',results=rows)
    save();print(name,json.dumps(rows),flush=True)
receipt['complete']=True;save()
