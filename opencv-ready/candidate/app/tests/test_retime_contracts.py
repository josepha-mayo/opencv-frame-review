import hashlib,json,pathlib,unittest
from common import proposed_recipe,validate_approval,canonical
from retime import MAX_PERIOD,MIN_CYCLES,MAX_REPEAT_FRAME_MAE,MAX_REPEAT_SAMPLE_ERROR,MIN_LUMA_RANGE
ROOT=pathlib.Path(__file__).resolve().parents[1]
class RetimeContracts(unittest.TestCase):
 def setUp(self):
  self.component={'mask_shape':[180,320],'mask_rle':[[5000,20]],'interval':[.4,2.3]}
 def test_explicit_bound_mode_and_policy(self):
  r=proposed_recipe('a'*64,'b'*64,'0',self.component,[],export_mode='periodic-local-retime-v2')
  self.assertEqual(r['edit']['factor'],5);p=r['edit']['cycle_policy']
  self.assertEqual((p['max_period_frames'],p['minimum_cycles'],p['max_repeat_plane_frame_mae'],p['max_repeat_sample_error'],p['min_luma_mean_range']),(MAX_PERIOD,MIN_CYCLES,MAX_REPEAT_FRAME_MAE,MAX_REPEAT_SAMPLE_ERROR,MIN_LUMA_RANGE))
  self.assertTrue(all(v==0 for v in r['protected_criteria'].values()))
  self.assertTrue({'retime.py','retime_export.py','acceptance.py'}.issubset(r['implementation_sha256']))
  a={'candidate_id':'0','approve':True,'protected_regions':[],'recipe':r,'recipe_sha256':hashlib.sha256(canonical(r)).hexdigest()}
  self.assertEqual(validate_approval(a,'a'*64,'b'*64,self.component),r)
  a['recipe']['edit']['factor']=2
  with self.assertRaises(ValueError):validate_approval(a,'a'*64,'b'*64,self.component)
 def test_mode_change_invalidates_recipe(self):
  r=proposed_recipe('a'*64,'b'*64,'0',self.component,[],export_mode='periodic-local-retime-v2')
  legacy=proposed_recipe('a'*64,'b'*64,'0',self.component,[],export_mode='legacy')
  self.assertNotEqual(canonical(r),canonical(legacy))
 def test_ui_scope_and_no_autoplay(self):
  html=(ROOT/'static/index.html').read_text();js=(ROOT/'static/app.js').read_text()
  for text in ('periodic-local-retime-v2','Slow periodic decoration 5×','Optional AAC-LC mono 48 kHz only','every sample difference ≤32','every outside-mask pixel must be exact','refuses the edited download on failure'):
   self.assertIn(text,html)
  self.assertNotIn('<video',html);self.assertNotIn('autoplay=',html)
  self.assertIn('protectionPlan = null; // Every retiming mode',js)
  self.assertIn('region.criteria.max_rgb_code_error',js)
 def test_only_accepted_filename_has_download_route(self):
  from server import DOWNLOADS
  self.assertNotIn('pending-candidate.mp4',DOWNLOADS)
  self.assertNotIn('rejected-candidate.mp4',DOWNLOADS)

if __name__=='__main__':unittest.main()
