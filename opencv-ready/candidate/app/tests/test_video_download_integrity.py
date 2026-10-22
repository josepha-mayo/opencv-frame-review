"""Synthetic bytes only; no video parsing, socket, encoding or browser."""
import io,pathlib,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from common import *
from server import Manager,Handler,Conflict,bounded_regular_bytes
class VideoDownloads(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.manager=Manager(self.tmp.name)
  with patch.object(self.manager.pool,'submit'):self.jid=self.manager.create('owned.mp4',b'owned-original')['id']
  self.path=self.manager.jobpath(self.jid);write_json(self.path/'analysis.json',{'input_sha256':sha(self.path/'input.mp4')})
  for role in ['control','edited']:(self.path/(role+'.mp4')).write_bytes(('owned-'+role).encode())
  write_json(self.path/'export.json',{'output_hashes':{r:sha(self.path/(r+'.mp4')) for r in ['control','edited']}});self.manager.jobs[self.jid]['status']='complete'
 def tearDown(self):self.manager.close();self.tmp.cleanup()
 def test_all_three_exact_validated_buffers(self):
  for name,file in [('original.mp4','input.mp4'),('control.mp4','control.mp4'),('edited.mp4','edited.mp4')]:self.assertEqual(self.manager.video_bytes(self.jid,name),(self.path/file).read_bytes())
 def test_mutated_original_control_and_edit_refused(self):
  for name,file in [('original.mp4','input.mp4'),('control.mp4','control.mp4'),('edited.mp4','edited.mp4')]:
   (self.path/file).write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'changed'):self.manager.video_bytes(self.jid,name)
 def test_declined_only_original_and_active_none(self):
  self.manager.jobs[self.jid]['status']='declined';self.assertEqual(self.manager.video_bytes(self.jid,'original.mp4'),b'owned-original')
  for name in ['control.mp4','edited.mp4']:
   with self.assertRaises(Conflict):self.manager.video_bytes(self.jid,name)
  self.manager.jobs[self.jid]['status']='exporting'
  with self.assertRaises(Conflict):self.manager.video_bytes(self.jid,'original.mp4')
 def test_missing_invalid_hash_or_filename_refused(self):
  with self.assertRaises(KeyError):self.manager.video_bytes(self.jid,'../../input.mp4')
  write_json(self.path/'export.json',{'output_hashes':{'edited':'invalid'}})
  with self.assertRaises(ValueError):self.manager.video_bytes(self.jid,'edited.mp4')
 def test_same_buffer_survives_after_read_swap(self):
  original=bounded_regular_bytes
  def swap(path,limit):
   data=original(path,limit);path.write_bytes(b'changed-after-read');return data
  with patch('server.bounded_regular_bytes',side_effect=swap):self.assertEqual(self.manager.video_bytes(self.jid,'edited.mp4'),b'owned-edited')
  with self.assertRaises(ValueError):self.manager.video_bytes(self.jid,'edited.mp4')
 def test_symlink_fifo_oversize_refused(self):
  import os,time
  p=self.path/'edited.mp4';p.unlink();p.symlink_to(self.path/'control.mp4')
  with self.assertRaises(OSError):self.manager.video_bytes(self.jid,'edited.mp4')
  p.unlink();os.mkfifo(p);start=time.monotonic()
  with self.assertRaises(ValueError):self.manager.video_bytes(self.jid,'edited.mp4')
  self.assertLess(time.monotonic()-start,1);p.unlink()
  with p.open('wb') as f:f.truncate(32*1024**2+1)
  with self.assertRaises(ValueError):self.manager.video_bytes(self.jid,'edited.mp4')
 def test_handler_writes_exact_verified_bytes_with_attachment(self):
  sent=[];headers=[];fake=SimpleNamespace(server=SimpleNamespace(manager=self.manager),send_response=sent.append,headers_safe=lambda *x:headers.append(x),wfile=io.BytesIO())
  Handler.verified_video(fake,self.jid,'edited.mp4');self.assertEqual(sent,[200]);self.assertEqual(fake.wfile.getvalue(),b'owned-edited');self.assertEqual(headers,[('video/mp4',12,'edited.mp4')])
  (self.path/'edited.mp4').write_bytes(b'changed');sent.clear()
  with self.assertRaises(ValueError):Handler.verified_video(fake,self.jid,'edited.mp4')
  self.assertEqual(sent,[])
if __name__=='__main__':unittest.main(verbosity=2)
