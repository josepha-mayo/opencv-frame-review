"""Owned-process tree accounting using PPIDs; /proc task children may be absent."""
from pathlib import Path
import os,resource,time

def snapshot(root_pid=None,expected_children=(),started=None):
 root_pid=os.getpid() if root_pid is None else root_pid;rows={}
 for item in Path('/proc').iterdir():
  if not item.name.isdigit():continue
  try:
   stat=(item/'stat').read_text().rsplit(')',1)[1].split();pid=int(item.name);ppid=int(stat[1]);cpu=(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK');rss=next((int(x.split()[1])*1024 for x in (item/'status').read_text().splitlines() if x.startswith('VmRSS:')),0);rows[pid]=(ppid,cpu,rss)
  except (FileNotFoundError,ProcessLookupError):continue
 if root_pid not in rows:raise RuntimeError('Own process resource accounting unavailable')
 selected={root_pid}
 while True:
  more={pid for pid,(ppid,_,_) in rows.items() if ppid in selected}
  if more<=selected:break
  selected|=more
 missing=set(expected_children)-selected
 if missing:raise RuntimeError('Active owned child accounting unavailable: '+','.join(map(str,sorted(missing))))
 own=resource.getrusage(resource.RUSAGE_SELF);dead=resource.getrusage(resource.RUSAGE_CHILDREN)
 return {'cpu_seconds':own.ru_utime+own.ru_stime+dead.ru_utime+dead.ru_stime+sum(rows[p][1] for p in selected if p!=root_pid),'rss_bytes':sum(rows[p][2] for p in selected),'own_rss_bytes':rows[root_pid][2],'live_descendant_pids':sorted(selected-{root_pid}),'wall_seconds':None if started is None else time.monotonic()-started}
