"""One bounded processing stage. No network operations."""
import os,sys,time
START=time.monotonic()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
from common import *

def main():
 if len(sys.argv)!=3 or sys.argv[1] not in ('analyze','export'):raise SystemExit('usage: worker.py analyze|export JOB_DIRECTORY')
 mode=sys.argv[1];job=Path(sys.argv[2]).resolve()
 if not job.is_dir() or not (job/'input.mp4').is_file():raise SystemExit('Job input missing')
 import engine
 bounds=engine.Bounds(job,mode,start=START);engine.BOUNDS=bounds;result=None;failed=None
 try:
  engine.verify_runtime();result=engine.analyze(job) if mode=='analyze' else engine.export(job)
 except BaseException as e:failed={'type':type(e).__name__,'message':str(e)}
 finally:
  resources=bounds.close();write_json(job/(mode+'.resources.json'),{'resources':resources,'commands':bounds.commands})
 if failed:
  write_json(job/(mode+'.error.json'),failed);print(json.dumps(failed),flush=True);return 1
 result['resources']=resources;write_json(job/('analysis.json' if mode=='analyze' else 'export.json'),result)
 if mode=='export':
  report=read_json(job/'report.json');report['resources']=resources;report['commands']=bounds.commands;write_json(job/'report.json',report)
 print(json.dumps({'stage':mode,'complete':True,'resources':resources}),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
