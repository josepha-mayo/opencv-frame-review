from pathlib import Path
import datetime,hashlib,json,math,subprocess,sys
import numpy as np,cv2
sys.path.insert(0,'/app/studio');import steady_detail
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
metadata=json.loads(Path('/audit/natural-v4-sources.json').read_text())
manifest=hashlib.sha256(Path('/app/studio/BUILD_HASHES.json').read_bytes()).hexdigest()
record={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':manifest,
 'selection_plan_sha256':hashlib.sha256(Path('/audit/natural-v4-selection-plan.json').read_bytes()).hexdigest(),
 'scope':'Offline production preparation plus unchanged detector; this does not establish HTTP/browser/export success. New-source convenience cohort. All selected windows retained.',
 'complete':False,'cases':[]}
for row in metadata:
    source=Path('/new')/row['filename'];assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(source)]))
    duration=float(probe['format']['duration']);starts=[min(600,int(duration*q)) for q in (.25,.5,.75)]
    for start in starts:
        folder=out/(row['id']+'-'+str(start));folder.mkdir(exist_ok=False)
        (folder/'uploaded-original.bin').symlink_to(source)
        (folder/'prepare-request.json').write_text(json.dumps({'start_seconds':start,'duration_seconds':12,'upload_sha256':row['sha256']}))
        run=subprocess.run([sys.executable,'/app/studio/prepare_worker.py',str(folder)],capture_output=True,text=True)
        result={'source':row['id'],'start_seconds':start,'duration_seconds':12,'original_sha256':row['sha256'],'preparation_returncode':run.returncode}
        if run.returncode:
            result['preparation_error']=json.loads((folder/'prepare-error.json').read_text())
        else:
            prepared=folder/'input.mp4'
            raw=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(prepared),'-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
            result.update(prepared_sha256=hashlib.sha256(prepared.read_bytes()).hexdigest(),detection=steady_detail.detect_native(raw,640,360,cv2,np))
            (folder/'detection.json').write_text(json.dumps(result['detection'],indent=2))
        record['cases'].append(result);(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
        print('Processed fixed cohort case',row['id'],start,flush=True)
record.update(complete=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
