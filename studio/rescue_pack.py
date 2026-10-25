"""One bounded, source-checked recovery archive; never archives a job directory."""
import hashlib
import io
import json
import re
import zipfile
import base64
import html

MAX_PACK_BYTES = 112 * 1024**2


def offline_review(report, members):
    """A self-contained static review, derived only from already verified artifacts."""
    esc=lambda value:html.escape(str(value),quote=True)
    summary=report['summary'];detail=summary['stationary_detail']
    def images(assets):
        result=[]
        for role,asset in assets.items():
            raw=members[asset['filename']]
            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(raw).hexdigest()!=asset['sha256']:
                raise ValueError('Offline review proof image changed.')
            result.append('<figure><figcaption>'+esc(role)+'</figcaption><img alt="'+esc(role+' static decoded proof')+'" src="data:image/png;base64,'+base64.b64encode(raw).decode()+'"></figure>')
        return '<div class="images">'+''.join(result)+'</div>'
    parts=['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
           '<title>Frame Review · Offline proof</title><style>',
           'body{margin:0;background:#f4f6f2;color:#162d25;font:16px/1.6 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:24px}h1{font-size:clamp(28px,5vw,48px);line-height:1.15}h2{margin-top:32px}.card,details{background:white;border:1px solid #cdd8cf;border-radius:12px;padding:18px;margin:18px 0}.status{font-weight:700;color:#365244}a{color:#174f42}nav{display:flex;gap:16px;flex-wrap:wrap}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(230px,100%),1fr));gap:12px}figure{min-width:0;margin:0}img{display:block;max-width:100%;height:auto;image-rendering:pixelated;border:1px solid #d8dfd9}figcaption{font-weight:700}code,pre{overflow-wrap:anywhere;white-space:pre-wrap;font-size:13px}ul{padding-left:22px}summary{cursor:pointer;font-weight:700}li{margin:8px 0}@media print{body{background:white}main{padding:0}.card,details{break-inside:avoid}a{color:inherit}}',
           '</style></head><body><main><p class="status">FRAME REVIEW / KEEP THE LESSON</p><h1>The comparison survives the job.</h1>',
           '<p>Offline proof page · all images are embedded. No server, account, script, network request or video playback is needed to inspect this page.</p>',
           '<div class="card"><strong>Generated comparison. Your decision is still required.</strong><p>Inspect whether the caret conveys teaching information and whether the prepared text is readable. Passing pixel checks does not establish readability, learning, attention, accessibility or time saved. This page does not record creator acceptance.</p></div>',
           '<nav aria-label="Proof sections"><a href="#boundaries">Cut points</a><a href="#teaching">Teaching timeline</a><a href="#files">Files &amp; provenance</a></nav>',
           '<section class="card"><h2>What the encoded checks report</h2><p>Selected activity inside hold: '+esc(detail['activity']['source'])+' → '+esc(detail['activity']['edited'])+'. Whole excerpt: '+esc(detail['whole_clip_activity']['source'])+' → '+esc(detail['whole_clip_activity']['edited'])+'. Newly timed threshold events: '+esc(detail['new_activity_events'])+'.</p>',
           '<p>Activity counts adjacent selected-mean RGB differences of at least eight codes. The three proof moments below are samples; the ordered teaching digests check the complete prepared excerpt.</p><ul>']
    for name,value in summary['checks'].items():
        parts.append('<li>'+esc(name.replace('_',' '))+': <strong>'+('PASS'if value is True else'NOT PASS')+'</strong></li>')
    parts.extend(['</ul><p>Prepared source SHA-256: <code>'+esc(report['input_sha256'])+'</code><br>Reviewed recipe SHA-256: <code>'+esc(report['recipe_sha256'])+'</code></p></section>',
                  '<section id="boundaries"><h2>Inspect entry and return cut points</h2>'])
    for row in report['frame_review']['rows']:
        parts.append('<article class="card"><h3>'+esc(row['label'])+' · frame '+esc(row['frame'])+'</h3>'+images(row['images'])+'</article>')
    parts.append('</section><section id="teaching"><h2>Inspect what keeps its timeline</h2>')
    for region in report['teaching_review']['regions']:
        parts.append('<article class="card"><h3>'+esc(region['label'])+'</h3><p>Prepared coordinates: <code>'+esc(region['xywh'])+'</code>. Ordered RGB sequence across '+esc(region['frames'])+' frames: <strong>'+('EXACT'if region['ordered_rgb_sequence_exact'] is True else'NOT EXACT')+'</strong>.</p>')
        parts.append('<details><summary>Ordered source/edit digests</summary><pre>'+esc(json.dumps(region['ordered_rgb_sequence_sha256'],indent=2))+'</pre></details>')
        for moment in region['moments']:
            parts.append('<h4>'+esc(' / '.join(moment['roles']))+' · frame '+esc(moment['frame'])+'</h4>'+images(moment['images']))
        parts.append('</article>')
    parts.append('</section><section id="files" class="card"><h2>Files &amp; provenance</h2><p>Extract the pack before using these relative file links. Keep the original. Exact edit checks reference the prepared clip, which can differ in resolution, picture and audio from the upload. Inspect manifest.json file hashes; this page does not independently authenticate the server.</p><ul>')
    for name in sorted(members):
        if not name.endswith('.png'):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',name):raise ValueError('Invalid offline artifact name.')
            parts.append('<li><a download href="'+esc(name)+'">'+esc(name)+'</a></li>')
    parts.append('<li><a download href="manifest.json">manifest.json</a></li></ul><p>The original upload is included only for upload jobs. Built-in samples include their prepared excerpt and provenance, not the full original. Source permission and licensing remain your responsibility. Credit and preparation details are in the provenance files above.</p></section></main></body></html>')
    return ''.join(parts).encode()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def archive(members, binding, limit=MAX_PACK_BYTES):
    """Fixed safe members only; no directory walk, compression or executable entries."""
    if not isinstance(members,dict) or not members or len(members)>64:
        raise ValueError('Rescue pack exceeds its bounded size; use individual artifacts.')
    for name,data in members.items():
        if not isinstance(data,bytes) or not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',name) or name=='manifest.json':
            raise ValueError('Invalid rescue-pack member.')
    if sum(map(len,members.values()))>limit:
        raise ValueError('Rescue pack exceeds its bounded size; use individual artifacts.')
    manifest={'schema':'lesson-rescue-pack-v1','binding':binding,'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}for name,data in sorted(members.items())},'meaning':'Hashes bind the downloaded files, not creator benefit, readability, rights clearance or independent server authenticity.'}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED)as z:
        for name,data in [*sorted(members.items()),('manifest.json',json.dumps(manifest,indent=2,allow_nan=False).encode())]:
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.create_system=3;info.external_attr=(0o100644<<16)
            z.writestr(info,data)
    if output.tell()>limit+128*1024:raise ValueError('Rescue-pack envelope exceeds its bound.')
    return output.getvalue()


def build(manager,jid,backend,studio,original_download,natural_examples,max_upload):
    """Validate media, reviewed recipe, report and every included proof before headers."""
    job=manager.view(jid)
    if job['status']!='complete' or job.get('frame_review_error') or job.get('teaching_review_error'):
        raise backend.Conflict('A complete verified comparison is required for a rescue pack.')
    folder=manager.jobpath(jid)
    read=lambda name,limit=2*1024**2:backend.bounded_regular_bytes(folder/name,limit)
    export=json.loads(read('export.json'));approval=json.loads(read('approval.json'))
    result=json.loads(read('result.json'))
    if result.get('schema')!='steady-detail-export-v2' or not all(export['summary']['checks'].values()):
        raise ValueError('Rescue pack requires the verified observed-brightness export.')
    report_raw=read('report.json');recipe_raw=read('recipe.json');report=json.loads(report_raw);recipe=json.loads(recipe_raw);analysis=json.loads(read('analysis.json'))
    if hashlib.sha256(canonical(recipe)).hexdigest()!=approval.get('recipe_sha256') or recipe!=approval.get('recipe') or report.get('approval')!=approval or report.get('summary')!=export['summary'] or report.get('recipe_sha256')!=approval['recipe_sha256'] or report.get('output_hashes')!=export['output_hashes'] or any(report.get(k)!=analysis.get(k)for k in ('input_sha256','prediction_sha256')):
        raise ValueError('Rescue-pack report or reviewed recipe changed.')
    prepared=manager.video_bytes(jid,'original.mp4')
    if hashlib.sha256(prepared).hexdigest()!=report.get('input_sha256'):
        raise ValueError('Rescue-pack report source changed.')
    text=read('report.txt');expected=('Steady observed detail\n\n'+json.dumps(report['summary'],indent=2)+'\n\nReview the original and edited clip before use.\n').encode()
    if text!=expected:raise ValueError('Readable rescue-pack report changed.')
    members={'prepared-lesson.mp4':prepared,'edited.mp4':manager.video_bytes(jid,'edited.mp4'),'control.mp4':manager.video_bytes(jid,'control.mp4'),'report.json':report_raw,'recipe.json':recipe_raw,'report.txt':text}
    preparation=manager.preparation(jid)
    if preparation:
        original=backend.bounded_regular_bytes(manager.uploaded_path(jid),max_upload)
        if hashlib.sha256(original).hexdigest()!=preparation['uploaded_sha256'] or hashlib.sha256(prepared).hexdigest()!=preparation['prepared_sha256']:
            raise ValueError('Rescue-pack retained source changed.')
        _,name=original_download(original);members[name]=original
        members['preparation.json']=json.dumps(preparation,indent=2).encode()
        members['lesson-decision.json']=json.dumps(manager.decision_record(jid),indent=2).encode()
    if job.get('sample_credit'):
        example=job['sample_credit'].get('id','terminal');_,credit_name=natural_examples[example]
        credit=backend.bounded_regular_bytes(studio/'fixtures'/credit_name,128*1024)
        expected_hash=json.loads(backend.bounded_regular_bytes(studio/'BUILD_HASHES.json',256*1024))['files']['studio/fixtures/'+credit_name]
        if hashlib.sha256(credit).hexdigest()!=expected_hash or json.loads(credit)!=job['sample_credit']:
            raise ValueError('Rescue-pack example provenance changed.')
        members['sample-provenance.json']=credit
    for filename,getter,key in [('frame-review.json',manager.frame_review,'frame_review_sha256'),('teaching-review.json',manager.teaching_review,'teaching_review_sha256')]:
        proof=getter(jid);raw=read(filename)
        if not proof or hashlib.sha256(raw).hexdigest()!=export.get(key):raise ValueError('Rescue-pack proof binding changed.')
        report_key='frame_review'if filename=='frame-review.json'else'teaching_review'
        if report.get(report_key)!=json.loads(raw):raise ValueError('Rescue-pack embedded report proof changed.')
        members[filename]=raw
        assets=([image for row in proof['rows']for image in row['images'].values()]if filename=='frame-review.json'else[image for region in proof['regions']for moment in region['moments']for image in moment['images'].values()])
        for asset in assets:members[asset['filename']]=backend.verified_image_bytes(folder/asset['filename'],asset['sha256'])
    members['README.txt']=('Frame Review rescue pack\n\nOpen review.html for a self-contained static proof page, including every boundary and teaching image. It needs no server, account, script or video playback. Extract the pack to use its artifact links.\n\nKeep this archive before the server job expires. Verify manifest.json file hashes, inspect report.json, the teaching and boundary PNGs, then decide whether to use edited.mp4. Generating a comparison is not acceptance for use.\n\nExact edit checks reference prepared-lesson.mp4; preparation changes source picture/audio. An uploaded-original file is included only for original-upload jobs. Built-in examples retain sample-provenance.json and do not contain the full original lesson. Individual links remain available. Source licensing/permission and creator review remain your responsibility. No measured learning, attention, accessibility or time-saving benefit.\n').encode()
    if 'workflow' not in job:
        raise ValueError('Source-bound workflow unavailable for rescue pack.')
    members['vision-workflow.json']=json.dumps(job['workflow'],indent=2,allow_nan=False).encode()
    members['review.html']=offline_review(report,members)
    runtime=backend.bounded_regular_bytes(studio/'BUILD_HASHES.json',256*1024)
    binding={'job_id':jid,'source_manifest_sha256':hashlib.sha256(runtime).hexdigest(),'input_sha256':report['input_sha256'],'recipe_sha256':report['recipe_sha256'],'output_hashes':report['output_hashes'],'sample_mapping':report['summary']['sample_mapping'],'uploaded_original_included':bool(preparation)}
    return archive(members,binding)
