"""Ordered motion receipts and real lossless PNG proofs, not media qualification."""
from pathlib import Path
import hashlib,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from teaching_motion import TeachingMotion
try:
    import numpy as np,cv2
except ImportError:np=None

@unittest.skipIf(np is None,'Pinned numerical runtime required')
class TeachingProof(unittest.TestCase):
    def frames(self):return [np.full((6,8,3),t*10,np.uint8) for t in range(8)]
    def collector(self):return TeachingMotion([{'label':'Live progress','xywh':[2,1,4,3]}],[1,6],8,np)
    def test_changing_protected_content_retains_exact_order_and_activity(self):
        c=self.collector()
        for t,f in enumerate(self.frames()):c.add(t,f,f.copy())
        row=c.result()['regions'][0]
        self.assertTrue(row['ordered_rgb_sequence_exact'])
        self.assertEqual(row['changed_pairs_inside_hold'],{'source':5,'edited':5})
        self.assertEqual(row['changed_adjacent_frame_pairs'],{'source':7,'edited':7})
        self.assertEqual(row['mean_absolute_temporal_rgb_codes'],{'source':10,'edited':10})
    def test_freezing_protected_progress_cannot_pass_ordered_digest(self):
        c=self.collector();frames=self.frames()
        for t,f in enumerate(frames):c.add(t,f,frames[1] if 1<=t<=6 else f)
        row=c.result()['regions'][0]
        self.assertFalse(row['ordered_rgb_sequence_exact']);self.assertEqual(row['changed_pairs_inside_hold']['edited'],0)
    def test_same_activity_count_does_not_hide_reordered_content(self):
        c=self.collector();frames=self.frames()
        for t,f in enumerate(frames):c.add(t,f,frames[-1-t])
        row=c.result()['regions'][0]
        self.assertEqual(row['changed_adjacent_frame_pairs']['source'],row['changed_adjacent_frame_pairs']['edited'])
        self.assertFalse(row['ordered_rgb_sequence_exact'])
    def test_missing_or_out_of_order_frame_refuses_proof(self):
        c=self.collector();f=self.frames()[0]
        with self.assertRaisesRegex(ValueError,'ordered'):c.add(1,f,f)
        c.add(0,f,f)
        with self.assertRaisesRegex(ValueError,'lacks'):c.result()
    def test_actual_png_bytes_and_decoded_pixels_match_the_selected_moments(self):
        c=self.collector();frames=self.frames()
        for t,f in enumerate(frames):c.add(t,f,f)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proof=c.write_review(root,cv2,{'input_sha256':'source-binding'})
            self.assertEqual(proof['input_sha256'],'source-binding')
            moments=proof['regions'][0]['moments'];self.assertEqual(len(moments),3)
            for moment in moments:
                expected=frames[moment['frame']][1:4,2:6]
                for role,asset in moment['images'].items():
                    raw=(root/asset['filename']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),asset['sha256'])
                    actual=cv2.cvtColor(cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
                    self.assertTrue(np.array_equal(actual,expected));self.assertEqual(hashlib.sha256(actual.tobytes()).hexdigest(),asset['decoded_rgb_sha256'])
    def test_only_three_moments_remain_when_peak_changes_late(self):
        c=self.collector();frames=self.frames()
        for t,f in enumerate(frames):
            f=np.full_like(f,t*t*4);c.add(t,f,f)
        self.assertLessEqual(len(c.rows[0]['moments']),3)
        self.assertEqual(sorted(c.rows[0]['moments']),[1,6])
    def test_static_region_does_not_invent_teaching_motion(self):
        c=self.collector();f=self.frames()[0]
        for t in range(8):c.add(t,f,f)
        row=c.result()['regions'][0];self.assertEqual(row['changed_pairs_inside_hold'],{'source':0,'edited':0});self.assertEqual(row['peak_change_mean_rgb_codes'],0)

if __name__=='__main__':unittest.main()
