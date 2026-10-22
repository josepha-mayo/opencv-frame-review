"""Executable DOM tests. No browser, media, playback, or creator-benefit claim."""
from pathlib import Path
import subprocess
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent / 'opencv-ready/candidate/app/tests'))
from test_boundary_ui_static import HARNESS, NODE

EXPOSE = '''boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,
  protectionValues, resetProtection, invalidateProtection, drawProtection,
  saveProtectedRegion, removeProtectedRegion, checkProtection,
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
assert.equal(ids.get('protected-list').querySelectorAll('button').length,4);
assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
''')

    def test_incomplete_draft_keeps_saved_areas_visible_but_cannot_be_approved(self):
        self.run_js('''
save('Equation',[10,10,80,25]);ui.protectX.value='5';api.invalidateProtection();
assert.equal(ui.protectOverlays.children.length,1);
assert.throws(()=>api.protectionValues(),/complete rectangle/);
assert.equal(api.plan(),null);assert.equal(ui.approve.disabled,true);
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
