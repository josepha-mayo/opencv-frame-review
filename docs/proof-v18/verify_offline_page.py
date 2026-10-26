import base64,hashlib,io,json,zipfile
from collections import Counter
from html.parser import HTMLParser

def verify(raw):
 with zipfile.ZipFile(io.BytesIO(raw))as z:
  assert z.testzip()is None;manifest=json.loads(z.read('manifest.json'));report=json.loads(z.read('report.json'));page=z.read('review.html').decode('utf-8')
  assert manifest['files']['review.html']['sha256']==hashlib.sha256(page.encode()).hexdigest()
  tags=[]
  class Read(HTMLParser):
   def handle_starttag(self,t,a):tags.append((t,dict(a)))
  Read().feed(page)
  assert not any(t in ('script','video','audio','iframe','form','base','object','embed')for t,a in tags)
  assert not any(k.startswith('on')for t,a in tags for k in a)
  assert "default-src 'none'"in page and 'img-src data:'in page and 'does not record creator acceptance'in page
  expected=[a for r in report['frame_review']['rows']for a in r['images'].values()]+[a for r in report['teaching_review']['regions']for m in r['moments']for a in m['images'].values()]
  images=[a['src']for t,a in tags if t=='img'];decoded=[]
  for src in images:
   assert src.startswith('data:image/png;base64,');png=base64.b64decode(src.split(',',1)[1],validate=True);decoded.append(hashlib.sha256(png).hexdigest())
  assert Counter(decoded)==Counter(a['sha256']for a in expected)
  for t,a in tags:
   if 'href'in a:assert a['href'].startswith('#')or a['href']in z.namelist()
  return dict(complete=True,embedded_proof_images=len(images),all_png_bytes_match_report=True,no_scripts_external_assets_or_media_elements=True,relative_artifact_links_present=True,html_sha256=hashlib.sha256(page.encode()).hexdigest(),html_bytes=len(page.encode()))
