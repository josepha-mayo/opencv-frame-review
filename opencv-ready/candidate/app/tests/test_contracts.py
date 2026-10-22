import copy, hashlib, json, pathlib, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from unittest.mock import patch, MagicMock
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from common import *
from server import Manager, Conflict, make_server

def stream():return {'codec_type':'video','codec_name':'h264','pix_fmt':'yuv420p','width':320,'height':180,'color_range':'tv','color_space':'bt709','color_transfer':'bt709','color_primaries':'bt709','chroma_location':'left','r_frame_rate':'30/1','avg_frame_rate':'30/1','time_base':'1/15360','nb_frames':'90','duration':'3.000000'}
def component():return {'interval':[.4,2.3],'mask_shape':[180,320],'mask_rle':[[100,64]],'area':64,'bbox':[100,0,64,1]}
class Admission(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate_probe({'streams':[stream()]})['width'],320)
 def test_larger_profile_is_explicit(self):
  s=stream();s.update(width=640,height=360,nb_frames='180',duration='6.000000')
  self.assertEqual(validate_probe({'streams':[s]})['width'],640)
  s['nb_frames']='90'
  with self.assertRaises(ValueError):validate_probe({'streams':[s]})
 def test_larger_frame_timing(self):
  d={'frames':[{'best_effort_timestamp':512*i} for i in range(180)]}
  self.assertEqual(len(validate_frames(d,180)),180)
  with self.assertRaises(ValueError):validate_frames(d)
 def test_reject_fields(self):
  for key,value in [('width',1920),('height',1080),('nb_frames','999999'),('duration','NaN'),('duration','inf'),('duration','4'),('color_transfer',None),('color_primaries','bt2020'),('color_range','pc'),('pix_fmt','yuv420p10le'),('r_frame_rate','60/1')]:
   with self.subTest(field=key,value=value):
    s=stream();s[key]=value
    with self.assertRaises(ValueError):validate_probe({'streams':[s]})
 def test_audio_and_rotation(self):
  with self.assertRaises(ValueError):validate_probe({'streams':[stream(),{'codec_type':'audio'}]})
  s=stream();s['side_data_list']=[{'rotation':90}]
  with self.assertRaises(ValueError):validate_probe({'streams':[s]})
 def test_frame_timing(self):
  d={'frames':[{'best_effort_timestamp':512*i} for i in range(90)]};self.assertEqual(len(validate_frames(d)),90)
  d['frames'][12]['best_effort_timestamp']=float('nan')
  with self.assertRaises(ValueError):validate_frames(d)
 def test_incomplete_frames(self):
  with self.assertRaises(ValueError):validate_frames({'frames':[]})
 def test_filename(self):self.assertEqual(safe_name('../../x;echo.txt'),'x_echo.txt')
class Approval(unittest.TestCase):
 def test_approval_binding(self):
  c=component();r=proposed_recipe('a','b','0',c);a={'approve':True,'candidate_id':'0','recipe':r,'recipe_sha256':hashlib.sha256(canonical(r)).hexdigest()};self.assertEqual(validate_approval(a,'a','b',c),r)
  for change in ['input','prediction','recipe','approval']:
   b=copy.deepcopy(a)
   if change=='recipe':b['recipe']['edit']['step_frames']=1
   if change=='approval':b['approve']=False
   with self.assertRaises(ValueError):validate_approval(b,'different' if change=='input' else 'a','different' if change=='prediction' else 'b',c)
 def test_interval_bounds(self):
  c=component();c['interval']=[-1,4]
  with self.assertRaises(ValueError):proposed_recipe('a','b','0',c)
class Server(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,self.tmp.name);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_address[1])
 def tearDown(self):self.server.shutdown();self.server.manager.close();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def req(self,path,data=None,headers=None):
  r=urllib.request.Request(self.url+path,data=data,headers=headers or {})
  return urllib.request.urlopen(r,timeout=5)
 def test_profile_and_no_token(self):
  d=json.load(self.req('/api/profile'));self.assertIn('csrf_token',d)
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('/api/jobs',b'bad')
  self.assertEqual(e.exception.code,403)
 def test_origin_and_host(self):
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/profile',headers={'Origin':'http://evil.invalid'})
  with self.assertRaises(urllib.error.HTTPError):self.req('/api/profile',headers={'Host':'evil.invalid'})
 def test_path_traversal(self):
  with self.assertRaises(urllib.error.HTTPError):self.req('/static/../common.py')
 def test_no_implicit_edit(self):
  m=self.server.manager
  with patch.object(m.pool,'submit') as submit:
   d=m.create('owned.mp4',b'owned');jid=d['id'];self.assertEqual(d['status'],'queued');self.assertEqual(submit.call_args.args[2],'analyze');self.assertFalse((m.jobpath(jid)/'approval.json').exists())
   with self.assertRaises(Conflict):m.approve(jid,{'approve':True})
   m.cancel(jid);self.assertEqual(m.view(jid)['status'],'cancelled')
 def test_decline_preserves_input(self):
  m=self.server.manager
  with patch.object(m.pool,'submit'):
   d=m.create('owned.mp4',b'owned');jid=d['id'];p=m.jobpath(jid);digest=sha(p/'input.mp4');m.jobs[jid]['status']='review';m.save(jid);m.decline(jid);self.assertEqual(sha(p/'input.mp4'),digest);self.assertEqual(m.view(jid)['status'],'declined');self.assertFalse((p/'edited.mp4').exists())
 def test_worker_launch_failure_is_terminal(self):
  m=self.server.manager
  with patch.object(m.pool,'submit'):
   jid=m.create('owned.mp4',b'owned')['id']
  with patch('server.subprocess.Popen',side_effect=OSError('injected launch failure')):m.run(jid,'analyze')
  self.assertEqual(m.view(jid)['status'],'failed');self.assertIn('injected launch failure',m.view(jid)['error']);self.assertFalse(m.processes)
 def test_bind_failure_closes_manager(self):
  with patch('server.Manager') as manager,patch('server.http.server.ThreadingHTTPServer',side_effect=OSError('injected bind failure')):
   with self.assertRaises(OSError):make_server(0,self.tmp.name)
   manager.return_value.close.assert_called_once()
 def test_cancel_stops_even_if_save_fails(self):
  m=self.server.manager
  with patch.object(m.pool,'submit'):jid=m.create('x',b'x')['id']
  process=MagicMock();m.processes[jid]=process
  with patch.object(m,'save',side_effect=OSError('injected disk full')),patch.object(m,'stop_process') as stop:
   result=m.cancel(jid);stop.assert_called_once_with(process);self.assertEqual(result['status'],'cancelled')
  m.processes.pop(jid,None)
 def test_shutdown_stops_even_if_save_fails(self):
  m=object.__new__(Manager);m.lock=threading.RLock();m.jobs={'fake':{'status':'analyzing'}};process=MagicMock();m.processes={'fake':process};m.pool=MagicMock();m.save=MagicMock(side_effect=OSError('injected disk full'));m.stop_process=MagicMock()
  errors=m.close();m.stop_process.assert_called_once_with(process);m.pool.shutdown.assert_called_once_with(wait=True,cancel_futures=True);self.assertTrue(errors)
 def test_oversize_before_job(self):
  with self.assertRaises(ValueError):self.server.manager.create('x',b'x'*(MAX_INPUT+1))
  self.assertFalse(self.server.manager.jobs)
if __name__=='__main__':unittest.main()
