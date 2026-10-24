"""Executable DOM tests. No browser, media, playback, or creator-benefit claim."""
from pathlib import Path
import subprocess
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent / 'opencv-ready/candidate/app/tests'))
from test_boundary_ui_static import HARNESS, NODE

EXPOSE = '''boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui, byId,
  protectionValues, resetProtection, invalidateProtection, drawProtection,
  saveProtectedRegion, removeProtectedRegion, editProtectedRegion, cancelProtectedEdit, checkProtection, loadTeachingGuide,
  startAreaMarking, cancelAreaMarking, markAreaCorner,
  plan() { return protectionPlan; },
  setBusy(value) { busy = value; updateControls(); },
  setUncertain(value) { stateUncertain = value; updateControls(); },
  breakCandidate() { delete job.candidates[0].bbox; },
  prepare() {
    job = {id:'a'.repeat(32), status:'review', prediction_sha256:'b'.repeat(64),
      candidates:[{id:'0',recipe_sha256:'c'.repeat(64),bbox:[260,50,40,40],interval_frames:[9,159]}]};
    selectedId='0'; imageLoaded=true; token='test';
    ui.image.naturalWidth=320; ui.image.naturalHeight=180;
    resetProtection(currentCandidate()); updateControls();
  },'''


class StudioEditor(unittest.TestCase):
    def test_marking_cancel_keeps_saved_box_and_draft_without_reusing_consent(self):
        self.run_js('''
save('Equation',[10,10,80,25]);api.editProtectedRegion(0);draft('Equation detail',[10,10,90,25]);
ui.reviewed.checked=true;api.startAreaMarking();
assert.equal(ids.get('protect-pick-cancel').hidden,false);
assert.equal(ui.protectCheck.disabled,true);assert.equal(ids.get('protect-add').disabled,true);
assert.equal(ui.reviewed.checked,false);assert.equal(api.plan(),null);
ui.image.getBoundingClientRect=()=>({left:10,top:20,width:160,height:90});
api.markAreaCorner({clientX:20,clientY:30});assert.ok(ui.protectStatus.textContent.includes('(20, 20)'));
api.cancelAreaMarking();
assert.equal(ui.protectW.value,'90');assert.equal(ids.get('protect-label').value,'Equation detail');
assert.ok(ids.get('protected-list').textContent.includes('[10, 10, 80, 25]'));
assert.equal(ids.get('protect-pick-cancel').hidden,true);assert.equal(ui.approve.disabled,true);
api.saveProtectedRegion();assert.equal(api.protectionValues()[0].xywh[2],90);
''')

    def test_scaled_reverse_corners_ignore_outside_image_and_block_plans_until_complete(self):
        self.run_js('''
ui.image.getBoundingClientRect=()=>({left:10,top:20,width:160,height:90});
api.startAreaMarking();api.markAreaCorner({clientX:9,clientY:30});
assert.ok(ui.protectStatus.textContent.includes('Choose the first corner'));
api.markAreaCorner({clientX:110,clientY:70});
assert.ok(ui.protectStatus.textContent.includes('(200, 100)'));
api.markAreaCorner({clientX:170,clientY:110});
assert.equal(ui.protectCheck.disabled,true);
api.markAreaCorner({clientX:30,clientY:30});
assert.deepEqual(Array.from(api.protectionValues()[0].xywh),[40,20,161,81]);
assert.equal(ui.protectCheck.disabled,false);assert.equal(ui.approve.disabled,true);
assert.ok(ui.protectStatus.textContent.includes('Nothing has been approved'));
''')

    def test_marking_cannot_mutate_during_uncertain_state_and_reset_drops_old_corner(self):
        self.run_js('''
save('Equation',[10,10,80,25]);
ui.image.getBoundingClientRect=()=>({left:0,top:0,width:320,height:180});
api.startAreaMarking();api.markAreaCorner({clientX:1,clientY:1});
api.setUncertain(true);api.markAreaCorner({clientX:50,clientY:50});api.cancelAreaMarking();
assert.equal(ids.get('protect-pick-cancel').hidden,false);assert.equal(ui.protectX.value,'');
api.setUncertain(false);api.removeProtectedRegion(0);assert.equal(api.protectionValues().length,1);
api.resetProtection(null);api.setBusy(false);api.startAreaMarking();
api.markAreaCorner({clientX:20,clientY:30});
assert.ok(ui.protectStatus.textContent.includes('(20, 30)'));assert.equal(ui.protectX.value,'');
api.cancelAreaMarking();assert.equal(api.protectionValues().length,0);
''')

    def test_example_areas_do_not_skip_review_or_overwrite_custom_work(self):
        self.run_js('''
const base={id:'a'.repeat(32),status:'review',input_sha256:'d'.repeat(64),prediction_sha256:'b'.repeat(64),candidates:[{id:'0',recipe_sha256:'c'.repeat(64),bbox:[260,50,40,40],interval_frames:[9,159]}],teaching_guides:[{source_sha256:'d'.repeat(64),candidate_id:'0',candidate_bbox:[260,50,40,40],focus:'Keep the readout moving',regions:[{label:'Readout',xywh:[10,10,80,25]}]}]};
api.setJob(base);api.setBusy(false);ui.reviewed.checked=true;
assert.equal(api.byId('teaching-guide').hidden,false);
api.loadTeachingGuide();assert.equal(api.protectionValues().length,1);
assert.equal(ui.reviewed.checked,false);assert.equal(api.plan(),null);assert.equal(ui.approve.disabled,true);
assert.equal(api.byId('teaching-guide-load').disabled,true);
api.loadTeachingGuide();assert.equal(api.protectionValues().length,1);
api.resetProtection(null);draft('My area',[20,20,30,20]);
assert.equal(api.byId('teaching-guide-load').disabled,true);
api.loadTeachingGuide();assert.equal(api.protectionValues()[0].label,'My area');
''')

    def test_example_guide_for_different_source_is_hidden(self):
        self.run_js('''
api.setJob({id:'a'.repeat(32),status:'review',input_sha256:'d'.repeat(64),candidates:[{id:'0',bbox:[260,50,40,40]}],teaching_guides:[{source_sha256:'e'.repeat(64),candidate_id:'0',candidate_bbox:[260,50,40,40],regions:[{label:'Other source',xywh:[10,10,80,25]}]}]});api.setBusy(false);
assert.equal(api.byId('teaching-guide').hidden,true);assert.equal(api.byId('teaching-guide-load').disabled,true);
api.loadTeachingGuide();assert.equal(api.protectionValues().length,0);assert.equal(api.plan(),null);
''')

    def test_prepared_lesson_cannot_plan_without_a_teaching_area(self):
        self.run_js('''
api.prepare();
api.setJob({id:'a'.repeat(32),status:'review',prediction_sha256:'b'.repeat(64),preparation:{source:{width:1920,height:1080}},candidates:[{id:'0',recipe_sha256:'c'.repeat(64),bbox:[260,50,40,40],interval_frames:[9,159]}]});
let calls=0;context.fetch=async()=>{calls++;throw new Error('must not send an empty teaching contract');};
await api.checkProtection();
assert.equal(calls,0);assert.equal(api.plan(),null);
assert.ok(ui.protectError.textContent.includes('at least one teaching area'));
assert.equal(ui.approve.disabled,true);
''')

    def test_retaining_source_does_not_claim_encoded_measurements(self):
        self.run_js('''
api.setJob({status:'declined',artifacts:{'Prepared lesson clip':'/api/jobs/abc/download/original.mp4'}});api.renderResults();
assert.equal(ui.results.hidden,false);
assert.equal(api.byId('results-title').textContent,'Retained lesson files');
assert.equal(api.byId('boundary-review').hidden,true);
assert.equal(api.byId('result-report-details').hidden,true);
''')
    def test_empty_artifacts_do_not_show_results_before_encoding(self):
        self.run_js('''
api.setJob({status:'review',artifacts:{}});api.renderResults();
assert.equal(ui.results.hidden,true);
''')

    def test_demo_analysis_needs_explicit_click_and_never_approves(self):
        self.run_js('''
api.setJob(null);api.setBusy(false);ui.cloudSamples.hidden=false;
const calls=[];
context.fetch=async(path,options={})=>{calls.push({path,...options});return {ok:true,json:async()=>({id:'f'.repeat(32),status:'review',candidates:[],artifacts:{}})};};
assert.equal(calls.length,0);
await ui.demo.events.click();
assert.equal(calls[0].path,'/api/demo');assert.equal(calls[0].method,'POST');
assert.equal(calls[0].body,'{}');assert.ok(calls.every(call=>!call.path.endsWith('/approve')));
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def run_js(self, code):
        harness = HARNESS.replace(
            '  addEventListener() {}',
            '  addEventListener(name, handler) { (this.events ??= {})[name] = handler; }'
        ).replace('this.attributes = {};', 'this.attributes = {}; this.style = {};').replace('boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,', EXPOSE)
        setup = '''
context.Headers=Headers;
api.prepare();
function draft(label, xywh) {
  ids.get('protect-label').value=label;
  [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field,index)=>field.value=String(xywh[index]));
  api.invalidateProtection();
}
function save(label, xywh) { draft(label,xywh);api.saveProtectedRegion(); }
function respond(mode='periodic-local-retime-v2') {
  context.fetch=async(path,options)=>({ok:true,json:async()=>{
    const request=JSON.parse(options.body);
    return {...request,export_mode:mode,recipe_sha256:'d'.repeat(64)};
  }});
}
'''
        result = subprocess.run(
            [NODE, '-e', harness + setup + '\n(async()=>{' + code + '\n})().catch(e=>{console.error(e);process.exitCode=1;});', str(STUDIO / 'static/app.js')],
            capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_four_areas_visible_and_numbered_instead_of_only_first(self):
        self.run_js('''
save('Equation',[10,10,80,25]);save('Diagram',[10,50,120,50]);
save('Counter',[180,15,40,20]);save('Footer',[10,150,200,10]);
assert.equal(ui.protectOverlays.children.length,4);
assert.equal(ui.protectCount.textContent,'4 of 4 areas saved');
assert.ok(ui.protectOverlays.textContent.includes('4. Footer'));
assert.equal(ui.protectOverlays.children[1].style.width,'37.5%');
assert.equal(ui.protectOverlays.children[1].style.left,'3.125%');
assert.equal(ui.protectOverlays.children[1].attributes.style,undefined);
const actions=ids.get('protected-list').querySelectorAll('button');
assert.equal(actions.filter(b=>b.attributes['aria-label'].startsWith('Remove protected area ')).length,4);
assert.equal(actions.filter(b=>b.attributes['aria-label'].startsWith('Edit protected area ')).length,4);
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def test_incomplete_draft_keeps_saved_areas_visible_but_cannot_be_approved(self):
        self.run_js('''
save('Equation',[10,10,80,25]);ui.protectX.value='5';api.invalidateProtection();
assert.equal(ui.protectOverlays.children.length,1);
assert.throws(()=>api.protectionValues(),/complete rectangle/);
assert.equal(api.plan(),null);assert.equal(ui.approve.disabled,true);
''')

    def test_edit_saved_area_at_four_area_limit_requires_save_and_fresh_plan(self):
        self.run_js('''
save('Equation',[10,10,80,25]);save('Diagram',[10,50,120,50]);
save('Counter',[180,15,40,20]);save('Footer',[10,150,200,10]);
respond();await api.checkProtection();ui.reviewed.checked=true;
ids.get('protected-list').querySelectorAll('button').find(b=>b.attributes['aria-label']==='Edit protected area Equation').events.click();
assert.equal(ids.get('protect-label').value,'Equation');assert.equal(ui.protectW.value,'80');
assert.equal(ui.protectCheck.disabled,true);assert.equal(ui.reviewed.checked,false);
assert.equal(ui.approve.disabled,true);assert.equal(api.plan(),null);
let calls=0;context.fetch=async()=>{calls++;throw new Error('must save before plan');};
await api.checkProtection();assert.equal(calls,0);
draft('Equation detail',[10,10,90,25]);api.saveProtectedRegion();
assert.equal(api.protectionValues().length,4);assert.equal(api.protectionValues()[0].label,'Equation detail');
assert.equal(api.protectionValues()[0].xywh[2],90);assert.equal(api.protectionValues()[1].label,'Diagram');
assert.equal(ids.get('protect-edit-cancel').hidden,true);assert.equal(ui.protectCheck.disabled,false);
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);assert.equal(api.plan(),null);
respond();await api.checkProtection();assert.equal(api.plan().protected_regions[0].xywh[2],90);
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def test_invalid_area_edit_can_cancel_without_losing_saved_regions(self):
        self.run_js('''
save('Equation',[10,10,80,25]);save('Footer',[10,150,200,10]);
const original=JSON.stringify(api.protectionValues());api.editProtectedRegion(0);
draft('Broken',[10,10,999,25]);api.saveProtectedRegion();
assert.ok(ui.protectError.textContent.includes('complete rectangle'));
assert.ok(ids.get('protected-list').textContent.includes('Equation'));
assert.equal(ids.get('protect-edit-cancel').hidden,false);
api.removeProtectedRegion(1);assert.ok(ids.get('protected-list').textContent.includes('Footer'));
api.cancelProtectedEdit();assert.equal(JSON.stringify(api.protectionValues()),original);
assert.equal(ids.get('protect-label').value,'');assert.equal(ui.protectX.value,'');
assert.equal(api.plan(),null);assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def test_edit_never_overwrites_a_draft_or_bypasses_locked_review(self):
        self.run_js('''
save('Equation',[10,10,80,25]);draft('New draft',[30,60,40,20]);
api.editProtectedRegion(0);assert.equal(ids.get('protect-label').value,'New draft');
assert.ok(ui.protectError.textContent.includes('draft has been kept'));
ui.protectX.value='';ui.protectY.value='';ui.protectW.value='';ui.protectH.value='';ids.get('protect-label').value='';api.invalidateProtection();
api.setBusy(true);api.editProtectedRegion(0);assert.equal(ids.get('protect-label').value,'');
api.setBusy(false);api.setUncertain(true);api.editProtectedRegion(0);assert.equal(ids.get('protect-label').value,'');
api.setUncertain(false);api.editProtectedRegion(-1);api.editProtectedRegion(9);assert.equal(ids.get('protect-label').value,'');
api.editProtectedRegion(0);assert.equal(ids.get('protect-label').value,'Equation');
api.resetProtection(null);api.setBusy(false);
assert.equal(api.protectionValues().length,0);assert.equal(ids.get('protect-edit-cancel').hidden,true);
assert.equal(ids.get('protect-label').value,'');assert.equal(ui.protectX.value,'');
''')

    def test_remove_one_area_keeps_others_and_invalidates_checked_plan(self):
        self.run_js('''
save('Equation',[10,10,80,25]);save('Footer',[10,150,200,10]);
respond();await api.checkProtection();ui.reviewed.checked=true;
assert.ok(api.plan());
const remove=ids.get('protected-list').querySelectorAll('button')[0];
assert.equal(remove.attributes['aria-label'],'Remove protected area Equation');
remove.events.click();
assert.equal(api.protectionValues().length,1);assert.equal(api.protectionValues()[0].label,'Footer');
assert.equal(ui.protectOverlays.children.length,1);
assert.equal(api.plan(),null);assert.equal(ui.reviewed.checked,false);
assert.equal(ui.planSummary.hidden,true);assert.equal(ui.approve.disabled,true);
''')

    def test_remove_locked_during_request_and_uncertain_state(self):
        self.run_js('''
save('Equation',[10,10,80,25]);api.setBusy(true);
assert.equal(ids.get('protected-list').querySelectorAll('button')[0].disabled,true);
api.removeProtectedRegion(0);assert.equal(api.protectionValues().length,1);
api.setBusy(false);api.setUncertain(true);api.removeProtectedRegion(0);
assert.equal(api.protectionValues().length,1);
api.setUncertain(false);api.removeProtectedRegion(-1);api.removeProtectedRegion(9);
assert.equal(api.protectionValues().length,1);
''')

    def test_fifth_area_and_duplicate_name_refused(self):
        self.run_js('''
save('Equation',[10,10,80,25]);draft('Equation',[15,50,20,20]);
api.saveProtectedRegion();assert.ok(ui.protectError.textContent.includes('distinct'));
draft('Two',[10,50,20,20]);api.saveProtectedRegion();
save('Three',[40,50,20,20]);save('Four',[70,50,20,20]);
draft('Five',[100,50,20,20]);api.saveProtectedRegion();
assert.ok(ui.protectError.textContent.includes('at most four'));
assert.equal(ui.protectOverlays.children.length,4);
''')

    def test_area_names_render_as_text(self):
        self.run_js('''
save('<img src=x onerror=alert(1)>',[10,10,80,25]);
assert.equal(ui.protectOverlays.querySelectorAll('img').length,0);
assert.ok(ui.protectOverlays.textContent.includes('<img src=x'));
''')

    def test_plan_brief_binds_mode_interval_and_named_areas_without_consent(self):
        self.run_js('''
save('Equation',[10,10,80,25]);respond();await api.checkProtection();
assert.ok(api.plan());assert.equal(ui.planSummary.hidden,false);
assert.ok(ui.planSummary.textContent.includes('5×'));
assert.ok(ui.planSummary.textContent.includes('frames 9–159'));
assert.ok(ui.planSummary.textContent.includes('Equation'));
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def test_mismatched_export_mode_refused(self):
        self.run_js('''
respond('legacy');await api.checkProtection();
assert.equal(api.plan(),null);assert.equal(ui.planSummary.hidden,true);
assert.ok(ui.protectError.textContent.includes('does not match'));
assert.equal(ui.approve.disabled,true);
''')

    def test_unrenderable_plan_cannot_leave_approval_enabled(self):
        self.run_js('''
respond();api.breakCandidate();await api.checkProtection();
assert.equal(api.plan(),null);assert.equal(ui.planSummary.hidden,true);
assert.equal(ui.approve.disabled,true);
''')

    def test_edit_plan_reset_clears_all_unsaved_state(self):
        self.run_js('''
save('Equation',[10,10,80,25]);respond();await api.checkProtection();
ui.reviewed.checked=true;api.resetProtection(null);
assert.equal(api.protectionValues().length,0);assert.equal(ui.protectOverlays.children.length,0);
assert.equal(ids.get('protected-list').children.length,0);
assert.equal(ui.planSummary.hidden,true);assert.equal(api.plan(),null);
assert.equal(ui.reviewed.checked,false);
''')


if __name__ == '__main__':
    unittest.main()
