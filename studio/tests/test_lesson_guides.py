"""A familiar lesson is not authority to edit a different source or teaching box."""
from pathlib import Path
import copy,sys,unittest
STUDIO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(STUDIO));sys.path.insert(0,str(STUDIO.parent/'opencv-ready/candidate/app'))
from lesson_guides import guide_for

class LessonGuides(unittest.TestCase):
    def setUp(self):
        self.candidate={'id':'steady-0','action':'steady-detail-v1','bbox':[370,330,6,10],'influence_xywh':[366,326,14,18]}
        self.credit={'prepared_sample_sha256':'a'*64,'label':'Progress lesson','reading_pause_guide':{'candidate_bbox':[370,330,6,10],'focus':'Keep changing progress','teaching_regions':[{'label':'Readout','xywh':[0,326,360,18]}]}}
    def test_only_exact_source_and_candidate_get_starting_regions(self):
        guide=guide_for('a'*64,self.candidate,self.credit,(360,640));self.assertEqual(guide['regions'],self.credit['reading_pause_guide']['teaching_regions']);self.assertIn('decide separately',guide['scope'])
        self.assertIsNone(guide_for('b'*64,self.candidate,self.credit,(360,640)))
        other=copy.deepcopy(self.candidate);other['bbox']=[220,172,4,12];self.assertIsNone(guide_for('a'*64,other,self.credit,(360,640)))
    def test_no_template_can_protect_the_influence_box(self):
        self.credit['reading_pause_guide']['teaching_regions'][0]['xywh']=[360,326,20,18]
        self.assertIsNone(guide_for('a'*64,self.candidate,self.credit,(360,640)))
    def test_invalid_regions_and_empty_templates_are_not_loaded(self):
        self.credit['reading_pause_guide']['teaching_regions'][0]['xywh']=[0,0,641,10]
        with self.assertRaises(ValueError):guide_for('a'*64,self.candidate,self.credit,(360,640))
        self.credit['reading_pause_guide']['teaching_regions']=[];self.assertIsNone(guide_for('a'*64,self.candidate,self.credit,(360,640)))
    def test_loading_returns_independent_regions_not_shared_mutable_metadata(self):
        guide=guide_for('a'*64,self.candidate,self.credit,(360,640));guide['regions'][0]['xywh'][0]=8;self.assertEqual(self.credit['reading_pause_guide']['teaching_regions'][0]['xywh'][0],0)

if __name__=='__main__':unittest.main()
