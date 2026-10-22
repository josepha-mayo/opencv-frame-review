"""Standard-library contracts shared by server, worker and tests."""
from pathlib import Path
import hashlib, json, math, re, secrets
from protected_regions import validate_regions, CRITERIA
APP = Path(__file__).resolve().parent
W,H,N,FPS = 320,180,90,30
MAX_INPUT = 8*1024*1024
MEDIA_PROFILES = [
 {'id':'owned-sdr-review-v0','width':320,'height':180,'frames':90,'fps':30,'duration_seconds':3,'max_input_bytes':4*1024**2},
 {'id':'owned-sdr-review-v1-card','width':640,'height':360,'frames':180,'fps':30,'duration_seconds':6,'max_input_bytes':8*1024**2},
]
def media_profile(shape, frames=None):
 for item in MEDIA_PROFILES:
  if shape==[item['height'],item['width']]:
   spec=dict(item)
   if frames is not None:
    if type(frames) is not int or not 30<=frames<=360 or frames%3:raise ValueError('Duration must be 30–360 frames in 3-frame increments (1.0–12.0 seconds).')
    spec.update(frames=frames,duration_seconds=frames//30 if frames%30==0 else frames/30)
   return spec
 raise ValueError('Unsupported dimensions; only the two declared profiles are admitted.')
DURATION_CONTRACT = {'minimum_frames':30,'maximum_frames':360,'frame_increment':3,'minimum_seconds':1.0,'maximum_seconds':12.0,'step_seconds':0.1,'fps':30}
PROFILE = json.loads((APP/'profile.json').read_text())
PROFILE_ID = 'owned-sdr-review-v0'
LIMITATIONS = [
 'Development profile validated only on known owned synthetic fixtures.',
 'This is limited abrupt-luminance candidate review, not a safety or conformance assessment.',
 'Gradual transitions, saturated red, patterns, HDR and viewing conditions are not covered.',
 'A local hold can alter motion and introduce an exit transition; encoded edges can spill outside the mask.',
 'No-candidate means only that this profile found no candidate.',
]
EDIT = {'kind':'local-hold','step_frames':10,'support':'approved candidate RLE','interval':'inclusive first/last candidate event frame'}
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(obj): return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def json_default(obj):
 if hasattr(obj,'item'): return obj.item()
 raise TypeError(type(obj).__name__)
def write_json(path,obj):
 path=Path(path); tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(obj,indent=2,allow_nan=False,default=json_default)+'\n'); tmp.replace(path)
def read_json(path): return json.loads(Path(path).read_text())
def safe_name(value):
 return re.sub(r'[^A-Za-z0-9 ._-]','_',str(value).replace('\\','/').split('/')[-1])[:100] or 'input.mp4'
def validate_probe(data):
 streams=data.get('streams',[])
 from audio_preserve import validate_streams
 if not streams: raise ValueError('Missing video stream')
 s=streams[0]
 count=s.get('nb_frames')
 if not isinstance(count,str) or not re.fullmatch(r'[1-9][0-9]{1,2}',count):raise ValueError('Missing or invalid frame count')
 spec=media_profile([s.get('height'),s.get('width')],int(count))
 validate_streams(data,spec['duration_seconds'])
 expected={'codec_name':'h264','pix_fmt':'yuv420p','width':spec['width'],'height':spec['height'],'color_range':'tv','color_space':'bt709','color_transfer':'bt709','color_primaries':'bt709','chroma_location':'left','r_frame_rate':'30/1','avg_frame_rate':'30/1','time_base':'1/15360','nb_frames':str(spec['frames'])}
 bad={k:[s.get(k),v] for k,v in expected.items() if s.get(k)!=v}
 if bad: raise ValueError('Unsupported input contract: '+json.dumps(bad,sort_keys=True))
 duration=float(s.get('duration','nan'))
 if not math.isfinite(duration) or abs(duration-spec['duration_seconds'])>1e-6: raise ValueError('Duration does not match the declared dimensions/profile.')
 if s.get('sample_aspect_ratio') not in (None,'1:1','0:1','N/A'): raise ValueError('Non-square pixel aspect ratios are unsupported.')
 for item in s.get('side_data_list',[]):
  if 'rotation' in item and item['rotation']!=0: raise ValueError('Rotated display matrices are unsupported.')
 if s.get('disposition',{}).get('attached_pic'): raise ValueError('Attached pictures are unsupported.')
 return s

def validate_frames(data,n=N):
 frames=data.get('frames',[])
 if len(frames)!=n: raise ValueError('Decoded frame count does not match the admitted profile.')
 pts=[]
 for f in frames:
  v=f.get('best_effort_timestamp')
  if type(v) is not int: raise ValueError('Missing or non-integral frame timestamps.')
  pts.append(v)
 if pts!=[512*i for i in range(n)]: raise ValueError('Frame timestamps do not match the frozen 30 fps profile.')
 return [x/15360 for x in pts]

def proposed_recipe(input_sha,prediction_sha,candidate_id,component,protected_regions=None,export_mode='legacy',input_profile=None):
 if export_mode not in ('legacy','native-yuv-whole-clip-v9','periodic-local-retime-v2'):raise ValueError('Unknown export mode')
 spec=media_profile(component['mask_shape'],None if input_profile is None else input_profile.get('frames'))
 if input_profile is not None and spec!=input_profile:raise ValueError('Invalid admitted input profile')
 lo,hi=[round(float(x)*FPS) for x in component['interval']]
 if not 0<=lo<=hi<spec['frames'] or [lo/FPS,hi/FPS]!=component['interval']: raise ValueError('Candidate interval is not on admitted frame timestamps.')
 regions=validate_regions(protected_regions,component['mask_shape'],component['mask_rle'] if protected_regions else None)
 result = {'protected_regions':regions,'protected_criteria':dict(CRITERIA),'profile':spec['id'],'input_profile':spec,'input_sha256':input_sha,'prediction_sha256':prediction_sha,'candidate_id':candidate_id,'component_sha256':hashlib.sha256(canonical(component)).hexdigest(),'frame_bounds_inclusive':[lo,hi],'edit':EDIT if export_mode=='legacy' else {'kind':'native-yuv-whole-clip-v9','reference_frame':0,'support':'approved luma mask and all touched 2x2 chroma blocks','interval':'entire clip'},'export_mode':export_mode,'detector_ast_sha256':PROFILE['detector_ast_sha256'],'temporal_ast_sha256':PROFILE['temporal_ast_sha256'],'transport_profile_sha256':sha(APP/'profile.json'),'audio_policy':'Optional AAC-LC mono 48 kHz, zero start, exact video duration; copy-only with packet/timing/PCM verification; local retiming only','implementation_sha256':{name:sha(APP/name) for name in ['common.py','engine.py','worker.py','frozen_algorithms.py','review_frames.py','protected_regions.py','native_yuv.py','retime.py','retime_export.py','acceptance.py','audio_preserve.py']}}
 if export_mode=='periodic-local-retime-v2':
  result['edit']={'kind':export_mode,'factor':5,'support':'approved luma mask and all touched 2x2 chroma blocks','interval':'inclusive detected interval','cycle_policy':{'max_period_frames':30,'minimum_cycles':3,'max_repeat_plane_frame_mae':2.0,'max_repeat_sample_error':32,'min_luma_mean_range':32.0},'scope':'bounded appearance recurrence, not semantic periodicity; optional supported audio copied and verified unchanged'}
  result['protected_criteria']={k:0 for k in CRITERIA}
 return result

def validate_approval(approval,input_sha,prediction_sha,component,input_profile=None):
 if approval.get('approve') is not True: raise ValueError('Explicit edit approval is required.')
 expected=proposed_recipe(input_sha,prediction_sha,approval.get('candidate_id'),component,approval.get('protected_regions',[]),approval.get('recipe',{}).get('export_mode','legacy'),input_profile)
 if approval.get('recipe')!=expected: raise ValueError('Approval does not match this input, prediction or edit recipe.')
 if approval.get('recipe_sha256')!=hashlib.sha256(canonical(expected)).hexdigest(): raise ValueError('Approved recipe hash mismatch.')
 return expected
