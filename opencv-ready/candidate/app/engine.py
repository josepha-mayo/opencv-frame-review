"""Bounded original CPU processing, isolated from the local web process."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']: os.environ[k]='1'
import ast, hashlib, json, math, pathlib, resource, signal, subprocess, sys, threading, time
from common import *
SITE=APP.parent/'opencv-inset-feature-check/site'
if SITE.is_dir(): sys.path.insert(0,str(SITE))
import numpy as np
import cv2
import frozen_algorithms as alg
from protected_regions import RegionMeasure
from review_frames import ReviewFrames
cv2.setNumThreads(1)
# Frozen float32 bit patterns of the original development-profile table.
# Avoid CPU-dispatched power differences; this is the existing gamma-2.4
# analysis convention, not a new color standard or changed threshold.
LUT=np.array([0, 903935698, 924085189, 935616457, 943970234, 950487396, 956403458, 960204591, 964769087, 967535336, 970767474, 973782052, 975893539, 978266405, 980909163, 982648536, 984251825, 986001750, 987901913, 989905767, 991011244, 992196887, 993464278, 994814950, 996250400, 997772082, 998812884, 999662071, 1000556454, 1001496697, 1002483447, 1003517339, 1004598998, 1005729031, 1006770499, 1007384783, 1008024139, 1008688849, 1009379194, 1010095446, 1010837879, 1011606758, 1012402345, 1013224900, 1014074677, 1014951927, 1015439234, 1015905704, 1016386277, 1016881075, 1017390213, 1017913810, 1018451979, 1019004833, 1019572487, 1020155051, 1020752634, 1021365345, 1021993291, 1022636579, 1023295315, 1023689889, 1024034860, 1024387709, 1024748489, 1025117246, 1025494032, 1025878896, 1026271887, 1026673053, 1027082441, 1027500100, 1027926076, 1028360415, 1028803166, 1029254372, 1029714080, 1030182335, 1030659182, 1031144664, 1031638827, 1031970249, 1032226076, 1032486309, 1032750969, 1033020075, 1033293652, 1033571718, 1033854295, 1034141404, 1034433066, 1034729299, 1035030125, 1035335564, 1035645635, 1035960360, 1036279757, 1036603845, 1036932645, 1037266177, 1037604458, 1037947509, 1038295348, 1038647994, 1039005466, 1039367782, 1039734962, 1040107024, 1040335689, 1040526629, 1040720037, 1040915923, 1041114295, 1041315162, 1041518533, 1041724417, 1041932823, 1042143760, 1042357236, 1042573259, 1042791840, 1043012985, 1043236703, 1043463004, 1043691895, 1043923385, 1044157482, 1044394196, 1044633534, 1044875503, 1045120112, 1045367370, 1045617284, 1045869864, 1046125116, 1046383049, 1046643670, 1046906988, 1047173011, 1047441746, 1047713202, 1047987386, 1048264306, 1048543970, 1048701192, 1048843779, 1048987750, 1049133107, 1049279856, 1049428000, 1049577541, 1049728486, 1049880835, 1050034595, 1050189768, 1050346359, 1050504370, 1050663805, 1050824669, 1050986964, 1051150696, 1051315865, 1051482478, 1051650536, 1051820043, 1051991005, 1052163422, 1052337300, 1052512642, 1052689452, 1052867732, 1053047486, 1053228718, 1053411431, 1053595629, 1053781314, 1053968492, 1054157164, 1054347334, 1054539006, 1054732183, 1054926868, 1055123065, 1055320777, 1055520008, 1055720760, 1055923037, 1056126842, 1056332178, 1056539050, 1056747460, 1056957411, 1057066757, 1057173279, 1057280576, 1057388650, 1057497503, 1057607136, 1057717551, 1057828751, 1057940734, 1058053505, 1058167063, 1058281411, 1058396551, 1058512483, 1058629211, 1058746734, 1058865054, 1058984174, 1059104094, 1059224817, 1059346343, 1059468675, 1059591813, 1059715759, 1059840515, 1059966082, 1060092461, 1060219655, 1060347665, 1060476492, 1060606138, 1060736604, 1060867891, 1061000002, 1061132938, 1061266699, 1061401288, 1061536705, 1061672953, 1061810033, 1061947946, 1062086694, 1062226279, 1062366701, 1062507962, 1062650063, 1062793007, 1062936793, 1063081425, 1063226902, 1063373227, 1063520401, 1063668426, 1063817302, 1063967031, 1064117615, 1064269055, 1064421352, 1064574508, 1064728524, 1064883401, 1065039142, 1065195746, 1065353216],dtype=np.uint32).view(np.float32)
WEIGHTS=np.array([[.2126,.7152,.0722]],np.float32)
DECODE_FILTER='scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=tv:out_range=pc:in_chroma_loc=left:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact+full_chroma_int,format=rgb24'
ENCODE_FILTER='scale=in_color_matrix=bt709:out_color_matrix=bt709:in_range=pc:out_range=tv:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709'
INPUT_FLAGS=['-protocol_whitelist','file,pipe','-f','mov','-enable_drefs','0','-use_absolute_path','0']
BOUNDS=None
CURRENT_PROFILE=media_profile([H,W])
class Bounds:
 def __init__(self,job,mode,start=None):
  self.job=Path(job);self.active={};self.lock=threading.Lock();self.stop=None;self.done=threading.Event();self.start=time.monotonic() if start is None else start;self.peak=0;self.commands=[]
  self.mode=mode;self.cpu_cap=30 if mode=='analyze' else 60;self.wall_cap=90 if mode=='analyze' else 180;self.rss_cap=256*1024**2;self.disk_cap=16*1024**2
  resource.setrlimit(resource.RLIMIT_CPU,(self.cpu_cap,121));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,32*1024**2));resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
  if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
  try:os.nice(10)
  except OSError:pass
  for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGXCPU]:signal.signal(sig,self.signal)
  signal.alarm(self.wall_cap);threading.Thread(target=self.watch,daemon=True).start()
 def configure(self,spec):
  large=spec['width']==640
  self.cpu_cap=(60 if self.mode=='analyze' else 120) if large else (30 if self.mode=='analyze' else 60)
  self.wall_cap=(120 if self.mode=='analyze' else 240) if large else (90 if self.mode=='analyze' else 180)
  self.rss_cap=((512 if large else 384) if spec['frames']>180 else (384 if large else 256))*1024**2;self.disk_cap=(32 if large else 16)*1024**2
  resource.setrlimit(resource.RLIMIT_CPU,(self.cpu_cap,self.cpu_cap+1));resource.setrlimit(resource.RLIMIT_FSIZE,(self.disk_cap,self.disk_cap))
  signal.alarm(max(1,int(self.wall_cap-(time.monotonic()-self.start))));self.guard()
 def signal(self,n,f):
  self.stop='Worker stopped by signal '+str(n);self.kill();raise RuntimeError(self.stop)
 def read_proc(self,pid):
  try:
   st=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();cpu=(int(st[11])+int(st[12]))/os.sysconf('SC_CLK_TCK')
   rss=next((int(x.split()[1])*1024 for x in Path(f'/proc/{pid}/status').read_text().splitlines() if x.startswith('VmRSS:')),0);return cpu,rss
  except (FileNotFoundError,ProcessLookupError):return 0,0
 def snapshot(self):
  own=resource.getrusage(resource.RUSAGE_SELF);dead=resource.getrusage(resource.RUSAGE_CHILDREN)
  with self.lock:children=[self.read_proc(pid) for pid in self.active]
  return {'cpu_seconds':own.ru_utime+own.ru_stime+dead.ru_utime+dead.ru_stime+sum(x[0] for x in children),'rss_bytes':self.read_proc(os.getpid())[1]+sum(x[1] for x in children),'wall_seconds':time.monotonic()-self.start}
 def guard(self):
  r=self.snapshot();self.peak=max(self.peak,r['rss_bytes'])
  if r['cpu_seconds']>self.cpu_cap:self.stop='Aggregate CPU limit exceeded'
  if r['rss_bytes']>self.rss_cap:self.stop='Aggregate RSS limit exceeded'
  if r['wall_seconds']>self.wall_cap:self.stop='Wall-time limit exceeded'
  if sum(p.stat().st_size for p in self.job.iterdir() if p.is_file())>self.disk_cap:self.stop='Job disk limit exceeded'
  if self.stop:self.kill();raise RuntimeError(self.stop)
 def kill(self):
  with self.lock:ps=list(self.active.values())
  for p in ps:
   if p.poll() is None:
    try:p.kill()
    except ProcessLookupError:pass
 def watch(self):
  while not self.done.wait(.1):
   try:self.guard()
   except BaseException:self.kill();return
 def begin(self,args,label,writing=False):
  self.guard();log=(self.job/(label+'.stderr.log')).open('wb');p=subprocess.Popen(args,cwd=self.job,stdin=subprocess.PIPE if writing else subprocess.DEVNULL,stdout=subprocess.DEVNULL if writing else subprocess.PIPE,stderr=log)
  with self.lock:self.active[p.pid]=p
  self.commands.append(args);return p,log
 def end(self,p,log):
  try:rc=p.wait(timeout=5)
  except BaseException:p.kill();p.wait();raise
  finally:
   with self.lock:self.active.pop(p.pid,None)
   log.close()
  self.guard()
  if rc:raise RuntimeError('Media subprocess failed (exit '+str(rc)+'); bounded stderr retained.')
 def abort(self,p,log):
  if p.poll() is None:p.kill()
  p.wait()
  with self.lock:self.active.pop(p.pid,None)
  log.close()
 def close(self):
  self.done.set();self.kill()
  with self.lock:ps=list(self.active.values())
  for p in ps:
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:pass
  signal.alarm(0);r=self.snapshot();r['peak_sampled_aggregate_rss_bytes']=self.peak;r['limits']={'cpu_seconds':self.cpu_cap,'wall_seconds':self.wall_cap,'rss_bytes':self.rss_cap,'job_bytes':self.disk_cap,'cpu_affinity':list(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None};return r

def guard():
 if BOUNDS:BOUNDS.guard()
def packed_mask(a):
 v=a.astype(bool).ravel();edge=np.diff(np.concatenate(([False],v,[False])).astype(np.int8));s=np.flatnonzero(edge==1);e=np.flatnonzero(edge==-1);return [[int(x),int(y-x)] for x,y in zip(s,e)]
def unpack_mask(rle,shape):
 if shape!=[H,W]:raise ValueError('Invalid mask dimensions')
 a=np.zeros(H*W,np.uint8);end=0
 for start,n in rle:
  if type(start) is not int or type(n) is not int or n<=0 or start<end or start+n>H*W:raise ValueError('Invalid mask run')
  a[start:start+n]=255;end=start+n
 if not np.any(a):raise ValueError('Empty selected mask')
 return a.reshape(H,W)
def verify_runtime():
 if np.__version__!=PROFILE['versions']['numpy'] or cv2.__version__!=PROFILE['versions']['opencv']:raise RuntimeError('Pinned NumPy/OpenCV versions required.')
 for name in ['ffmpeg','ffprobe']:
  if sha('/usr/bin/'+name)!=PROFILE['versions'][name+'_sha256']:raise RuntimeError('Pinned '+name+' changed; transport revalidation required.')
 tree=ast.parse((APP/'frozen_algorithms.py').read_text())
 for name,key in [('detector','detector_ast_sha256'),('temporal','temporal_ast_sha256')]:
  node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
  if hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()!=PROFILE[key]:raise RuntimeError('Frozen '+name+' AST changed.')
 alg.np=np;alg.cv2=cv2;alg.P=PROFILE;alg.LUT=LUT;alg.WEIGHTS=WEIGHTS;alg.guard=guard;alg.packed_mask=packed_mask

def capture_json(args,label):
 p,log=BOUNDS.begin(args,label)
 try:
  b=p.stdout.read(131073)
  if len(b)>131072:raise ValueError('Metadata output exceeds limit')
  p.stdout.close();BOUNDS.end(p,log);return json.loads(b)
 except BaseException:
  if not log.closed:BOUNDS.abort(p,log)
  raise

def probe(path,label,output_codec=None):
 base=['/usr/bin/ffprobe','-v','error','-threads','1']+INPUT_FLAGS
 meta=capture_json(base+['-show_streams','-show_format','-of','json',str(path)],label+'_meta')
 if output_codec is not None:
  if not meta.get('streams') or meta['streams'][0].get('codec_name')!=output_codec:raise ValueError('Unexpected native output codec')
  admitted=json.loads(json.dumps(meta));admitted['streams'][0]['codec_name']='h264';st=validate_probe(admitted)
 else:st=validate_probe(meta)
 if len(meta['streams'])==2:
  from audio_preserve import validate_presentation
  validate_presentation(path,media_profile([st['height'],st['width']],int(st['nb_frames']))['duration_seconds'])
 global W,H,N,CURRENT_PROFILE
 spec=media_profile([st['height'],st['width']],int(st['nb_frames']))
 if path.stat().st_size>spec['max_input_bytes']:raise ValueError('Input exceeds its profile byte limit')
 if label!='source' and label!='export_source' and spec!=CURRENT_PROFILE:raise ValueError('Encoded output changed the media profile')
 CURRENT_PROFILE=spec;W,H,N=spec['width'],spec['height'],spec['frames'];BOUNDS.configure(spec)
 frames=capture_json(base+['-select_streams','v:0','-read_intervals','%+#'+str(N+1),'-show_frames','-show_entries','frame=best_effort_timestamp','-of','json',str(path)],label+'_pts')
 ts=validate_frames(frames,N);write_json(BOUNDS.job/(label+'.probe.json'),{'metadata':meta,'frames':frames});return ts

def decode(path,label):
 args=['/usr/bin/ffmpeg','-hide_banner','-nostdin','-loglevel','error','-threads','1','-filter_threads','1','-filter_complex_threads','1']+INPUT_FLAGS+['-i',str(path),'-map','0:v:0','-an','-sn','-dn','-vf',DECODE_FILTER,'-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','-threads','1','pipe:1']
 p,log=BOUNDS.begin(args,label+'_decode');size=W*H*3
 try:
  for _ in range(N):
   b=p.stdout.read(size)
   if len(b)!=size:raise ValueError('Decoded frame count/size mismatch')
   guard();yield np.frombuffer(b,np.uint8).reshape(H,W,3)
  if p.stdout.read(1):raise ValueError('More decoded frames than admitted')
  p.stdout.close();BOUNDS.end(p,log)
 except BaseException:
  if not log.closed:BOUNDS.abort(p,log)
  raise

def encode(path,frames,label):
 args=['/usr/bin/ffmpeg','-hide_banner','-nostdin','-loglevel','error','-n','-threads','1','-filter_threads','1','-filter_complex_threads','1','-f','rawvideo','-pixel_format','rgb24','-video_size',str(W)+'x'+str(H),'-framerate','30','-i','pipe:0','-vf',ENCODE_FILTER,'-an','-c:v','libx264','-preset','veryfast','-qp','18','-aq-mode','0','-psy','0','-rc-lookahead','0','-bf','0','-g','30','-keyint_min','30','-sc_threshold','0','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-chroma_sample_location','left','-fps_mode','passthrough','-video_track_timescale','15360','-frames:v',str(N),str(path)]
 p,log=BOUNDS.begin(args,label+'_encode',True)
 try:
  count=0
  for a in frames:p.stdin.write(a.tobytes());count+=1;guard()
  if count!=N:raise ValueError('Encode frame count mismatch')
  p.stdin.close();BOUNDS.end(p,log)
 except BaseException:
  if not log.closed:BOUNDS.abort(p,log)
  raise

def analyze(job):
 source=job/'input.mp4';digest=sha(source)
 if not 0<source.stat().st_size<=MAX_INPUT:raise ValueError('Input size outside profile')
 ts=probe(source,'source');prediction=alg.detector(decode(source,'source'),ts)
 write_json(job/'prediction.json',prediction);prediction_sha=sha(job/'prediction.json')
 if len(prediction['components'])>16:raise ValueError('More than 16 regions; this review interface cannot admit the clip.')
 needed={min(N-1,round(c['first_candidate_timestamp']*FPS)) for c in prediction['components']};frames={}
 if needed:
  for j,a in enumerate(decode(source,'previews')):
   if j in needed:frames[j]=a
 out=[]
 for i,c in enumerate(prediction['components']):
  mask=unpack_mask(c['mask_rle'],c['mask_shape']);lo,hi=[round(x*FPS) for x in c['interval']];frame=min(N-1,round(c['first_candidate_timestamp']*FPS))
  image=frames[frame].copy();tint=image.copy();tint[mask!=0]=[30,220,150];image=cv2.addWeighted(image,.65,tint,.35,0);x,y,w,h=c['bbox'];cv2.rectangle(image,(x,y),(x+w-1,y+h-1),(250,170,30),1)
  if not cv2.imwrite(str(job/f'candidate-{i}.png'),cv2.cvtColor(image,cv2.COLOR_RGB2BGR)):raise RuntimeError('Preview write failed')
  recipe=proposed_recipe(digest,prediction_sha,str(i),c,input_profile=CURRENT_PROFILE)
  out.append({'id':str(i),'bbox':c['bbox'],'interval_frames':[lo,hi],'interval_seconds':c['interval'],'pixels':c['area'],'preview_frame':frame,'recipe_sha256':hashlib.sha256(canonical(recipe)).hexdigest()})
 return {'input_profile':CURRENT_PROFILE,'input_sha256':digest,'prediction_sha256':prediction_sha,'candidates':out,'scope':LIMITATIONS,'message':'Review a candidate before any edit.' if out else 'This limited profile found no candidate. No safety or compliance conclusion follows.'}

def source_index(t,lo,hi):return lo+10*((t-lo)//10) if lo<=t<=hi else t
def edited_frames(source,mask,lo,hi):
 outside=mask==0
 for t,a in enumerate(source):
  b=a.copy()
  if lo<=t<=hi:b[mask!=0]=source[source_index(t,lo,hi)][mask!=0]
  if not np.array_equal(b[outside],a[outside]) or (not lo<=t<=hi and not np.array_equal(a,b)):raise RuntimeError('Pre-encode edit exceeded approved scope')
  yield b

def hist_summary(hist):
 total=int(hist.sum());nz=np.flatnonzero(hist)
 if not total:return {'mean_rgb_code_error':None,'p99_rgb_code_error':None,'max_rgb_code_error':None,'channel_samples':0}
 return {'mean_rgb_code_error':float(np.dot(hist,np.arange(256))/total),'p99_rgb_code_error':int(np.searchsorted(np.cumsum(hist),math.ceil(.99*total))),'max_rgb_code_error':int(nz[-1]) if len(nz) else 0,'channel_samples':total}

def measure(source,control,edited,mask,lo,hi,review=None,protected_regions=None):
 protected=RegionMeasure(protected_regions or [],np,cv2)
 outside=cv2.bitwise_not(mask);hist=np.zeros(256,np.int64);maxintended=0.;perframe=[]
 for t,a in enumerate(source):
  b=next(control);c=next(edited)
  if review is not None:review.capture(t,a,b,c)
  protected.add(b,c)
  d=cv2.absdiff(b,c)
  for ch in range(3):hist+=cv2.calcHist([d],[ch],outside,[256],[0,256]).ravel().astype(np.int64)
  intended=sum(cv2.mean(cv2.absdiff(c,source[source_index(t,lo,hi)]),mask=mask)[:3])/3;maxintended=max(maxintended,intended);perframe.append({'frame':t,'source_index':source_index(t,lo,hi),'selected_intended_mean_rgb_error':intended});guard()
 for stream in [control,edited]:
  try:next(stream)
  except StopIteration:pass
  else:raise RuntimeError('Unexpected extra measurement frame')
 return {'protected_content':protected.result(),'all_outside_histogram':hist.tolist(),'all_outside':hist_summary(hist),'selected_intended_max_perframe_mean_rgb_error':maxintended,'perframe':perframe}

def trace(frames,mask,lo,hi):
 v=[]
 for a in frames:v.append(float(cv2.mean(cv2.transform(cv2.LUT(a,LUT),WEIGHTS),mask=mask)[0]));guard()
 r=alg.temporal(np.tile(v,3),np.arange(N*3));events=[]
 for e in r['events']:
  if N<=e['frame']<N*2:events.append(dict(e,frame_in_cycle=e['frame']-N))
 return {'trace':v,'middle_cycle_max_count':max(r['counts'][N:N*2]),'middle_cycle_counts':r['counts'][N:N*2],'middle_cycle_events':events,'seam_absolute_delta':abs(v[0]-v[-1]),'entry_delta':abs(v[lo]-v[lo-1]) if lo else abs(v[0]-v[-1]),'exit_delta':abs(v[hi+1]-v[hi]) if hi+1<N else abs(v[0]-v[-1])}

def export(job):
 sourcepath=job/'input.mp4';analysis=read_json(job/'analysis.json');prediction=read_json(job/'prediction.json');approval=read_json(job/'approval.json')
 current_input=sha(sourcepath);current_prediction=sha(job/'prediction.json')
 if current_input!=analysis['input_sha256'] or current_prediction!=analysis['prediction_sha256']:raise ValueError('Input or prediction changed after analysis; approval invalidated.')
 cid=approval.get('candidate_id')
 if not isinstance(cid,str) or not cid.isdigit() or int(cid)>=len(prediction['components']):raise ValueError('Unknown approved candidate')
 ts=probe(sourcepath,'export_source')
 if analysis['input_profile']!=CURRENT_PROFILE:raise ValueError('Admitted profile changed after analysis')
 component=prediction['components'][int(cid)];recipe=validate_approval(approval,current_input,current_prediction,component,CURRENT_PROFILE);lo,hi=recipe['frame_bounds_inclusive'];mask=unpack_mask(component['mask_rle'],component['mask_shape'])
 if cv2.countNonZero(mask)==W*H:raise ValueError('Full-frame edits have no outside preservation evidence and are unsupported in this local-edit profile.')
 if recipe.get('export_mode')=='periodic-local-retime-v2':
  import retime_export
  return retime_export.export(sys.modules[__name__],job,sourcepath,recipe,component,approval,current_input,current_prediction,ts)
 if len(read_json(job/'export_source.probe.json')['metadata']['streams'])>1:raise ValueError('Audio preservation is supported only in local periodic retiming. Choose that action; legacy actions will not remove your audio.')
 if recipe.get('export_mode')=='native-yuv-whole-clip-v9':
  import native_yuv
  return native_yuv.export(sys.modules[__name__],job,sourcepath,recipe,component,approval,current_input,current_prediction,ts)
 source=list(decode(sourcepath,'export_source'))
 encode(job/'control.mp4',iter(source),'control');encode(job/'edited.mp4',edited_frames(source,mask,lo,hi),'edited')
 for name in ['control','edited']:
  if probe(job/(name+'.mp4'),name)!=ts:raise ValueError('Encoded timestamps changed')
 preds={}
 for name in ['control','edited']:preds[name]=alg.detector(decode(job/(name+'.mp4'),name+'_detect'),ts);write_json(job/(name+'.prediction.json'),preds[name])
 output_hashes={n:sha(job/(n+'.mp4')) for n in ['control','edited']}
 review=ReviewFrames(job,mask,lo,hi,ts,guard)
 quality=measure(source,decode(job/'control.mp4','control_measure'),decode(job/'edited.mp4','edited_measure'),mask,lo,hi,review,recipe['protected_regions'])
 traces={'source':trace(source,mask,lo,hi)}
 for name in ['control','edited']:traces[name]=trace(decode(job/(name+'.mp4'),name+'_trace'),mask,lo,hi)
 def overlap(c):
  other=unpack_mask(c['mask_rle'],c['mask_shape']);return cv2.countNonZero(cv2.bitwise_and(mask,other))/cv2.countNonZero(cv2.bitwise_or(mask,other))
 best=max([overlap(c) for c in preds['control']['components']],default=0.)
 checks={'output_metadata_and_timing':True,'preencode_scope_exact':True,'control_support_iou_at_least_0_8':best>=.8,'selected_rolling_count_at_most_6':traces['edited']['middle_cycle_max_count']<=6,'outside_mean_at_most_1':quality['all_outside']['mean_rgb_code_error']<=1,'outside_p99_at_most_3':quality['all_outside']['p99_rgb_code_error']<=3,'selected_intended_mean_at_most_2':quality['selected_intended_max_perframe_mean_rgb_error']<=2}
 if quality['protected_content']['declared']:checks['creator_protected_content']=quality['protected_content']['passed']
 warnings=['Passing these numeric checks does not establish safety, compliance or artistic acceptance.','Outside-mask maximum error is reported even when mean and p99 pass.','Boundary and loop values are mean-luminance traces of the selected region; they are not comprehensive spatial flash assessment.']
 boundary={key:{'control_delta':traces['control'][field],'edited_delta':traces['edited'][field]} for key,field in [('entry','entry_delta'),('exit','exit_delta'),('loop_seam','seam_absolute_delta')]}
 if boundary['exit']['edited_delta']>=.1 and boundary['exit']['control_delta']<.1:warnings.append('The edit introduces a newly timed strong exit transition in the selected-region mean trace.')
 summary={'protected_content':quality['protected_content'],'review_status':'needs_creator_review' if all(checks.values()) else 'checks_failed','selected_trigger_count':{'control':traces['control']['middle_cycle_max_count'],'edited':traces['edited']['middle_cycle_max_count'],'criterion_max':6},'outside_mask_error':quality['all_outside'],'boundary':boundary,'checks':checks,'warnings':warnings,'scope':'Known-development-profile processing; no safety/conformance or creator-benefit claim.'}
 if current_input!=sha(sourcepath) or output_hashes!={n:sha(job/(n+'.mp4')) for n in ['control','edited']}:raise RuntimeError('Media changed while boundary review was collected')
 frame_review=review.finish({'input_sha256':current_input,'prediction_sha256':current_prediction,'recipe_sha256':approval['recipe_sha256'],'output_hashes':output_hashes},{'newly_timed':boundary['exit']['edited_delta']>=.1 and boundary['exit']['control_delta']<.1,'edited_delta':boundary['exit']['edited_delta'],'control_delta':boundary['exit']['control_delta'],'criterion':.1})
 write_json(job/'frame-review.json',frame_review)
 report={'profile':CURRENT_PROFILE['id'],'input_profile':CURRENT_PROFILE,'summary':summary,'approval':approval,'input_sha256':current_input,'prediction_sha256':current_prediction,'output_hashes':output_hashes,'frame_review':frame_review,'quality':quality,'selected_traces':traces,'control_support_iou':best,'output_candidate_counts':{n:len(p['components']) for n,p in preds.items()},'versions':PROFILE['versions'],'limitations':LIMITATIONS}
 write_json(job/'report.json',report);write_json(job/'recipe.json',recipe)
 (job/'report.txt').write_text('Creator review report\n\nProcessing complete. '+summary['review_status']+'\n\n'+json.dumps(summary,indent=2,default=json_default)+'\n\nInput SHA256: '+current_input+'\nEdited SHA256: '+report['output_hashes']['edited']+'\nControl SHA256: '+report['output_hashes']['control']+'\n\nNo safety, certification or publication clearance is implied.\n')
 return {'summary':summary,'output_hashes':report['output_hashes'],'frame_review_sha256':sha(job/'frame-review.json')}
