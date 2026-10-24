"""Three prepared natural examples; repeats are not independent successes."""
from pathlib import Path
import json,subprocess,sys
out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
rows=[]
for example in ('jupyter','npm','gentoo'):
    run=subprocess.run([sys.executable,str(Path(__file__).with_name('integration_steady_detail.py')),str(out/example),example])
    rows.append({'example':example,'returncode':run.returncode})
    (out/'results.json').write_text(json.dumps({'complete':False,'cases':rows},indent=2)+'\n')
    if run.returncode:raise SystemExit(run.returncode)
(out/'results.json').write_text(json.dumps({'complete':True,'cases':rows},indent=2)+'\n')
