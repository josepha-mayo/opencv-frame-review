from pathlib import Path
import json,subprocess,sys
cases=json.loads(Path('/audit/natural-v4-cases.json').read_text());gentoo=json.loads(Path('/audit/natural-v5-gentoo-case.json').read_text());gentoo['source_group']='v5-shell';cases.append(gentoo)
out=Path(sys.argv[1]);out.mkdir(exist_ok=True);failures=[]
for c in cases:
    source=Path({'new':'/new','old':'/originals','earlier':'/earlier','v5-shell':'/v5shell'}[c['source_group']])/c['filename'];config=out/(c['id']+'-case.json');config.write_text(json.dumps(c,indent=2)+'\n')
    r=subprocess.run([sys.executable,'/audit/qualify-natural-v6.py',str(out/c['id']),str(source),str(c['start']),str(config)],capture_output=True,text=True)
    (out/(c['id']+'.log')).write_text(r.stdout+r.stderr);print(c['id'],'HTTP qualification exit',r.returncode,flush=True)
    if r.returncode:failures.append(c['id']);print((r.stdout+r.stderr)[-1800:],flush=True)
if failures:raise RuntimeError('Retained qualification failures: '+', '.join(failures))
