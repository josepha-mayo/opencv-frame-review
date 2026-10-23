"""Exploratory recheck of two previously negative, real editor tutorials."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,subprocess,sys,datetime
import numpy as np,cv2
sys.path.insert(0,'/app/studio');import steady_boundaries
sys.path.insert(0,'/app/opencv-ready/candidate/app');import engine
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
sources=json.loads(Path('/audit/reading-lessons-sources.json').read_text())
record={'complete':False,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_manifest_sha256':hashlib.sha256(Path('/app/studio/BUILD_HASHES.json').read_bytes()).hexdigest(),'scope':'Exploratory fixed non-overlapping twelve-second grid, from zero through duration-12, capped at 600 seconds. Two previously screened negative editor tutorials, chosen by topic before these outcomes. Offline preparation/detection only; useful meaning and HTTP/export qualification remain separate. No detector code is changed from the frozen v5 build.','sources':sources,'cases':[]}
def decode(path,label):
    p=subprocess.Popen(['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',str(path),'-an','-vf',engine.DECODE_FILTER,'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],stdout=subprocess.PIPE)
    for _ in range(360):yield np.frombuffer(p.stdout.read(640*360*3),np.uint8).reshape(360,640,3)
    assert p.wait()==0
e=SimpleNamespace(W=640,H=360,N=360,np=np,cv2=cv2,LUT=engine.LUT,WEIGHTS=engine.WEIGHTS,decode=decode,guard=lambda:None)
for source in sources:
    path=Path('/originals')/source['filename'];assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    duration=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(path)]))['format']['duration'])
    for start in range(0,min(600,int(duration)-11)+1,12):
        folder=out/(path.stem+'-'+str(start));folder.mkdir()
        (folder/'uploaded-original.bin').symlink_to(path)
        (folder/'prepare-request.json').write_text(json.dumps({'start_seconds':start,'duration_seconds':12,'upload_sha256':source['sha256']}))
        run=subprocess.run([sys.executable,'/app/studio/prepare_worker.py',str(folder)],capture_output=True,text=True)
        (folder/'prepare.log').write_text(run.stdout+run.stderr)
        row={'source':path.stem,'start_seconds':start,'original_sha256':source['sha256'],'preparation_returncode':run.returncode,'authored_defect':False}
        if run.returncode:row['error']=json.loads((folder/'prepare-error.json').read_text())
        else:
            prepared=folder/'input.mp4'
            raw=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(prepared),'-an','-pix_fmt','yuv420p','-f','rawvideo','pipe:1']),np.uint8).reshape(360,-1)
            row.update(prepared_sha256=hashlib.sha256(prepared.read_bytes()).hexdigest(),detection=steady_boundaries.detect(e,prepared,raw))
        record['cases'].append(row);(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
        print(path.stem,start,'proposals',len(row.get('detection',{}).get('candidates',[])),flush=True)
record.update(complete=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
