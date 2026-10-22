"""Loopback-only, dependency-free review interface; one serial CPU worker."""
from common import *
import argparse, concurrent.futures, datetime, http.server, mimetypes, os, signal, socket, stat, subprocess, sys, threading, time, urllib.parse
ACTIVE={'queued','analyzing','exporting'}
DOWNLOADS={'original.mp4':'input.mp4','edited.mp4':'edited.mp4','control.mp4':'control.mp4','report.json':'report.json','recipe.json':'recipe.json','report.txt':'report.txt','frame-review.json':'frame-review.json'}
class Conflict(ValueError):pass
def bounded_regular_bytes(path,limit):
 # Nonblocking prevents a substituted FIFO from hanging before fstat.
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as source:
  st=os.fstat(source.fileno())
  if not stat.S_ISREG(st.st_mode) or st.st_size>limit:raise ValueError('Static review artifact is not a bounded regular file.')
  data=source.read(limit+1)
 if len(data)>limit:raise ValueError('Static review artifact grew beyond its byte limit.')
 return data

def verified_image_bytes(path,expected_sha256):
 data=bounded_regular_bytes(path,4*1024**2)
 if hashlib.sha256(data).hexdigest()!=expected_sha256:raise ValueError('Static review image changed before serving.')
 return data
class Manager:
 def __init__(self,root):
  self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.processes={};self.jobs={}
  for p in self.root.glob('*/job.json'):
   if re.fullmatch('[0-9a-f]{32}',p.parent.name):
    try:
     obj=read_json(p)
     if obj['status'] in ACTIVE:obj.update(status='failed',error='Server restarted before processing finished; no result accepted.');write_json(p,obj)
     self.jobs[p.parent.name]=obj
    except (ValueError,KeyError):pass
 def jobpath(self,jid):
  if not re.fullmatch('[0-9a-f]{32}',jid) or jid not in self.jobs:raise KeyError('Unknown job')
  return self.root/jid
 def save(self,jid):write_json(self.jobpath(jid)/'job.json',self.jobs[jid])
 def frame_review(self,jid):
  path=self.jobpath(jid);export=read_json(path/'export.json')
  expected=export.get('frame_review_sha256')
  if expected is None:return None
  file=path/'frame-review.json'
  raw=bounded_regular_bytes(file,1024**2)
  if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Static review manifest changed; comparison unavailable.')
  review=json.loads(raw);analysis=read_json(path/'analysis.json');approval=read_json(path/'approval.json')
  if review.get('schema')!='encoded-boundaries-v1' or review.get('input_sha256')!=analysis['input_sha256'] or review.get('prediction_sha256')!=analysis['prediction_sha256'] or review.get('recipe_sha256')!=approval['recipe_sha256'] or review.get('output_hashes')!=export['output_hashes']:raise ValueError('Static review source binding mismatch.')
  if sha(path/'input.mp4')!=review['input_sha256'] or any(sha(path/(name+'.mp4'))!=value for name,value in review['output_hashes'].items()):raise ValueError('Static review media changed; comparison unavailable.')
  # Bound the review timeline to the exact approved input, not a global profile maximum.
  recipe=approval.get('recipe')
  if not isinstance(recipe,dict) or hashlib.sha256(canonical(recipe)).hexdigest()!=approval.get('recipe_sha256'):raise ValueError('Static review approved recipe changed.')
  admitted=recipe.get('input_profile')
  if not isinstance(admitted,dict):raise ValueError('Static review admitted profile missing.')
  spec=media_profile([admitted.get('height'),admitted.get('width')],admitted.get('frames'))
  if admitted!=spec or analysis.get('input_profile')!=spec:raise ValueError('Static review admitted profile mismatch.')
  rows=review.get('rows',[])
  if len(rows)!=4:raise ValueError('Static review rows incomplete.')
  for row in rows:
   if type(row.get('frame')) is not int or not 0<=row['frame']<spec['frames'] or set(row.get('images',{}))!={'original','control','edited'}:raise ValueError('Invalid static review row.')
   for role,image in row['images'].items():
    filename=f"boundary-f{row['frame']:05d}-{role}.png";target=path/filename
    if image.get('filename')!=filename:raise ValueError('Static review image changed or unavailable.')
    verified_image_bytes(target,image.get('sha256'))
    image['url']=f'/api/jobs/{jid}/review/{filename}'
  return review
 def video_bytes(self,jid,name):
  # Hash the exact bounded response bytes; stale exports must not be downloaded.
  path=self.jobpath(jid);state=self.jobs[jid]['status']
  if name not in ('original.mp4','control.mp4','edited.mp4'):raise KeyError('Unknown video artifact')
  if state!='complete' and not(state=='declined' and name=='original.mp4'):raise Conflict('Artifact is not available in this job state.')
  if name=='original.mp4':
   expected=read_json(path/'analysis.json')['input_sha256'];filename='input.mp4';limit=MAX_INPUT
  else:
   expected=read_json(path/'export.json')['output_hashes'][name[:-4]];filename=name;limit=32*1024**2
  if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Video artifact has no valid source hash.')
  data=bounded_regular_bytes(path/filename,limit)
  if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Video artifact changed; download refused.')
  return data
 def view(self,jid):
  with self.lock:
   path=self.jobpath(jid);out=dict(self.jobs[jid]);out['candidates']=[]
   if (path/'analysis.json').is_file():
    analysis=read_json(path/'analysis.json');out.update({k:analysis[k] for k in ['input_sha256','prediction_sha256','message']});out['candidates']=[dict(c,overlay_url=f'/api/jobs/{jid}/preview/{c["id"]}.png') for c in analysis['candidates']]
   if out['status']=='complete' and (path/'export.json').is_file():out['summary']=read_json(path/'export.json')['summary']
   if out['status']=='complete' and (path/'export.json').is_file():
    try:out['frame_review']=self.frame_review(jid)
    except (ValueError,KeyError,OSError) as e:out['frame_review_error']=str(e)
   out['artifacts']={}
   if out['status']=='declined':out['artifacts']={'Original unchanged':f'/api/jobs/{jid}/download/original.mp4'}
   if out['status']=='complete':out['artifacts']={label:f'/api/jobs/{jid}/download/{name}' for label,name in [('Original input','original.mp4'),('Edited comparison','edited.mp4'),('Unchanged re-encode control','control.mp4'),('Report JSON','report.json'),('Recipe JSON','recipe.json'),('Readable report','report.txt')]}
   return out
 def create(self,name,data):
  if not 0<len(data)<=MAX_INPUT:raise ValueError('Input must be between 1 byte and 8 MiB.')
  with self.lock:
   if len(self.jobs)>=8:raise Conflict('Eight-job development limit reached. Retain/review current jobs before starting a fresh data directory.')
   if sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())+len(data)>256*1024**2:raise Conflict('Application disk limit reached.')
   jid=secrets.token_hex(16);p=self.root/jid;p.mkdir(mode=0o700);(p/'input.mp4').write_bytes(data);self.jobs[jid]={'id':jid,'status':'queued','input_name':safe_name(name),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};self.save(jid);self.pool.submit(self.run,jid,'analyze');return self.view(jid)
 def run(self,jid,mode):
  p=None;log=None;failure=None;rc=None;path=self.root/jid
  try:
   with self.lock:
    path=self.jobpath(jid)
    if self.jobs[jid]['status']=='cancelled':return
    self.jobs[jid]['status']='analyzing' if mode=='analyze' else 'exporting';self.save(jid)
    log=(path/(mode+'.worker.log')).open('wb')
    p=subprocess.Popen([sys.executable,str(APP/'worker.py'),mode,str(path)],cwd=APP,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);self.processes[jid]=p
   try:rc=p.wait(timeout=130 if mode=='analyze' else 250)
   except subprocess.TimeoutExpired:
    self.stop_process(p);failure='Worker exceeded its outer wall-time limit; no result accepted.'
   err=path/(mode+'.error.json')
   if err.exists():failure=read_json(err).get('message','Worker failed.')
   elif rc!=0:failure=failure or 'Worker stopped or exceeded its limit; no result accepted.'
   elif not (path/('analysis.json' if mode=='analyze' else 'export.json')).is_file():failure='Worker returned without the required result; no result accepted.'
  except BaseException as e:
   failure='Worker orchestration failed: '+type(e).__name__+': '+str(e)
   if p is not None:
    try:self.stop_process(p)
    except BaseException:pass
  finally:
   if p is not None:
    try:self.stop_process(p)
    except BaseException as e:failure=failure or 'Worker group cleanup failed: '+str(e)
   if log is not None:log.close()
   with self.lock:
    self.processes.pop(jid,None)
    if jid in self.jobs and self.jobs[jid]['status']!='cancelled':
     if failure:self.jobs[jid].update(status='failed',error=failure)
     else:self.jobs[jid]['status']='review' if mode=='analyze' else 'complete'
    if jid in self.jobs:
     try:self.save(jid)
     except OSError as e:self.jobs[jid].update(status='failed',error='Cannot persist job state: '+str(e))
 @staticmethod
 def stop_process(p):
  # The process owns a new session/group. Descendants can remain after its
  # leader exits, so poll() alone cannot decide whether cleanup is needed.
  try:os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError:return
  try:p.wait(timeout=2)
  except subprocess.TimeoutExpired:pass
  # A bounded grace period also covers children whose leader already exited.
  deadline=time.monotonic()+.25
  while time.monotonic()<deadline:
   try:os.killpg(p.pid,0)
   except ProcessLookupError:return
   time.sleep(.025)
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:raise RuntimeError('Worker leader did not terminate')
 def plan(self,jid,body):
  with self.lock:
   path=self.jobpath(jid)
   if self.jobs[jid]['status']!='review':raise Conflict('This job is not awaiting review.')
   a=read_json(path/'analysis.json');pred=read_json(path/'prediction.json');cid=body.get('candidate_id')
   candidate=next((c for c in a['candidates'] if c['id']==cid),None)
   if not candidate:raise ValueError('Choose an existing candidate.')
   if body.get('prediction_sha256')!=a['prediction_sha256'] or sha(path/'prediction.json')!=a['prediction_sha256'] or sha(path/'input.mp4')!=a['input_sha256']:raise Conflict('Input/prediction changed; approval invalidated.')
   if len(read_json(path/'source.probe.json')['metadata']['streams'])>1 and body.get('export_mode','legacy')!='periodic-local-retime-v2':raise ValueError('Audio is preserved only by Slow periodic decoration. Choose that action; legacy actions will not remove your audio.')
   component=pred['components'][int(cid)];base=proposed_recipe(a['input_sha256'],a['prediction_sha256'],cid,component,input_profile=a['input_profile'])
   if hashlib.sha256(canonical(base)).hexdigest()!=candidate['recipe_sha256']:raise Conflict('Implementation changed; analyze again before reviewing.')
   recipe=proposed_recipe(a['input_sha256'],a['prediction_sha256'],cid,component,body.get('protected_regions',[]),body.get('export_mode','legacy'),input_profile=a['input_profile'])
   return {'candidate_id':cid,'prediction_sha256':a['prediction_sha256'],'export_mode':recipe['export_mode'],'protected_regions':recipe['protected_regions'],'recipe':recipe,'recipe_sha256':hashlib.sha256(canonical(recipe)).hexdigest()}
 def approve(self,jid,body):
  with self.lock:
   if body.get('approve') is not True:raise ValueError('Explicit approval is required.')
   plan=self.plan(jid,body);path=self.jobpath(jid)
   if body.get('recipe_sha256')!=plan['recipe_sha256']:raise Conflict('Edit or protected areas changed; review the plan again.')
   approval=dict(plan,approve=True,approved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
   a=read_json(path/'analysis.json');pred=read_json(path/'prediction.json');validate_approval(approval,a['input_sha256'],a['prediction_sha256'],pred['components'][int(plan['candidate_id'])],a['input_profile'])
   write_json(path/'approval.json',approval);self.jobs[jid]['status']='queued';self.save(jid);self.pool.submit(self.run,jid,'export');return self.view(jid)
 def decline(self,jid):
  with self.lock:
   self.jobpath(jid)
   if self.jobs[jid]['status']!='review':raise Conflict('Only a reviewed job can be left unchanged.')
   self.jobs[jid]['status']='declined';self.save(jid);return self.view(jid)
 def cancel(self,jid):
  with self.lock:
   self.jobpath(jid)
   if self.jobs[jid]['status'] not in ACTIVE:raise Conflict('Job is not active.')
   self.jobs[jid]['status']='cancelled';p=self.processes.get(jid)
   try:self.save(jid)
   except OSError as e:self.jobs[jid]['error']='Cancellation requested; could not persist state: '+str(e)
  if p:
   try:self.stop_process(p)
   except BaseException as e:
    with self.lock:self.jobs[jid].update(status='failed',error='Cancellation could not confirm worker termination: '+str(e))
  return self.view(jid)
 def close(self):
  errors=[]
  with self.lock:
   processes=list(self.processes.values())
   for jid,obj in self.jobs.items():
    if obj['status'] in ACTIVE:
     obj['status']='cancelled'
     try:self.save(jid)
     except OSError as e:errors.append('State persistence: '+str(e))
  try:
   for p in processes:
    try:self.stop_process(p)
    except BaseException as e:errors.append('Process termination: '+str(e))
  finally:self.pool.shutdown(wait=True,cancel_futures=True)
  self.cleanup_errors=errors
  return errors

class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def setup(self):super().setup();self.connection.settimeout(10)
 def headers_safe(self,ctype,length,attachment=None):
  self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(length));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
  if attachment:self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
  self.end_headers()
 def respond(self,code,obj):
  data=json.dumps(obj,allow_nan=False).encode();self.send_response(code);self.headers_safe('application/json',len(data));self.wfile.write(data)
 def secure(self,post=False):
  if self.headers.get('Host') not in self.server.allowed_hosts:raise ValueError('Only the local loopback host is admitted.')
  origin=self.headers.get('Origin')
  if origin and origin not in self.server.allowed_origins:raise ValueError('Cross-origin requests are refused.')
  if post and not secrets.compare_digest(self.headers.get('X-App-Token',''),self.server.csrf_token):raise PermissionError('Missing or stale application token.')
 def body(self,maximum):
  if self.headers.get('Transfer-Encoding'):raise ValueError('Transfer encoding is unsupported.')
  try:n=int(self.headers.get('Content-Length','-1'))
  except ValueError:raise ValueError('Content-Length required.')
  if n<0 or n>maximum:raise ValueError('Request body exceeds the supported limit.')
  value=self.rfile.read(n)
  if len(value)!=n:raise ValueError('Incomplete request body.')
  return value
 def file(self,path,attachment=None):
  if not path.is_file():raise KeyError('File not available')
  data=path.read_bytes();self.send_response(200);self.headers_safe(mimetypes.guess_type(path.name)[0] or 'application/octet-stream',len(data),attachment);self.wfile.write(data)
 def verified_image(self,path,expected_sha256):
  # Verify the exact response buffer, rather than validating then reopening.
  # No-follow and size checks keep the image route narrowly scoped.
  data=verified_image_bytes(path,expected_sha256)
  self.send_response(200);self.headers_safe('image/png',len(data));self.wfile.write(data)
 def verified_video(self,jid,name):
  data=self.server.manager.video_bytes(jid,name)
  self.send_response(200);self.headers_safe('video/mp4',len(data),name);self.wfile.write(data)
 def handle_error(self,e):
  code=403 if isinstance(e,PermissionError) else 404 if isinstance(e,KeyError) else 409 if isinstance(e,Conflict) else 400
  self.close_connection=True
  try:self.respond(code,{'error':str(e)})
  except (BrokenPipeError,ConnectionResetError):pass
 def do_GET(self):
  try:
   self.secure();path=urllib.parse.urlsplit(self.path).path
   if path=='/':return self.file(APP/'static/index.html')
   if path in ['/static/app.js','/static/styles.css']:return self.file(APP/path.lstrip('/'))
   if path=='/api/profile':return self.respond(200,{'profile':{'id':PROFILE_ID,'width':W,'height':H,'fps':FPS,'frames':N,'duration_seconds':3,'codec':'H.264','color':'limited-range tagged BT.709 YUV420, square pixels, left chroma','audio':'optional AAC-LC mono 48 kHz; zero start and exact video duration; copy-only, local retiming only','edit':EDIT},'limits':{'max_input_bytes':MAX_INPUT,'max_jobs':8,'active_cpu_workers':1,'worker_rss_bytes':512*1024**2},'duration_contract':DURATION_CONTRACT,'supported_profiles':MEDIA_PROFILES,'limitations':LIMITATIONS,'csrf_token':self.server.csrf_token})
   m=re.fullmatch(r'/api/jobs/([0-9a-f]{32})(?:/(preview|download|review)/([^/]+))?',path)
   if not m:raise KeyError('Not found')
   jid,kind,name=m.groups();job=self.server.manager.jobpath(jid)
   if kind is None:return self.respond(200,self.server.manager.view(jid))
   if kind=='preview' and re.fullmatch(r'[0-9]+\.png',name):return self.file(job/('candidate-'+name))
   if kind=='review' and re.fullmatch(r'boundary-f[0-9]{5}-(original|control|edited)\.png',name):
    if self.server.manager.jobs[jid]['status']!='complete':raise Conflict('Static result comparison is not complete.')
    review=self.server.manager.frame_review(jid)
    image=next((image for row in review['rows'] for image in row['images'].values() if image['filename']==name),None) if review is not None else None
    if image is None:raise KeyError('Static comparison image unavailable')
    return self.verified_image(job/name,image['sha256'])
   if kind=='download' and name in DOWNLOADS:
    state=self.server.manager.view(jid)['status']
    if state!='complete' and not(state=='declined' and name=='original.mp4'):raise Conflict('Artifact is not available in this job state.')
    if name in ('original.mp4','control.mp4','edited.mp4'):return self.verified_video(jid,name)
    return self.file(job/DOWNLOADS[name],name)
   raise KeyError('Not found')
  except (ValueError,KeyError,PermissionError,OSError) as e:self.handle_error(e)
 def do_POST(self):
  try:
   self.secure(True);path=urllib.parse.urlsplit(self.path).path
   if path=='/api/jobs':return self.respond(202,self.server.manager.create(urllib.parse.unquote(self.headers.get('X-Filename','input.mp4')),self.body(MAX_INPUT)))
   m=re.fullmatch(r'/api/jobs/([0-9a-f]{32})/(approve|decline|cancel|plan)',path)
   if not m:raise KeyError('Not found')
   jid,action=m.groups();body=json.loads(self.body(8192) or b'{}')
   if not isinstance(body,dict):raise ValueError('JSON object required')
   result=getattr(self.server.manager,action)(jid,body) if action in ('approve','plan') else getattr(self.server.manager,action)(jid)
   return self.respond(202 if action=='approve' else 200,result)
  except (ValueError,KeyError,PermissionError,OSError) as e:self.handle_error(e)
 def log_message(self,fmt,*args):pass

def make_server(port=8765,data_dir=None):
 manager=Manager(data_dir or APP/'jobs')
 try:server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
 except BaseException:manager.close();raise
 server.daemon_threads=True;server.manager=manager;server.csrf_token=secrets.token_hex(32)
 port=server.server_address[1];server.allowed_hosts={f'127.0.0.1:{port}',f'localhost:{port}'};server.allowed_origins={'http://'+v for v in server.allowed_hosts};return server
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--data-dir',type=Path,default=APP/'jobs');args=parser.parse_args();server=make_server(args.port,args.data_dir)
 print(f'Local creator review: http://127.0.0.1:{server.server_address[1]} (no autoplay; Ctrl+C stops workers)',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  try:
   errors=server.manager.close()
   if errors:print('Cleanup warnings: '+json.dumps(errors),flush=True)
  finally:server.server_close()
