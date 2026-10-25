"""Invitation-only anonymous pilot collector. Does not alter the editing runtime."""
from pathlib import Path
import base64
import datetime
import hashlib
import hmac
import itertools
import json
import os
import re
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent
ROLES={'independent','team'}
EXPERIENCE={'often','sometimes','never','prefer_not_say'}
DEVICES={'phone','tablet','computer'}
PREFERENCES={'A','B','same','neither'}
LOSS={'A','B','both','neither','unsure'}
SKIPS={'playback_error','unreadable','do_not_want_to_continue'}

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(value).hexdigest()
def encode(raw):return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def decode(raw):return base64.urlsafe_b64decode(raw+'='*(-len(raw)%4))

class Conflict(ValueError):pass
class Forbidden(ValueError):pass

class AwsStore:
    def __init__(self,bucket,prefix):
        import boto3
        from botocore.config import Config
        self.client=boto3.client('s3',region_name='us-east-1',config=Config(signature_version='s3v4',connect_timeout=2,read_timeout=2,retries={'max_attempts':1,'mode':'standard'}))
        self.bucket=bucket;self.prefix=prefix.rstrip('/')+'/'
    def put(self,key,value,once=False):
        request=dict(Bucket=self.bucket,Key=self.prefix+'responses/'+key,Body=canonical(value),ContentType='application/json',ServerSideEncryption='AES256')
        if once:request['IfNoneMatch']='*'
        return self.client.put_object(**request)
    def media_url(self,key):
        return self.client.generate_presigned_url('get_object',Params={'Bucket':self.bucket,'Key':self.prefix+'assets/'+key+'.webm'},ExpiresIn=1800)

class Study:
    def __init__(self,protocol,media,invites,secret,store,opened=False,clock=time.time):
        self.protocol=protocol;self.media=media;self.invites=invites;self.secret=secret;self.store=store;self.opened=opened;self.clock=clock
        self.protocol_hash=digest(canonical(protocol));self.media_hash=digest(canonical(media))
        self.close=datetime.datetime.fromisoformat(protocol['closes_utc'].replace('Z','+00:00')).timestamp()
        self.cases={c['id']:c for c in protocol['cases']}
        if len(secret)<32 or len(self.cases)!=3 or media.get('complete') is not True or set(media['cases'])!=set(self.cases):raise ValueError('Study configuration incomplete.')
        for variants in media['cases'].values():
            if variants.get('matched_timestamp_sequences') is not True:raise ValueError('Study timing comparison unavailable.')
            for variant in ('source','edited'):
                item=variants[variant]
                if (not re.fullmatch('[0-9a-f]{64}',item['sha256']) or item.get('native_samples_exact') is not True
                    or item.get('all_teaching_rgb_digests_match_pinned_linux') is not True or item.get('audio_tracks')!=0):raise ValueError('Qualified silent study media required.')
    def invitation(self,code):
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}',code):raise Forbidden('Invalid invitation.')
        iid=digest(code.encode());invite=self.invites.get(iid)
        if not invite:raise Forbidden('Invalid invitation.')
        return iid,invite
    def check_open(self,invite):
        if self.clock()>=self.close:raise Conflict('Collection is closed. No response was saved.')
        if invite['kind']!='qa' and not self.opened:raise Conflict('Human collection is not open yet. No response was saved.')
    def sign(self,payload):
        raw=encode(canonical(payload));return raw+'.'+hmac.new(self.secret,raw.encode(),hashlib.sha256).hexdigest()
    def session(self,value):
        if not isinstance(value,str) or len(value)>2048:raise Forbidden('Invalid study session.')
        try:
            raw,signature=value.split('.')
            if not hmac.compare_digest(signature,hmac.new(self.secret,raw.encode(),hashlib.sha256).hexdigest()):raise Forbidden('Invalid study session.')
            payload=json.loads(decode(raw))
        except (ValueError,KeyError,UnicodeError):raise Forbidden('Invalid study session.') from None
        if (payload.get('protocol')!=self.protocol_hash or payload.get('media')!=self.media_hash
            or type(payload.get('issued')) is not int or not 0<=self.clock()-payload['issued']<=3600
            or payload.get('iid') not in self.invites):raise Forbidden('Study session expired or changed.')
        return payload,self.invites[payload['iid']]
    def layout(self,invite):
        cell=invite['cell'];ids=list(self.cases)
        order=list(itertools.permutations(ids))[cell%6]
        return order,{case:('source' if (cell//6+ids.index(case))%2==0 else 'edited') for case in ids}
    def start(self,body):
        if set(body)!={'invite','consent','role','experience','device'} or body['consent'] is not True:raise ValueError('Voluntary adult participation and the required choices are needed.')
        if body['role'] not in ROLES or body['experience'] not in EXPERIENCE or body['device'] not in DEVICES:raise ValueError('Choose the required study options.')
        iid,invite=self.invitation(body['invite']);self.check_open(invite)
        payload=dict(iid=iid,issued=int(self.clock()),protocol=self.protocol_hash,media=self.media_hash,
                     role=body['role'],experience=body['experience'],device=body['device'],consent=True)
        token=self.sign(payload);kind=invite['kind'];order,_=self.layout(invite)
        self.store.put(('qa-starts/' if kind=='qa' else 'starts/')+iid+'.json',dict(payload,kind=kind,last_started_utc=datetime.datetime.fromtimestamp(self.clock(),datetime.timezone.utc).isoformat()))
        cases=[]
        for cid in order:
            case={k:v for k,v in self.cases[cid].items() if k not in ('correct','ground_truth')}
            _,a=self.layout(invite)
            case['videos']={slot:self.store.media_url(self.media['cases'][cid][a[cid] if slot=='A' else ('edited' if a[cid]=='source' else 'source')]['sha256']) for slot in ('A','B')};cases.append(case)
        return dict(session=token,protocol_sha256=self.protocol_hash,media_sha256=self.media_hash,is_qa=kind=='qa',cases=cases,closes_utc=self.protocol['closes_utc'])
    def invite_info(self,body):
        if set(body)!={'invite'}:raise ValueError('Invitation required.')
        _,invite=self.invitation(body['invite'])
        return dict(is_qa=invite['kind']=='qa',collection_open=(self.opened or invite['kind']=='qa') and self.clock()<self.close,
                    protocol_sha256=self.protocol_hash,media_sha256=self.media_hash,closes_utc=self.protocol['closes_utc'])
    def video(self,query):
        if set(query)!={'session','case','slot'} or query['case'] not in self.cases or query['slot'] not in ('A','B'):raise ValueError('Unknown study clip.')
        _,invite=self.session(query['session']);_,a=self.layout(invite)
        variant=a[query['case']] if query['slot']=='A' else ('edited' if a[query['case']]=='source' else 'source')
        return self.store.media_url(self.media['cases'][query['case']][variant]['sha256'])
    def submit(self,body):
        if set(body)!={'session','cases'}:raise ValueError('Unexpected response fields.')
        session,invite=self.session(body['session']);self.check_open(invite)
        order,a=self.layout(invite);rows=body['cases']
        if not isinstance(rows,list) or len(rows)!=3 or [r.get('id') for r in rows if isinstance(r,dict)]!=list(order):raise ValueError('Complete the three assigned lessons in order.')
        normalized=[]
        required={'id','outcome','answer','answer_ms','preference','distraction_A','distraction_B','lost_information','skip_reason','telemetry'}
        for row in rows:
            cid=row['id'];case=self.cases[cid]
            if set(row)!=required or row['outcome'] not in ('completed','skipped'):raise ValueError('Response shape changed.')
            if row['answer'] is not None and row['answer'] not in {o['id'] for o in case['options']}:raise ValueError('Unknown reading answer.')
            if row['answer_ms'] is not None and (type(row['answer_ms']) is not int or not 0<=row['answer_ms']<=600000):raise ValueError('Reading time is outside the study bound.')
            if set(row['telemetry'])!={'A','B'}:raise ValueError('Playback information missing.')
            for telemetry in row['telemetry'].values():
                if set(telemetry)!={'ended','watched_seconds','plays','error'} or type(telemetry['ended']) is not bool:raise ValueError('Playback information changed.')
                if type(telemetry['watched_seconds']) not in (int,float) or not 0<=telemetry['watched_seconds']<=600:raise ValueError('Playback duration outside bound.')
                if type(telemetry['plays']) is not int or not 0<=telemetry['plays']<=30 or type(telemetry['error']) is not bool:raise ValueError('Playback information outside bound.')
            if row['outcome']=='completed':
                if (row['answer'] is None or row['answer_ms'] is None or row['preference'] not in PREFERENCES
                    or row['lost_information'] not in LOSS or row['skip_reason'] is not None
                    or any(type(row[k]) is not int or not 1<=row[k]<=5 for k in ('distraction_A','distraction_B'))
                    or not all(t['ended'] is True and t['watched_seconds']>=10 for t in row['telemetry'].values())):raise ValueError('Watch both clips and answer the required comparison questions, or record a skip.')
            else:
                if row['skip_reason'] not in SKIPS or any(row[k] is not None for k in ('preference','distraction_A','distraction_B','lost_information')):raise ValueError('Record a skip reason without an invented preference.')
            pref=row['preference'];decoded=(a[cid] if pref=='A' else ('edited' if a[cid]=='source' else 'source') if pref=='B' else pref)
            normalized.append(dict(row,first_variant=a[cid],decoded_preference=decoded,answer_correct=(row['answer']==case['correct']) if row['answer'] is not None else None))
        kind=invite['kind'];result=dict(schema='lesson-reading-response-v1',protocol_sha256=self.protocol_hash,media_sha256=self.media_hash,
              participant_id=session['iid'],allocation_cell=invite['cell'],kind=kind,is_qa=kind=='qa',role=session['role'],experience=session['experience'],device=session['device'],consent=True,consent_scope='software_qa' if kind=='qa' else 'voluntary_adult_pilot',
              issued_utc=datetime.datetime.fromtimestamp(session['issued'],datetime.timezone.utc).isoformat(),
              submitted_utc=datetime.datetime.fromtimestamp(self.clock(),datetime.timezone.utc).isoformat(),cases=normalized,
              provenance='Invited self-reported volunteer; no independent personhood or attention authentication. Browser playback telemetry is self-reported.')
        self.store.put(('qa-results/' if kind=='qa' else 'results/')+session['iid']+'.json',result,once=True)
        return dict(received=True,is_qa=kind=='qa',receipt=session['iid'][:16],debrief='One version of each lesson holds a small observed caret state; the other keeps the prepared source. The comparison does not establish learning benefit. Thank you. Keep your invitation if you want to exclude your response.',mapping={cid:{'A':a[cid],'B':'edited' if a[cid]=='source' else 'source'} for cid in order})
    def withdraw(self,body):
        if set(body)!={'invite'}:raise ValueError('Invitation required.')
        iid,invite=self.invitation(body['invite'])
        self.store.put(('qa-withdrawals/' if invite['kind']=='qa' else 'withdrawals/')+iid+'.json',dict(participant_id=iid,withdrawn_utc=datetime.datetime.fromtimestamp(self.clock(),datetime.timezone.utc).isoformat()))
        return {'excluded':True,'message':'This invitation is marked excluded from analysis. Private raw records expire after 30 days.'}

_APP=None
def app():
    global _APP
    if _APP is None:
        read=lambda name:json.loads((ROOT/name).read_text(encoding='utf-8'))
        _APP=Study(read('protocol.json'),read('media.json'),read('invites.json'),os.environ['STUDY_SECRET'].encode(),AwsStore(os.environ['STUDY_BUCKET'],os.environ['STUDY_PREFIX']),os.environ.get('HUMAN_COLLECTION_OPEN')=='1')
    return _APP

def response(status,value,ctype='application/json',headers=None):
    if ctype=='application/json':value=json.dumps(value,allow_nan=False)
    return {'statusCode':status,'headers':{'Content-Type':ctype,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',**(headers or {})},'body':value}

def handler(event,context):
    from botocore.exceptions import ClientError,BotoCoreError
    try:
        study=app();method=event['requestContext']['http']['method'];path=event.get('rawPath','/')
        headers={k.lower():v for k,v in event.get('headers',{}).items()};origin='https://'+event['requestContext']['domainName']
        if method=='POST' and headers.get('origin')!=origin:raise Forbidden('Cross-origin submissions refused.')
        if method=='GET' and path in ('/','/study.js','/study.css'):
            name,ctype={'/':('index.html','text/html; charset=utf-8'),'/study.js':('study.js','application/javascript; charset=utf-8'),'/study.css':('study.css','text/css; charset=utf-8')}[path]
            bucket=os.environ['STUDY_BUCKET'];media_hosts=f'https://{bucket}.s3.amazonaws.com https://{bucket}.s3.us-east-1.amazonaws.com'
            content=(ROOT/'static'/name).read_text(encoding='utf-8')
            script_policy=style_policy="'self'"
            if path=='/':
                js=(ROOT/'static/study.js').read_text(encoding='utf-8');css=(ROOT/'static/study.css').read_text(encoding='utf-8')
                content=content.replace('<link rel="stylesheet" href="/study.css">','<style>'+css+'</style>').replace('<script src="/study.js" defer></script>','').replace('</body>','<script>'+js+'</script></body>')
                script_policy+=" 'sha256-"+base64.b64encode(hashlib.sha256(js.encode()).digest()).decode()+"'"
                style_policy+=" 'sha256-"+base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()+"'"
            return response(200,content,ctype,{'Content-Security-Policy':f"default-src 'none'; script-src {script_policy}; style-src {style_policy}; connect-src 'self'; media-src 'self' {media_hosts}; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})
        if method=='GET' and path=='/health':return response(200,{'ready':True,'protocol_sha256':study.protocol_hash,'media_sha256':study.media_hash,'human_collection_open':study.opened and study.clock()<study.close})
        if method=='GET' and path=='/api/media':
            parsed=urllib.parse.parse_qs(event.get('rawQueryString',''),max_num_fields=3)
            if any(len(v)!=1 for v in parsed.values()):raise ValueError('Repeated clip query.')
            return response(302,'','text/plain',{'Location':study.video({k:v[0] for k,v in parsed.items()})})
        if method!='POST' or path not in ('/api/invitation','/api/start','/api/submit','/api/withdraw'):return response(404,{'error':'Not found.'})
        raw=event.get('body') or ''
        if len(raw)>16384:raise ValueError('Study response too large.')
        raw=base64.b64decode(raw,validate=True) if event.get('isBase64Encoded') else raw.encode()
        if len(raw)>12000 or not headers.get('content-type','').startswith('application/json'):raise ValueError('Bounded JSON response required.')
        body=json.loads(raw)
        if not isinstance(body,dict):raise ValueError('JSON object required.')
        result={'/api/invitation':study.invite_info,'/api/start':study.start,'/api/submit':study.submit,'/api/withdraw':study.withdraw}[path](body)
        return response(200,result)
    except ClientError as error:
        # S3 conditional PutObject has no modeled PreconditionFailed exception.
        # Handle its duplicate-write conflict here, at the HTTP boundary only.
        code=error.response.get('Error',{}).get('Code')
        if code in ('PreconditionFailed','ConditionalRequestConflict'):return response(409,{'error':'This invitation already has a response. It was not changed or counted again.'})
        return response(503,{'error':'Private response storage is unavailable. No success is claimed; retain this page and retry.'})
    except BotoCoreError:
        return response(503,{'error':'Private response storage is unavailable. No success is claimed; retain this page and retry.'})
    except Forbidden as error:return response(403,{'error':str(error)})
    except Conflict as error:return response(409,{'error':str(error)})
    except (ValueError,KeyError,TypeError,UnicodeError) as error:return response(400,{'error':'Invalid or incomplete study request: '+str(error)})
