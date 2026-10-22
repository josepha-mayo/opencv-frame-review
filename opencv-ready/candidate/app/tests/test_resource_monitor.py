"""Small no-media accounting test with owned sleeping Python descendants."""
import json,pathlib,signal,subprocess,sys,time,unittest
from unittest.mock import patch
from resource_monitor import snapshot
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from server import Manager
class TreeAccounting(unittest.TestCase):
 def test_parent_and_grandchild_rss_are_counted(self):
  code="import json,subprocess,sys,time\na=bytearray(8*1024**2)\np=subprocess.Popen([sys.executable,'-c','import time; a=bytearray(8*1024**2); print(1,flush=True); time.sleep(10)'],stdout=subprocess.PIPE,text=True)\np.stdout.readline();print(json.dumps({'pid':p.pid}),flush=True);time.sleep(10)\n"
  p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,text=True,start_new_session=True)
  try:
   grandchild=json.loads(p.stdout.readline())['pid'];v=snapshot(expected_children=[p.pid]);self.assertIn(p.pid,v['live_descendant_pids']);self.assertIn(grandchild,v['live_descendant_pids']);self.assertGreater(v['rss_bytes']-v['own_rss_bytes'],16*1024**2)
  finally:Manager.stop_process(p);p.stdout.close()
 def test_missing_expected_child_fails_closed(self):
  with self.assertRaises(RuntimeError):snapshot(expected_children=[999999999])
if __name__=='__main__':unittest.main()
