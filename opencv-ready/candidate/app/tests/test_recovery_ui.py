"""Executable DOM-stub recovery tests. Not browser/media verification."""
import subprocess
import unittest
from test_boundary_ui_static import HARNESS, NODE, SCRIPT

class RecoveryUI(unittest.TestCase):
 def run_js(self, code):
  harness=HARNESS.replace('boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,', '''boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,
  initialize, restoreJob, forgetRecovery, rememberJob, validJobId, recovery,
  getJob() { return job; }, getPlan() { return protectionPlan; },
  getRecoveryId() { return recoveryId; },''')
  setup=r'''
context.Headers = Headers;
context.window.setTimeout = () => 1;
context.window.clearTimeout = () => {};
const storage = new Map();
context.window.sessionStorage = {getItem: k => storage.get(k) ?? null,
 setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)};
const key = 'frame-review:last-job:v1', id = 'a'.repeat(32), calls = [];
ui.protectRect.style = {}; ui.statusPill.dataset = {};
function response(value, ok=true) { return {ok, status: ok ? 200 : 404, json: async()=>value}; }
function server(job, failed=false) {
 context.fetch = async (path, options) => {
  calls.push([path, options.method]);
  if(path==='/api/profile') return response({csrf_token:'token'});
  if(failed) throw Error('offline');
  return response(job);
 };
}
'''
  out=subprocess.run([NODE,'-e',harness+setup+'\n(async()=>{'+code+'\n})().catch(e=>{console.error(e);process.exitCode=1;});',str(SCRIPT)],capture_output=True,text=True,timeout=5)
  self.assertEqual(out.returncode,0,out.stdout+out.stderr)
 def test_complete_restored_without_post_or_duplicate_upload(self):
  self.run_js('''storage.set(key,id); server({id,status:'complete',input_name:'owned.mp4',summary:{},artifacts:{Report:'/api/jobs/'+id+'/download/report.json'}});
  await api.initialize(); assert.equal(api.getJob().id,id); assert.equal(ui.jobArea.hidden,false);
  assert.equal(ui.artifacts.children.length,1,api.recovery.status.textContent); assert.equal(ui.reviewed.checked,false);
  assert.equal(api.getPlan(),null); assert.equal(calls.length,2); assert.ok(calls.every(c=>c[1]==='GET'));
  assert.ok(api.recovery.status.textContent.includes('No decision was repeated'));''')
 def test_review_restored_requires_fresh_consent_and_plan(self):
  self.run_js('''storage.set(key,id); server({id,status:'review',candidates:[]});
  ui.reviewed.checked=true; await api.initialize();
  assert.equal(ui.reviewed.checked,false);assert.equal(api.getPlan(),null);assert.equal(ui.approve.disabled,true);
  assert.equal(ui.file.disabled,true); assert.equal(calls.length,2);''')
 def test_failure_blocks_new_upload_retry_only_reads(self):
  self.run_js('''storage.set(key,id); server(null,true); await api.initialize();
  assert.equal(api.getJob(),null); assert.equal(ui.file.disabled,true);
  assert.equal(api.recovery.retry.hidden,false); assert.equal(api.recovery.dismiss.hidden,false);
  assert.equal(storage.get(key),id);
  server({id,status:'cancelled'}); await api.restoreJob();
  assert.equal(api.getJob().status,'cancelled'); assert.equal(ui.file.disabled,false);
  assert.ok(calls.every(c=>c[1]==='GET'));''')
 def test_forget_failed_reference_does_not_delete_or_cancel(self):
  self.run_js('''storage.set(key,id); server(null,true); await api.initialize(); const count=calls.length;
  api.forgetRecovery(); assert.equal(calls.length,count); assert.equal(storage.has(key),false);
  assert.equal(ui.file.disabled,false); assert.equal(api.getRecoveryId(),null);''')
 def test_mismatched_job_or_unknown_status_not_adopted(self):
  for value in ["{id:'b'.repeat(32),status:'complete'}","{id,status:'invented'}", "{id,status:'constructor'}", "{id,status:'toString'}", "{id,status:'__proto__'}"]:
   self.run_js('storage.set(key,id);server('+value+''');await api.initialize();
   assert.equal(api.getJob(),null);assert.equal(ui.file.disabled,true);assert.equal(api.recovery.retry.hidden,false);''')
 def test_render_failure_rolls_back_and_remains_retryable(self):
  self.run_js('''storage.set(key,id);server({id,status:'complete',summary:{protected_content:{declared:true,regions:null}}});
  await api.initialize();assert.equal(api.getJob(),null);assert.equal(api.getRecoveryId(),id);
  assert.equal(ui.jobArea.hidden,true);assert.equal(ui.results.hidden,true);assert.equal(ui.file.disabled,true);
  server({id,status:'complete',summary:{}});await api.restoreJob();
  assert.equal(api.getJob().id,id);assert.equal(api.getRecoveryId(),null);assert.equal(ui.file.disabled,false);''')
 def test_invalid_saved_id_never_requested(self):
  self.run_js('''storage.set(key,'../../elsewhere');server(null);await api.initialize();
  assert.equal(calls.length,1);assert.equal(storage.has(key),false);assert.equal(ui.file.disabled,false);''')
 def test_unavailable_storage_does_not_break_new_work(self):
  self.run_js('''context.window.sessionStorage={getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}};
  server(null);await api.initialize();assert.equal(ui.file.disabled,false);api.rememberJob(id);
  assert.ok(api.recovery.status.textContent.includes('Keep this tab open'));''')
 def test_inflight_recovery_cannot_be_dismissed_or_repeated(self):
  self.run_js('''storage.set(key,id);let resolve;
  context.fetch=async path=>{calls.push(path);return path==='/api/profile'?response({csrf_token:'token'}):await new Promise(r=>resolve=r);};
  const pending=api.initialize();for(let i=0;i<10;i++)await Promise.resolve();
  assert.equal(ui.file.disabled,true);api.forgetRecovery();await api.restoreJob();
  assert.equal(calls.length,2);assert.equal(storage.get(key),id);
  resolve(response({id,status:'failed',error:'Validation refused'}));await pending;
  assert.equal(api.getJob().status,'failed');assert.equal(ui.file.disabled,false);''')

if __name__=='__main__':unittest.main()
