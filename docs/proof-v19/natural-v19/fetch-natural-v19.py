from pathlib import Path
import datetime,hashlib,json,re,urllib.parse,urllib.request
W=Path(__file__).resolve().parent
titles=[('sed-tamil','Sed-command-delete-tutorial in Tamil-2018-july-10.webm'),('lynx-tamil','Konsole-browser-lynx-Tamil-Wikipedia.webm')]
plan={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':[{'id':i,'title':t}for i,t in titles],'rule':'Seven fixed 12-second windows per original, starts floor(min(duration-12,600)*q) for q=.10,.25,.35,.50,.65,.75,.90. Record all outcomes, never add a defect; proposals require human inspection before calling a useful repair.','scope':'Two new named terminal/browser lessons selected after prior screens; same creator as earlier Tamil samples, not independent creators. Exploratory selection. Not representative recall or human benefit.','runtime_manifest_sha256':'4af4ce21231c400e1111c42386a898a29b648e46fbcfafe97021b9983f65d935'}
pp=W/'natural-v19-selection-plan.json'
if pp.exists():assert json.loads(pp.read_text())['sources']==plan['sources']
else:pp.write_text(json.dumps(plan,indent=2)+'\n')
out=W/'natural-v19-originals';out.mkdir(exist_ok=True)
rp=W/'natural-v19-sources.json';records=json.loads(rp.read_text())if rp.exists()else[]
for key,title in titles:
 if any(r['id']==key for r in records):continue
 query=urllib.parse.urlencode({'action':'query','format':'json','prop':'imageinfo','titles':'File:'+title,'iiprop':'url|size|sha1|extmetadata','iiextmetadatafilter':'Artist|LicenseShortName|LicenseUrl|Credit'})
 req=lambda url:urllib.request.Request(url,headers={'User-Agent':'FrameReview natural lesson evaluation/1.0'})
 info=next(iter(json.load(urllib.request.urlopen(req('https://commons.wikimedia.org/w/api.php?'+query),timeout=45))['query']['pages'].values()))['imageinfo'][0]
 assert 0<info['size']<64*1024**2
 media=urllib.request.urlopen(req(info['url']),timeout=90).read(64*1024**2+1)
 assert len(media)==info['size'] and hashlib.sha1(media).hexdigest()==info['sha1']
 filename=key+'.webm';(out/filename).write_bytes(media)
 clean=lambda k:re.sub('<[^>]+>','',info.get('extmetadata',{}).get(k,{}).get('value',''))
 records.append({'id':key,'filename':filename,'title':title,'page':info['descriptionurl'],'original_url':info['url'],'bytes':len(media),'sha256':hashlib.sha256(media).hexdigest(),'commons_sha1':info['sha1'],'artist':clean('Artist'),'license':clean('LicenseShortName'),'license_url':clean('LicenseUrl'),'credit':clean('Credit'),'rights_scope':'Official Commons metadata as listed; not independent rights clearance or endorsement. No added defect.','fetched_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 rp.write_text(json.dumps(records,indent=2)+'\n');print(key,len(media),flush=True)
