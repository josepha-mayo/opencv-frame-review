"""Duration admission must remain exact and approval-bound."""
import copy,hashlib,unittest
from test_contracts import stream,component
from common import *
from audio_preserve import validate_streams
class DurationContract(unittest.TestCase):
 def test_every_admitted_count_at_both_shapes(self):
  for w,h in [(320,180),(640,360)]:
   for n in range(30,361,3):
    s=stream();s.update(width=w,height=h,nb_frames=str(n),duration=f'{n/30:.6f}')
    self.assertEqual(validate_probe({'streams':[s]})['nb_frames'],str(n))
    self.assertEqual(len(validate_frames({'frames':[{'best_effort_timestamp':i*512} for i in range(n)]},n)),n)
 def test_counts_fail_closed(self):
  for n in ['0','1','27','29','31','359','361','363','999','30.0',30,None,True]:
   s=stream();s.update(nb_frames=n,duration='1')
   with self.subTest(n=n),self.assertRaises(ValueError):validate_probe({'streams':[s]})
 def test_duration_and_timestamps_stay_exact(self):
  s=stream();s.update(nb_frames='123',duration='4.1000011')
  with self.assertRaises(ValueError):validate_probe({'streams':[s]})
  pts=[{'best_effort_timestamp':i*512} for i in range(360)];pts[-1]['best_effort_timestamp']+=1
  with self.assertRaises(ValueError):validate_frames({'frames':pts},360)
 def test_long_recipe_is_explicitly_bound(self):
  c=component();c['interval']=[.4,11.3];spec=media_profile([180,320],360)
  r=proposed_recipe('a','b','0',c,export_mode='periodic-local-retime-v2',input_profile=spec)
  a={'approve':True,'candidate_id':'0','recipe':r,'recipe_sha256':hashlib.sha256(canonical(r)).hexdigest()}
  self.assertEqual(validate_approval(a,'a','b',c,spec),r)
  for n in [90,357]:
   with self.assertRaises(ValueError):validate_approval(a,'a','b',c,media_profile([180,320],n))
  bad=copy.deepcopy(spec);bad['duration_seconds']=11
  with self.assertRaises(ValueError):proposed_recipe('a','b','0',c,input_profile=bad)
 def test_fractional_audio_uses_integral_ticks(self):
  a={'codec_type':'audio','codec_name':'aac','profile':'LC','codec_tag_string':'mp4a','sample_rate':'48000','channels':1,'channel_layout':'mono','time_base':'1/48000','start_pts':0,'duration_ts':196800}
  self.assertTrue(validate_streams({'streams':[{'codec_type':'video'},a]},4.1))
  a['duration_ts']-=1
  with self.assertRaises(ValueError):validate_streams({'streams':[{'codec_type':'video'},a]},4.1)
if __name__=='__main__':unittest.main()
