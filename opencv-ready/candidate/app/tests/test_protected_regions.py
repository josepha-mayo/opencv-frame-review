"""Synthetic fixed-area/approval checks. No media encoding or browser use."""
import copy,hashlib,pathlib,sys,tempfile,unittest
from unittest.mock import patch
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
import engine as e
from common import *
from server import Manager,Conflict
from protected_regions import RegionMeasure,validate_regions

def component():return {'interval':[.4,2.3],'mask_shape':[180,320],'mask_rle':[[100,64]],'area':64,'bbox':[100,0,64,1]}
def region():return [{'label':'Instruction','xywh':[5,20,20,10]}]
class Regions(unittest.TestCase):
 def test_validation_refuses_invalid_coordinates_and_labels(self):
  for bad in [None,[],[0,0,True,2],[0,0,1.0,2],[-1,0,2,2],[319,179,2,2],[0,0,0,2]]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate_regions([{'label':'A','xywh':bad}],[180,320])
  for bad in ['','a'*41,'line\nbreak',7]:
   with self.assertRaises(ValueError):validate_regions([{'label':bad,'xywh':[0,0,2,2]}],[180,320])
  with self.assertRaises(ValueError):validate_regions(region()*5,[180,320])
  with self.assertRaises(ValueError):validate_regions(region()*2,[180,320])
 def test_overlap_exact_rle_not_bounding_box(self):
  self.assertEqual(validate_regions(region(),[180,320],component()['mask_rle']),region())
  with self.assertRaisesRegex(ValueError,'overlaps'):validate_regions([{'label':'A','xywh':[105,0,2,1]}],[180,320],component()['mask_rle'])
  self.assertEqual(len(validate_regions([{'label':'A','xywh':[164,0,2,1]}],[180,320],component()['mask_rle'])),1)
 def test_no_region_is_not_a_pass_claim(self):
  m=RegionMeasure([],e.np,e.cv2);a=e.np.zeros((10,20,3),e.np.uint8);m.add(a,a)
  self.assertIsNone(m.result()['passed']);self.assertFalse(m.result()['declared'])
 def test_single_changed_code_fails_max_even_when_mean_and_p99_pass(self):
  m=RegionMeasure([{'label':'A','xywh':[0,0,20,10]}],e.np,e.cv2);a=e.np.zeros((10,20,3),e.np.uint8);b=a.copy();b[2,3,1]=4;m.add(a,b);r=m.result();v=r['regions'][0]['measurements']
  self.assertLess(v['mean_rgb_code_error'],.1);self.assertEqual(v['p99_rgb_code_error'],0);self.assertEqual(v['max_rgb_code_error'],4);self.assertFalse(r['passed'])
 def test_every_frame_and_region_counted(self):
  m=RegionMeasure([{'label':'A','xywh':[0,0,2,2]},{'label':'B','xywh':[2,0,2,2]}],e.np,e.cv2);a=e.np.zeros((2,4,3),e.np.uint8)
  m.add(a,a);b=a.copy();b[0,3,0]=9;m.add(a,b);r=m.result();self.assertEqual(r['frames'],2);self.assertTrue(r['regions'][0]['passed']);self.assertFalse(r['regions'][1]['passed']);self.assertEqual(r['regions'][1]['channel_samples'],24)
 def test_engine_measure_keeps_the_new_measurement(self):
  a=e.np.zeros((10,20,3),e.np.uint8);b=a.copy();b[2,3,1]=4;mask=e.np.zeros((10,20),e.np.uint8);mask[0,0]=255
  q=e.measure([a],iter([a]),iter([b]),mask,0,0,protected_regions=[{'label':'A','xywh':[2,2,3,3]}])
  self.assertFalse(q['protected_content']['passed']);self.assertEqual(q['protected_content']['regions'][0]['measurements']['max_rgb_code_error'],4)
 def test_contract_is_approval_bound(self):
  c=component();r=proposed_recipe('a','b','0',c,region());a={'approve':True,'candidate_id':'0','protected_regions':region(),'recipe':r,'recipe_sha256':hashlib.sha256(canonical(r)).hexdigest()}
  self.assertEqual(validate_approval(a,'a','b',c),r);self.assertIn('protected_regions.py',r['implementation_sha256'])
  for kind in ['coordinates','label','criterion','missing']:
   b=copy.deepcopy(a)
   if kind=='coordinates':b['protected_regions'][0]['xywh'][0]+=1
   if kind=='label':b['protected_regions'][0]['label']='Changed'
   if kind=='criterion':b['recipe']['protected_criteria']['max_rgb_code_error']=4
   if kind=='missing':b.pop('protected_regions')
   with self.subTest(kind=kind),self.assertRaises(ValueError):validate_approval(b,'a','b',c)
class Plans(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.m=Manager(self.tmp.name);self.submit=patch.object(self.m.pool,'submit');self.submit.start();self.jid=self.m.create('owned',b'owned input')['id'];self.path=self.m.jobpath(self.jid)
  write_json(self.path/'source.probe.json',{'metadata':{'streams':[{'codec_type':'video'}]}})
  c=component();write_json(self.path/'prediction.json',{'components':[c]});a={'input_profile':media_profile([180,320]),'input_sha256':sha(self.path/'input.mp4'),'prediction_sha256':sha(self.path/'prediction.json'),'message':'review','candidates':[{'id':'0','recipe_sha256':hashlib.sha256(canonical(proposed_recipe(sha(self.path/'input.mp4'),sha(self.path/'prediction.json'),'0',c))).hexdigest()}]};write_json(self.path/'analysis.json',a);self.m.jobs[self.jid]['status']='review';self.m.save(self.jid);self.body={'candidate_id':'0','prediction_sha256':a['prediction_sha256'],'protected_regions':region()}
 def tearDown(self):self.submit.stop();self.m.close();self.tmp.cleanup()
 def test_plan_does_not_approve_and_exact_choice_can_approve(self):
  plan=self.m.plan(self.jid,self.body);self.assertEqual(self.m.jobs[self.jid]['status'],'review');self.assertFalse((self.path/'approval.json').exists())
  b=dict(self.body,approve=True,recipe_sha256=plan['recipe_sha256']);self.m.approve(self.jid,b);stored=read_json(self.path/'approval.json');self.assertEqual(stored['recipe']['protected_regions'],region());self.assertEqual(stored['protected_regions'],region())
 def test_stale_plan_and_changed_input_refuse(self):
  plan=self.m.plan(self.jid,self.body);b=copy.deepcopy(self.body);b.update(approve=True,recipe_sha256=plan['recipe_sha256']);b['protected_regions'][0]['xywh'][0]+=1
  with self.assertRaises(Conflict):self.m.approve(self.jid,b)
  self.assertFalse((self.path/'approval.json').exists());(self.path/'input.mp4').write_bytes(b'changed')
  with self.assertRaises(Conflict):self.m.plan(self.jid,self.body)
 def test_overlap_plan_refuses(self):
  self.body['protected_regions']=[{'label':'A','xywh':[105,0,2,1]}]
  with self.assertRaisesRegex(ValueError,'overlaps'):self.m.plan(self.jid,self.body)
if __name__=='__main__':unittest.main(verbosity=2)
