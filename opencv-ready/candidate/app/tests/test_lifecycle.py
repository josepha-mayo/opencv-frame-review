"""No-media lifecycle checks. Injected boundaries are not load/stress validation."""
import json, os, pathlib, signal, subprocess, sys, tempfile, threading, time, unittest
from unittest.mock import MagicMock, patch
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from common import *
from server import Manager
class Lifecycle(unittest.TestCase):
 def test_restart_is_terminal(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/('a'*32);p.mkdir();write_json(p/'job.json',{'id':'a'*32,'status':'exporting'})
   m=Manager(td)
   try:self.assertEqual(m.jobs['a'*32]['status'],'failed')
   finally:m.close()
 def test_outer_timeout_is_terminal_and_cleans(self):
  with tempfile.TemporaryDirectory() as td:
   m=Manager(td)
   try:
    with patch.object(m.pool,'submit'):jid=m.create('x',b'x')['id']
    fake=MagicMock();fake.wait.side_effect=subprocess.TimeoutExpired('fake',.01)
    with patch('server.subprocess.Popen',return_value=fake),patch.object(m,'stop_process') as stop:m.run(jid,'analyze')
    self.assertEqual(m.view(jid)['status'],'failed');self.assertGreaterEqual(stop.call_count,1);self.assertFalse(m.processes)
   finally:m.close()
 def test_failed_numeric_result_is_not_accepted(self):
  with tempfile.TemporaryDirectory() as td:
   m=Manager(td)
   try:
    with patch.object(m.pool,'submit'):jid=m.create('x',b'x')['id']
    p=m.jobpath(jid);m.jobs[jid]['status']='complete';write_json(p/'export.json',{'summary':{'review_status':'checks_failed','checks':{'preservation':False}}})
    v=m.view(jid);self.assertEqual(v['summary']['review_status'],'checks_failed');self.assertIs(v['summary']['checks']['preservation'],False)
   finally:m.close()
 def test_real_process_group_cleanup(self):
  # Own sleeping Python parent/child, no media, no busy loop. The parent
  # handles TERM and reaps its child. Cleanup is also tested with poll()
  # falsely reporting an exited leader, exercising the old skip bug.
  with tempfile.TemporaryDirectory() as td:
   marker=pathlib.Path(td)/'child.pid'
   code="import pathlib,signal,subprocess,sys,time\np=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\ndef done(n,f):\n p.terminate();p.wait();sys.exit(0)\nsignal.signal(signal.SIGTERM,done)\npathlib.Path(sys.argv[1]).write_text(str(p.pid))\nwhile True:time.sleep(.1)\n"
   p=subprocess.Popen([sys.executable,'-c',code,str(marker)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    deadline=time.monotonic()+3
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
    self.assertTrue(marker.exists());child=int(marker.read_text())
    proxy=MagicMock();proxy.pid=p.pid;proxy.poll.return_value=0;proxy.wait.side_effect=p.wait
    Manager.stop_process(proxy);self.assertIsNotNone(p.poll())
    self.assertFalse(pathlib.Path(f'/proc/{child}').exists(),'Child was not reaped by the owned test parent')
   finally:
    if p.poll() is None:
     os.killpg(p.pid,signal.SIGKILL);p.wait()
 def test_resource_guard_boundaries(self):
  import engine
  with tempfile.TemporaryDirectory() as td:
   for field,value in [('cpu_seconds',31),('rss_bytes',256*1024**2+1),('wall_seconds',91)]:
    with self.subTest(field=field):
     b=object.__new__(engine.Bounds);b.job=pathlib.Path(td);b.peak=0;b.cpu_cap=30;b.wall_cap=90;b.rss_cap=256*1024**2;b.disk_cap=16*1024**2;b.stop=None;b.kill=MagicMock();values={'cpu_seconds':0,'rss_bytes':1,'wall_seconds':0};values[field]=value;b.snapshot=MagicMock(return_value=values)
     with self.assertRaises(RuntimeError):b.guard()
     b.kill.assert_called_once()
if __name__=='__main__':unittest.main()
