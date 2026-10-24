"""Stationary detail tests; synthetic signals exercise gates, not impact claims."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import steady_detail as steady
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'opencv-ready/candidate/app'))
from protected_regions import validate_regions
try:
    import numpy as np
    import cv2
except ImportError:
    np = cv2 = None


@unittest.skipIf(np is None or cv2 is None,'Pinned numerical runtime required for detector tests')
class StationaryBlink(unittest.TestCase):
    def test_observed_luma_hold_keeps_all_original_chroma_and_unselected_luma(self):
        from steady_export import held_luma_frames
        source=[np.arange(12,dtype=np.uint8)+t*20 for t in range(3)]
        mask=np.zeros((2,4),np.uint8);mask[:,2:4]=255
        output=list(held_luma_frames(source,mask,[0,0,0]));selected=np.flatnonzero(mask.ravel())
        for t,frame in enumerate(output):
            self.assertTrue(np.array_equal(frame[selected],source[0][selected]))
            self.assertTrue(np.array_equal(frame[8:],source[t][8:]))
            self.assertTrue(np.array_equal(frame[np.setdiff1d(np.arange(8),selected)],source[t][np.setdiff1d(np.arange(8),selected)]))
        self.assertTrue(np.array_equal(source[2],np.arange(12,dtype=np.uint8)+40))

    def test_observed_luma_hold_refuses_an_invalid_mapping(self):
        from steady_export import held_luma_frames
        source=[np.arange(12,dtype=np.uint8)]
        for mapping in ([],[1],[-1],[.5]):
            with self.assertRaises(ValueError):list(held_luma_frames(source,np.zeros((2,4),np.uint8),mapping))

    def source(self):
        frames=np.full((180,90,160),32,np.uint8)
        for t in range(180):
            frames[t,30:40,40:44]=220 if (t//15)%2 else 32
        return frames

    def test_stationary_two_states_propose_observed_brighter_frame(self):
        frames=self.source();found=steady.detect(frames,cv2,np)['candidates']
        self.assertEqual(len(found),1)
        candidate=found[0]
        self.assertEqual(candidate['bbox'],[40,30,4,10])
        self.assertEqual(candidate['state_transitions'],11)
        self.assertEqual(int(frames[candidate['reference_frame'],30,40]),220)

    def test_typing_that_adds_a_third_appearance_is_not_frozen_through(self):
        frames=self.source()
        frames[90:,30:40,40:44]=140
        self.assertEqual(steady.detect(frames,cv2,np)['candidates'],[])

    def test_short_dwell_rapid_changes_are_not_stationary_reading_blinks(self):
        frames=self.source()
        for t in range(180):frames[t,30:40,40:44]=220 if (t//3)%2 else 32
        self.assertEqual(steady.detect(frames,cv2,np)['candidates'],[])

    def test_static_detail_never_becomes_an_edit_proposal(self):
        self.assertEqual(steady.detect(np.full((180,90,160),32,np.uint8),cv2,np)['candidates'],[])

    def test_downsampled_thin_caret_survives_small_compression_variation(self):
        frames=np.full((180,90,160),230,np.uint8)
        for t in range(180):
            frames[t,30:36,40:42]=(196 if (t//15)%2 else 230)+(t%3-1)*2
        found=steady.detect(frames,cv2,np)['candidates']
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['bbox'],[40,30,2,6])
        self.assertEqual(found[0]['reference_state'],'darker')

    def test_low_separation_codec_noise_is_not_a_blink_proposal(self):
        frames=np.full((180,90,160),230,np.uint8)
        for t in range(180):frames[t,30:36,40:42]=224 if (t//15)%2 else 230
        self.assertEqual(steady.detect(frames,cv2,np)['candidates'],[])

    def test_blink_that_stops_is_not_held_through_the_following_pause(self):
        frames=np.full((360,90,160),32,np.uint8)
        for t in range(120):frames[t,30:40,40:44]=220 if (t//15)%2 else 32
        candidates=steady.detect(frames,cv2,np)['candidates']
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]['interval_frames'],[0,119])

    def test_dark_caret_on_light_background_keeps_its_visible_state(self):
        frames=255-self.source()
        candidate=steady.detect(frames,cv2,np)['candidates'][0]
        self.assertEqual(candidate['reference_state'],'darker')
        self.assertEqual(int(frames[candidate['reference_frame'],30,40]),35)

    def test_changing_colour_cannot_hide_behind_a_stable_luma_model(self):
        frames=self.source();native=[]
        for t,frame in enumerate(frames):
            uv=np.full((45,80),128,np.uint8)
            if t>=90:uv[15:20,20:22]=200
            native.append(np.r_[frame.ravel(),uv.ravel(),np.full(45*80,128,np.uint8)])
        self.assertEqual(steady.detect_native(native,160,90,cv2,np)['candidates'],[])


class SourceBoundSteadyPlan(unittest.TestCase):
    def test_changed_source_and_influence_overlap_refuse_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for name in ('input.mp4','prediction.json','steady-analysis.json'):(folder/name).write_bytes(name.encode())
            def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
            analysis={'input_sha256':sha(folder/'input.mp4'),'prediction_sha256':sha(folder/'prediction.json'),
                      'input_profile':{'width':160,'height':90,'frames':180}}
            candidate={'id':'steady-0','bbox':[40,30,4,10],'influence_xywh':[36,26,12,18],'reference_frame':15}
            detection={'candidates':[candidate]}
            body={'candidate_id':'steady-0','export_mode':steady.MODE,'prediction_sha256':analysis['prediction_sha256'],
                  'protected_regions':[{'label':'Lesson text','xywh':[0,0,30,90]}]}
            plan=steady.plan(folder,analysis,detection,body,sha,validate_regions)
            self.assertEqual(plan['recipe']['reference_frame'],15)
            self.assertFalse((folder/'approval.json').exists())
            with self.assertRaisesRegex(ValueError,'overlaps'):
                steady.plan(folder,analysis,detection,{**body,'protected_regions':[{'label':'Teaching','xywh':[37,27,1,1]}]},sha,validate_regions)
            (folder/'input.mp4').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Source changed'):
                steady.plan(folder,analysis,detection,body,sha,validate_regions)
