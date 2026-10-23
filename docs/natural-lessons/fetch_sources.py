"""Fetch the exact licensed natural-audit inputs; verify SHA-256 before using.

python fetch_sources.py /path/to/originals [--camera] [--verify-only]
The optional camera stress input is a Commons transcode, not an active lesson.
"""
from pathlib import Path
import argparse, hashlib, json, urllib.request

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--camera',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();base=Path(__file__).resolve().parent
    sources=json.loads((base/'sources.json').read_text(encoding='utf-8'))
    if args.camera:sources.append(json.loads((base/'camera-stress-source.json').read_text(encoding='utf-8')))
    args.directory.mkdir(parents=True,exist_ok=True)
    for source in sources:
        filename=source['filename'];assert Path(filename).name==filename
        target=args.directory/filename
        if not target.exists():
            if args.verify_only:raise FileNotFoundError(target)
            request=urllib.request.Request(source['url'],headers={'User-Agent':'FrameReviewEvaluation/1.0 (licensed research inputs)'})
            with urllib.request.urlopen(request,timeout=60) as response:data=response.read(64*1024**2+1)
            if len(data)!=source['bytes'] or hashlib.sha256(data).hexdigest()!=source['sha256']:
                raise ValueError('Source identity changed; stop rather than substitute: '+filename)
            temporary=target.with_suffix(target.suffix+'.download')
            temporary.write_bytes(data);temporary.replace(target)
        data=target.read_bytes()
        if len(data)!=source['bytes'] or hashlib.sha256(data).hexdigest()!=source['sha256']:
            raise ValueError('Existing source identity differs: '+filename)
        print(filename,source['sha256'])

if __name__=='__main__':main()
