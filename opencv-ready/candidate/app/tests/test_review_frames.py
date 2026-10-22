"""Synthetic pixel/unit contracts; no video processing or browser inference."""
import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
import engine as e
from common import *
from review_frames import ReviewFrames,boundary_rows
from server import Manager,make_server,bounded_regular_bytes,verified_image_bytes

class BoundaryFrames(unittest.TestCase):
 def binding(self):return {'input_sha256':'a'*64,'prediction_sha256':'b'*64,'recipe_sha256':'c'*64,'output_hashes':{'control':'d'*64,'edited':'e'*64}}
 def test_boundary_rows_and_loop_edges(self):
  rows=boundary_rows(2,5,[i/30 for i in range(8)]);self.assertEqual([r['frame'] for r in rows],[1,2,5,6]);self.assertFalse(any(r['loop_wrap'] for r in rows))
  rows=boundary_rows(0,7,[i/30 for i in range(8)]);self.assertEqual([r['frame'] for r in rows],[7,0,7,0]);self.assertEqual([r['loop_wrap'] for r in rows],[True,False,False,True])
 def test_invalid_timestamps_interval(self):
  for lo,hi,ts in [(-1,2,[0,1,2]),(0,3,[0,1,2]),(0,1,[0,float('nan')]),(0,1,[0,0])]:
   with self.assertRaises(ValueError):boundary_rows(lo,hi,ts)
 def test_pixel_alignment_lossless_hashes_and_no_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   mask=e.np.zeros((40,50),e.np.uint8);mask[20:22,25:28]=255;r=ReviewFrames(td,mask,2,5,[i/30 for i in range(8)]);self.assertEqual(r.crop,[9,4,35,34])
   for t in range(8):
    frames=[e.np.full((40,50,3),[t,t+name+20,name+100],e.np.uint8) for name in range(3)];before=[a.tobytes() for a in frames];r.capture(t,*frames);self.assertEqual(before,[a.tobytes() for a in frames])
   data=r.finish(self.binding(),{'newly_timed':False,'control_delta':0.,'edited_delta':0.,'criterion':.1})
   for row in data['rows']:
    for n,name in enumerate(['original','control','edited']):
     item=row['images'][name];p=pathlib.Path(td)/item['filename'];rgb=e.cv2.cvtColor(e.cv2.imread(str(p)),e.cv2.COLOR_BGR2RGB);self.assertTrue(e.np.all(rgb==[row['frame'],row['frame']+n+20,n+100]));self.assertEqual(sha(p),item['sha256']);self.assertEqual(hashlib.sha256(rgb.tobytes()).hexdigest(),item['decoded_crop_rgb_sha256'])
 def test_incomplete_duplicate_or_bad_binding_refused(self):
  with tempfile.TemporaryDirectory() as td:
   a=e.np.zeros((2,2,3),e.np.uint8);m=e.np.ones((2,2),e.np.uint8);r=ReviewFrames(td,m,1,2,[i/30 for i in range(4)])
   with self.assertRaises(ValueError):r.finish(self.binding(),{})
   r.capture(0,a,a,a)
   with self.assertRaises(ValueError):r.capture(0,a,a,a)
   for t in [1,2,3]:r.capture(t,a,a,a)
   bad=self.binding();bad['input_sha256']='invalid'
   with self.assertRaises(ValueError):r.finish(bad,{})
 def test_measure_numbers_unchanged_with_capture(self):
  with tempfile.TemporaryDirectory() as td:
   source=[e.np.full((3,4,3),t*10,e.np.uint8) for t in range(12)];mask=e.np.zeros((3,4),e.np.uint8);mask[1,1]=255
   expected=e.measure(source,iter(source),e.edited_frames(source,mask,3,8),mask,3,8)
   review=ReviewFrames(td,mask,3,8,[i/30 for i in range(12)])
   actual=e.measure(source,iter(source),e.edited_frames(source,mask,3,8),mask,3,8,review)
   self.assertEqual(expected,actual);self.assertEqual(len(review.finish(self.binding(),{})['rows']),4)

class ReviewServing(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.m=Manager(self.tmp.name)
  with patch.object(self.m.pool,'submit'):self.jid=self.m.create('owned.mp4',b'original')['id']
  self.path=self.m.jobpath(self.jid)
  for name in ['control','edited']:(self.path/(name+'.mp4')).write_bytes(name.encode())
  spec=e.media_profile([180,320],30);recipe={'input_profile':spec};recipe_sha=hashlib.sha256(e.canonical(recipe)).hexdigest()
  analysis={'input_profile':spec,'input_sha256':sha(self.path/'input.mp4'),'prediction_sha256':'b'*64,'message':'test','candidates':[]};write_json(self.path/'analysis.json',analysis);write_json(self.path/'approval.json',{'recipe':recipe,'recipe_sha256':recipe_sha})
  binding={k:analysis[k] for k in ['input_sha256','prediction_sha256']};binding.update(recipe_sha256=recipe_sha,output_hashes={n:sha(self.path/(n+'.mp4')) for n in ['control','edited']})
  mask=e.np.ones((2,2),e.np.uint8);r=ReviewFrames(self.path,mask,1,2,[i/30 for i in range(4)])
  for t in range(4):
   a=e.np.full((2,2,3),t,e.np.uint8);r.capture(t,a,a,a)
  write_json(self.path/'frame-review.json',r.finish(binding,{}));write_json(self.path/'export.json',{'summary':{'review_status':'needs_creator_review'},'output_hashes':binding['output_hashes'],'frame_review_sha256':sha(self.path/'frame-review.json')});self.m.jobs[self.jid]['status']='complete'
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def test_manifest_binding_and_original_first(self):
  view=self.m.view(self.jid);self.assertEqual(next(iter(view['artifacts'])),'Original input');self.assertEqual(len(view['frame_review']['rows']),4);image=view['frame_review']['rows'][0]['images']['original'];self.assertEqual(image['url'],f'/api/jobs/{self.jid}/review/{image["filename"]}')
 def test_modified_png_not_exposed(self):
  (self.path/'boundary-f00000-original.png').write_bytes(b'changed');v=self.m.view(self.jid);self.assertNotIn('frame_review',v);self.assertIn('image changed',v['frame_review_error'])
 def test_modified_media_not_exposed(self):
  (self.path/'edited.mp4').write_bytes(b'changed');v=self.m.view(self.jid);self.assertNotIn('frame_review',v);self.assertIn('media changed',v['frame_review_error'])
 def test_modified_manifest_not_exposed(self):
  with (self.path/'frame-review.json').open('a') as f:f.write(' ')
  v=self.m.view(self.jid);self.assertNotIn('frame_review',v);self.assertIn('manifest changed',v['frame_review_error'])
 def test_http_image_requires_completed_intact_binding(self):
  import threading,urllib.request,urllib.error
  self.m.save(self.jid);server=make_server(0,self.tmp.name);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_address[1])+f'/api/jobs/{self.jid}/review/boundary-f00000-original.png'
  try:
   with urllib.request.urlopen(url,timeout=3) as response:self.assertEqual(response.read(),(self.path/'boundary-f00000-original.png').read_bytes());self.assertEqual(response.headers['Content-Type'],'image/png')
   server.manager.jobs[self.jid]['status']='review'
   with self.assertRaises(urllib.error.HTTPError) as ex:urllib.request.urlopen(url,timeout=3)
   self.assertEqual(ex.exception.code,409);server.manager.jobs[self.jid]['status']='complete'
   (self.path/'boundary-f00000-original.png').write_bytes(b'changed')
   with self.assertRaises(urllib.error.HTTPError) as ex:urllib.request.urlopen(url,timeout=3)
   self.assertEqual(ex.exception.code,400)
  finally:server.shutdown();server.manager.close();server.server_close();thread.join()
 def test_valid_image_swapped_after_validation_is_refused(self):
  import threading,urllib.request,urllib.error
  self.m.save(self.jid);server=make_server(0,self.tmp.name);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_address[1])+f'/api/jobs/{self.jid}/review/boundary-f00000-original.png'
  original=server.manager.frame_review
  def swapped(jid):
   result=original(jid);(self.path/'boundary-f00000-original.png').write_bytes((self.path/'boundary-f00001-original.png').read_bytes());return result
  try:
   with patch.object(server.manager,'frame_review',side_effect=swapped):
    with self.assertRaises(urllib.error.HTTPError) as ex:urllib.request.urlopen(url,timeout=3)
    self.assertEqual(ex.exception.code,400);self.assertIn(b'changed before serving',ex.exception.read())
  finally:server.shutdown();server.manager.close();server.server_close();thread.join()
 def test_manifest_parses_the_same_bytes_that_were_hashed(self):
  target=self.path/'frame-review.json';original=bounded_regular_bytes;reads=[]
  def changed_after_read(path,limit):
   value=original(path,limit)
   if path==target:
    reads.append(1);path.write_text('{"tampered":true}')
   return value
  with patch('server.bounded_regular_bytes',side_effect=changed_after_read):review=self.m.frame_review(self.jid)
  self.assertEqual(len(reads),1);self.assertEqual(review['schema'],'encoded-boundaries-v1')
  with self.assertRaises(ValueError):self.m.frame_review(self.jid)
 def test_nonregular_or_oversized_image_is_bounded_refusal(self):
  import os,time
  huge=self.path/'oversized.png'
  with huge.open('wb') as out:out.truncate(4*1024**2+1)
  with self.assertRaises(ValueError):verified_image_bytes(huge,'a'*64)
  fifo=self.path/'pipe.png';os.mkfifo(fifo);start=time.monotonic()
  with self.assertRaises(ValueError):verified_image_bytes(fifo,'a'*64)
  self.assertLess(time.monotonic()-start,1.)
  link=self.path/'link.png';link.symlink_to(self.path/'boundary-f00000-original.png')
  with self.assertRaises(OSError):verified_image_bytes(link,'a'*64)
 def test_review_implementation_is_approval_bound(self):
  component={'interval':[.4,2.3],'mask_shape':[180,320]};r=proposed_recipe('a','b','0',component);self.assertEqual(r['implementation_sha256']['review_frames.py'],sha(APP/'review_frames.py'))
if __name__=='__main__':unittest.main(verbosity=2)
