"""Causal cut-point and decoded-pixel regressions; no human-benefit claims."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import steady_boundaries as boundaries
try:
    import numpy as np
    import cv2
except ImportError:
    np=None


@unittest.skipIf(np is None,'Pinned numerical runtime required')
class BoundarySelection(unittest.TestCase):
    def source(self):
        rgb=np.full((180,2,2,3),32,np.uint8)
        for t in range(180):rgb[t]=220 if (t//15)%2 else 32
        native=np.concatenate([rgb[:,:,:,0].reshape(180,4),np.full((180,2),128,np.uint8)],axis=1)
        candidate={'bbox':[2,2,2,2],'interval_frames':[0,119],'reference_frame':15,'alternate_frame':0,'state_mean_error_limit':2}
        return candidate,rgb,rgb.mean(axis=(1,2,3))/255,native

    def test_fixed_window_return_that_worsens_gets_source_matched_cuts(self):
        c,rgb,linear,native=self.source()
        c['interval_frames']=[0,120]
        self.assertGreater(abs(linear[121]-linear[15]),abs(linear[121]-linear[120]))
        selected=boundaries.select(c,rgb,linear,native,np)
        self.assertIsNotNone(selected)
        lo,hi=selected['interval_frames']
        self.assertGreater(lo,0);self.assertLess(hi,len(rgb)-1)
        self.assertGreaterEqual(hi-lo+1,60)
        self.assertGreaterEqual(selected['boundary_alignment']['predicted_source_internal_changes'],4)
        for name in ('predicted_entry','predicted_exit'):
            m=selected['boundary_alignment'][name]
            self.assertTrue(boundaries.not_worse(m['source'],m['edited']))
        self.assertTrue(np.array_equal(rgb[selected['reference_frame']],rgb[15]))

    def test_insufficient_interior_duration_refuses_instead_of_editing_loop(self):
        c,rgb,linear,native=self.source();c['interval_frames']=[0,59]
        self.assertIsNone(boundaries.select(c,rgb,linear,native,np))

    def test_pixelwise_boundary_gate_catches_same_mean_rearrangement(self):
        base=np.full((2,2,3),100,np.uint8);changed=base.copy();changed[0,0]=140;changed[0,1]=60
        self.assertEqual(base.mean(),changed.mean())
        samples={t:{'source':{'selected':base,'influence':base},'edited':{'selected':base,'influence':base}} for t in (0,1,2,3,4,5)}
        samples[2]['edited']={'selected':changed,'influence':changed}
        measured=boundaries.encoded_measurements(samples,2,3,6,np)
        self.assertFalse(measured['passed'])
        self.assertFalse(measured['measurements']['entry']['selected']['passed'])

    def test_static_identical_encoded_cuts_and_loop_pass_exactly(self):
        base=np.full((2,2,3),100,np.uint8)
        samples={t:{'source':{'selected':base,'influence':base},'edited':{'selected':base,'influence':base}} for t in range(6)}
        measured=boundaries.encoded_measurements(samples,2,3,6,np)
        self.assertTrue(measured['passed'])
        self.assertEqual(measured['measurements']['loop_seam']['influence']['edited']['maximum_rgb_codes'],0)

    def test_reused_full_width_measurement_matches_frozen_frame_mask(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'opencv-ready/candidate/app'))
        import engine
        engine.verify_runtime()
        frame=np.random.default_rng(52).integers(0,256,(360,640,3),dtype=np.uint8)
        bbox=[206,210,2,6];mask=np.zeros((360,640),np.uint8);mask[210:216,206:208]=255
        expected=float(cv2.mean(cv2.transform(cv2.LUT(frame,engine.LUT),engine.WEIGHTS),mask=mask)[0])
        self.assertEqual(boundaries.selected_linear(engine,frame,bbox),expected)

    def test_reused_values_preserve_frozen_temporal_diagnostic(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'opencv-ready/candidate/app'))
        import engine
        engine.verify_runtime()
        old_n=engine.N
        try:
            engine.N=180
            fake=[np.full((1,1,3),220 if (t//15)%2 else 32,np.uint8) for t in range(180)]
            # Compare against the actual frozen entry point over identical
            # decoded pixels, rather than a second copy of its implementation.
            actual_values=[float(cv2.mean(cv2.transform(cv2.LUT(f,engine.LUT),engine.WEIGHTS))[0]) for f in fake]
            from unittest.mock import patch
            with patch.object(engine,'guard'), patch.object(engine.alg,'guard'):
                expected=engine.trace(iter(fake),np.full((1,1),255,np.uint8),15,149)
                self.assertEqual(boundaries.trace_from_values(engine,actual_values,15,149),expected)
        finally:engine.N=old_n
