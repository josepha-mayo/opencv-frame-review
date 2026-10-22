"""DOM-stub contract only. No real browser, media or network activity."""
import subprocess,unittest
from test_boundary_ui_static import HARNESS,NODE,SCRIPT
class ProtectionUI(unittest.TestCase):
 def run_js(self,code):
  harness=HARNESS.replace('boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,','boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui, protectionValues, resetProtection, invalidateProtection,\n  getProtectionPlan() { return protectionPlan; },')
  out=subprocess.run([NODE,'-e',harness+'\n'+code,str(SCRIPT)],capture_output=True,text=True,timeout=5)
  self.assertEqual(out.returncode,0,out.stdout+out.stderr)
 def test_rectangle_bounds_empty_and_consent_reset(self):
  self.run_js('''
  ui.image.naturalWidth=640;ui.image.naturalHeight=360;ui.protectRect.style={};
  api.resetProtection({recipe_sha256:'a'.repeat(64)});
  assert.equal(api.protectionValues().length,0);assert.equal(api.getProtectionPlan(),null);
  [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((f,i)=>f.value=String([470,171,100,60][i]));
  assert.equal(JSON.stringify(api.protectionValues()),JSON.stringify([{label:'Important area',xywh:[470,171,100,60]}]));
  ui.reviewed.checked=true;api.invalidateProtection();assert.equal(api.getProtectionPlan(),null);assert.equal(ui.reviewed.checked,false);assert.equal(ui.approve.disabled,true);
  ui.protectW.value='1000';assert.throws(()=>api.protectionValues(),/inside the image/);
  ui.protectW.value='';assert.throws(()=>api.protectionValues(),/complete rectangle/);
  ui.protectW.value='1.5';assert.throws(()=>api.protectionValues(),/integer pixels/);
  ''')
 def test_failed_measurement_and_undeclared_are_explicit(self):
  self.run_js('''
  const protected_content={declared:true,frames:180,passed:false,regions:[{label:'Important area',xywh:[470,171,100,60],passed:false,measurements:{mean_rgb_code_error:.01,p99_rgb_code_error:0,max_rgb_code_error:4}}]};
  api.setJob({status:'complete',summary:{protected_content,review_status:'checks_failed',checks:{creator_protected_content:false}}});api.renderResults();
  assert.ok(ui.highlights.textContent.includes('Failed preservation criteria'));assert.ok(ui.highlights.textContent.includes('criterion not met'));
  assert.ok(walk(ui.highlights).some(n=>n.classList.contains('protected-failed')));
  api.setJob({status:'complete',summary:{protected_content:{declared:false,passed:null,regions:[]}}});api.renderResults();
  assert.ok(ui.highlights.textContent.includes('No important area declared'));
  ''')
if __name__=='__main__':unittest.main(verbosity=2)
