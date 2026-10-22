"""Serving duration is bound to the approved clip, never a global maximum."""
import copy,hashlib
from test_review_frames import ReviewServing
from common import media_profile,canonical,read_json,write_json,sha
class ReviewDurationBounds(ReviewServing):
 def set_profile(self,n):
  spec=media_profile([180,320],n);a=read_json(self.path/'analysis.json');a['input_profile']=spec;write_json(self.path/'analysis.json',a)
  approval={'recipe':{'input_profile':spec}};approval['recipe_sha256']=hashlib.sha256(canonical(approval['recipe'])).hexdigest();write_json(self.path/'approval.json',approval)
  review=read_json(self.path/'frame-review.json');review['recipe_sha256']=approval['recipe_sha256'];self.save_review(review)
 def save_review(self,review):
  write_json(self.path/'frame-review.json',review);export=read_json(self.path/'export.json');export['frame_review_sha256']=sha(self.path/'frame-review.json');write_json(self.path/'export.json',export)
 def row_at(self,n):
  review=read_json(self.path/'frame-review.json');row=review['rows'][-1];row['frame']=n;row['seconds']=n/30
  for role,image in row['images'].items():
   old=self.path/image['filename'];image['filename']=f'boundary-f{n:05d}-{role}.png';(self.path/image['filename']).write_bytes(old.read_bytes())
  self.save_review(review)
 def test_frame_359_served_for_360_frame_approved_input(self):
  self.set_profile(360);self.row_at(359);self.assertEqual(self.m.frame_review(self.jid)['rows'][-1]['frame'],359)
 def test_frame_30_not_served_for_30_frame_input(self):
  self.set_profile(30);self.row_at(30)
  with self.assertRaisesRegex(ValueError,'Invalid static review row'):self.m.frame_review(self.jid)
 def test_frame_360_not_served_for_360_frame_input(self):
  self.set_profile(360);self.row_at(360)
  with self.assertRaisesRegex(ValueError,'Invalid static review row'):self.m.frame_review(self.jid)
 def test_analysis_cannot_expand_approved_length(self):
  self.set_profile(30);a=read_json(self.path/'analysis.json');a['input_profile']=media_profile([180,320],360);write_json(self.path/'analysis.json',a)
  with self.assertRaisesRegex(ValueError,'profile mismatch'):self.m.frame_review(self.jid)
 def test_recipe_length_change_invalidates_hash(self):
  self.set_profile(30);a=read_json(self.path/'approval.json');a['recipe']['input_profile']=media_profile([180,320],360);write_json(self.path/'approval.json',a)
  with self.assertRaisesRegex(ValueError,'recipe changed'):self.m.frame_review(self.jid)
 def test_missing_profile_refused(self):
  self.set_profile(30);a=read_json(self.path/'analysis.json');a.pop('input_profile');write_json(self.path/'analysis.json',a)
  with self.assertRaisesRegex(ValueError,'profile mismatch'):self.m.frame_review(self.jid)
 def test_approval_swap_cannot_change_review_bound_profile(self):
  from unittest.mock import patch
  import server
  self.set_profile(30)
  a=read_json(self.path/'analysis.json');a['input_profile']=media_profile([180,320],360);write_json(self.path/'analysis.json',a)
  original=server.read_json;count=0
  new_recipe={'input_profile':media_profile([180,320],360)}
  def swapped(path):
   nonlocal count
   result=original(path)
   if path==self.path/'approval.json':
    count+=1
    if count==2:return {'recipe':new_recipe,'recipe_sha256':hashlib.sha256(canonical(new_recipe)).hexdigest()}
   return result
  with patch.object(server,'read_json',side_effect=swapped):
   with self.assertRaises(ValueError):self.m.frame_review(self.jid)
