"""Causal branches and binding refusal; no semantic or human-impact claims."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow_trace import snapshot


class WorkflowTrace(unittest.TestCase):
    def test_visual_output_changes_next_action_without_approving(self):
        job=dict(id='a'*32,status='review',input_sha256='b'*64,prediction_sha256='c'*64,candidates=[])
        unchanged=copy.deepcopy(job)
        self.assertEqual(snapshot(job)['route'],'keep_source')
        job['candidates']=[dict(id='steady-0',bbox=[1,2,2,10],interval_frames=[10,100])]
        trace=snapshot(job)
        self.assertEqual(trace['route'],'request_human_review')
        self.assertFalse(trace['human_control']['source_bound_generation_approval'])
        self.assertEqual(trace['human_control']['creator_acceptance_for_use'],'not_recorded')
        self.assertEqual(unchanged['candidates'],[])

    def test_failed_checks_or_missing_approval_withhold_recommendation(self):
        job=dict(id='a'*32,status='complete',input_sha256='b'*64,prediction_sha256='c'*64,candidates=[{'id':'steady-0'}],summary={'checks':{'teaching_exact':True}})
        recipe={'input_sha256':job['input_sha256'],'prediction_sha256':job['prediction_sha256'],'candidate_id':'steady-0'}
        approval=dict(approve=True,candidate_id='steady-0',prediction_sha256=job['prediction_sha256'],recipe=recipe,
                      recipe_sha256=hashlib.sha256(json.dumps(recipe,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        self.assertEqual(snapshot(job)['route'],'withhold_recommendation')
        self.assertEqual(snapshot(job,approval)['route'],'inspect_comparison')
        job['summary']['checks']['teaching_exact']=False
        self.assertEqual(snapshot(job,approval)['route'],'withhold_recommendation')
        job['summary']['checks']['teaching_exact']=True
        job['teaching_review_error']='changed image'
        self.assertEqual(snapshot(job,approval)['route'],'withhold_recommendation')
        approval['recipe']['input_sha256']='d'*64
        with self.assertRaisesRegex(ValueError,'binding changed'):snapshot(job,approval)

    def test_failure_and_cancellation_never_become_success(self):
        for status,route in [('failed','withhold_recommendation'),('cancelled','cancelled'),('declined','keep_source'),('exporting','wait_for_tools')]:
            self.assertEqual(snapshot(dict(id='a'*32,status=status,candidates=[]))['route'],route)


if __name__=='__main__':unittest.main()
