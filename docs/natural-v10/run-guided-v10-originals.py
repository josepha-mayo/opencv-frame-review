from pathlib import Path
import json,subprocess,sys
W=Path('/audit');cases=json.loads((W/'natural-v4-cases.json').read_text());g=json.loads((W/'marking-v9-gentoo-adjusted-case.json').read_text());g['source_group']='v5shell';cases.insert(0,g)
for file,group in [('natural-v6-writer-case.json','v6'),('natural-v6-userpage-case.json','v6b')]:
    c=json.loads((W/file).read_text());c['source_group']=group;cases.append(c)
out=Path(sys.argv[1]);out.mkdir(exist_ok=False);failures=[]
if len(sys.argv)>2:
    selected=sys.argv[2].split(',');cases=[case for case in cases if case['id']in selected]
    assert len(cases)==len(selected),'Choose known retained cases for a sequential isolated retry.'
for case in cases:
    folder={'new':'/new','old':'/originals','earlier':'/earlier','v5shell':'/v5shell','v6':'/v6','v6b':'/v6b'}[case['source_group']];config=out/(case['id']+'-config.json');config.write_text(json.dumps(case,indent=2)+'\n')
    r=subprocess.run([sys.executable,'/audit/qualify-guided-v10.py',str(out/case['id']),folder+'/'+case['filename'],str(case['start']),str(config)],capture_output=True,text=True);(out/(case['id']+'.log')).write_text(r.stdout+r.stderr);print(case['id'],'original HTTP qualification',r.returncode,flush=True)
    if r.returncode:failures.append(case['id']);print((r.stdout+r.stderr)[-1600:],flush=True)
if failures:raise RuntimeError('Retained failures: '+','.join(failures))

