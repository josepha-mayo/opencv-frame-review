from pathlib import Path
import subprocess,sys
W=Path(__file__).resolve().parent;version=sys.argv[1];assert version in ('v9','v9b','v9c')
s=(W/'natural-v6-cohort.py').read_text().replace('natural-v6','natural-'+version).replace('assert len(sources)==7','assert len(sources)=='+('4'if version=='v9'else'3')).replace('Twenty-one fixed windows from seven named instructional recordings',('Twelve windows from four new drawing/image-editing instructional recordings'if version=='v9'else'Nine windows from three additional Linux/command-line recordings'))
(W/('natural-'+version+'-final-cohort.py')).write_text(s,encoding='utf-8')
E='/home/joseph/.local/share/opencv-creator-runtime/evidence/marking-v9-'+version+'-skeletonfix';D=['wsl','-d','Ubuntu-24.04','-u','root','--exec','docker','-H','unix:///var/run/docker.sock']
def linux(p):return subprocess.check_output(['wsl','-d','Ubuntu-24.04','--exec','wslpath','-a',str(p)],text=True).strip()
subprocess.run(['wsl','-d','Ubuntu-24.04','-u','root','--exec','install','-d','-o','10001','-g','10001',E],check=True)
subprocess.run(D+['run','--rm','--network','none','--cpuset-cpus',('0'if version=='v9'else'1'),'-v',linux(W)+':/audit:ro','-v',linux(W/('natural-'+version+'-originals'))+':/new:ro','-v',E+':/evidence','opencv-creator:marking-v9-final','python','/audit/natural-'+version+'-final-cohort.py','/evidence'],check=True)
