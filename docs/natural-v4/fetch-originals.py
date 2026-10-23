"""Fetch selected public evaluation originals into a new directory; verify bytes.

Example: python docs/natural-v4/fetch-originals.py ./originals --case jupyter
Use --case all for all seven recorded sources. Media credits/licenses are separate
from source-code notices; downloading does not grant additional reuse rights.
"""
from pathlib import Path
import argparse,hashlib,json,urllib.request
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('new_directory',type=Path)
parser.add_argument('--case',default='jupyter')
args=parser.parse_args()
here=Path(__file__).resolve().parent
source_file=here/'all-sources.json'
sources=json.loads(source_file.read_text(encoding='utf-8'))
selected=sources if args.case=='all' else [s for s in sources if s['id']==args.case]
if not selected:parser.error('Unknown case; use an id from all-sources.json or all')
args.new_directory.mkdir(exist_ok=False)
for source in selected:
    name=source['filename'];assert Path(name).name==name
    request=urllib.request.Request(source.get('original_url',source.get('url')),headers={'User-Agent':'FrameReviewNaturalEvaluation/1.0'})
    with urllib.request.urlopen(request,timeout=60) as response:data=response.read(64*1024**2+1)
    if len(data)>64*1024**2 or len(data)!=source['bytes'] or hashlib.sha256(data).hexdigest()!=source['sha256']:
        raise RuntimeError('Original bytes do not match the recorded source: '+name)
    (args.new_directory/name).write_bytes(data)
    print(name,source['sha256'])
