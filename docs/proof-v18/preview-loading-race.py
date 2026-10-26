"""Build labelled static loading-race QA from a qualified Joomla rescue ZIP.

Usage: python preview-loading-race.py PACK.zip NEW_OUTPUT_DIRECTORY
Then: python serve-loading-race.py NEW_OUTPUT_DIRECTORY
No approval, encoding or human study is performed.
"""
from pathlib import Path
import hashlib,json,shutil,sys,zipfile
HERE=Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'studio/static/app.js').is_file())
OUT=Path(sys.argv[2]).resolve();OUT.mkdir(exist_ok=False)
with zipfile.ZipFile(sys.argv[1])as z:
 frame=json.loads(z.read('frame-review.json'));teaching=json.loads(z.read('teaching-review.json'));summary=json.loads(z.read('report.json'))['summary']
 def asset(a,kind):
  data=z.read(a['filename']);assert hashlib.sha256(data).hexdigest()==a['sha256']
  rel=Path('api/jobs')/('1'*32)/kind/a['filename'];target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);a['url']='/'+rel.as_posix()
 for row in frame['rows']:
  for a in row['images'].values():asset(a,'review')
 for region in teaching['regions']:
  for moment in region['moments']:
   for a in moment['images'].values():asset(a,'teaching')
job={'id':'1'*32,'status':'complete','input_sha256':frame['input_sha256'],'prediction_sha256':frame['prediction_sha256'],'frame_review':frame,'teaching_review':teaching,'summary':summary,'artifacts':{}}
region=json.loads(json.dumps(teaching['regions'][0]));region['label']='Uncached loading QA';moment=region['moments'][0]
for role,a in moment['images'].items():
 original=OUT/a['url'].lstrip('/');target=original.parent/('uncached-'+role+'.png');shutil.copyfile(original,target);a['url']='/'+target.relative_to(OUT).as_posix()
static=OUT/'static';static.mkdir()
for name in ('styles.css','natural-gentoo.png'):shutil.copyfile(REPO/'studio/static'/name,static/name)
bootstrap='  job='+json.dumps(job)+'; renderResults(); byId("result-highlights").append(teachingComparison('+json.dumps(region)+','+json.dumps(moment)+'));'
for source,name in ((REPO/'studio/static/app.js','app.js'),(HERE/'v17-before-app.js','before.js')):
 text=source.read_text(encoding='utf-8');assert text.count('  initialize();')==1;(static/name).write_text(text.replace('  initialize();',bootstrap),encoding='utf-8')
html=(REPO/'studio/static/index.html').read_text(encoding='utf-8').replace('<body>','<body><p role="status">LOCAL RECORDED-PNG LOADING QA: no live encoding, approval, human response or measured benefit.</p>')
(OUT/'index.html').write_text(html,encoding='utf-8');(OUT/'before.html').write_text(html.replace('/static/app.js','/static/before.js'),encoding='utf-8')
print('Open /before.html and /, then compare Uncached loading QA frame114 at200%, pan and rapidly switch edit/source during loading.')
