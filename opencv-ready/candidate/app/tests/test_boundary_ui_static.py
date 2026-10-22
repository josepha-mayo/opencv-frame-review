"""Source and dependency-free Node/DOM-stub checks, not browser or media validation.

No server is started, no URL is requested, and no PNG or clip is decoded here.
Image load/error events and natural dimensions are explicitly simulated.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest

APP = Path(__file__).resolve().parents[1]
SCRIPT = APP / 'static/app.js'
NODE = shutil.which('node')


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


HARNESS = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attributes = {};
    this.hidden = false; this.disabled = false; this.checked = false;
    this.files = []; this._text = ''; this.className = '';
    const names = new Set();
    this.classList = {add: x => names.add(x), remove: x => names.delete(x),
      contains: x => names.has(x), toggle: (x, enabled) => enabled ? names.add(x) : names.delete(x)};
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener() {}
  querySelectorAll(tag) { return walk(this).filter(x => x !== this && x.tagName === tag); }
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
const ids = new Map();
const document = {
  getElementById(id) { if (!ids.has(id)) ids.set(id, new Node('div')); return ids.get(id); },
  createElement(tag) { return new Node(tag); }, querySelectorAll() { return []; }
};
const noIO = () => { throw Error('Unexpected network or timed work in static UI test'); };
const context = {document, URL, window: {location: {origin: 'http://ui.test'},
  addEventListener() {}, setTimeout: noIO, clearTimeout: noIO}, fetch: noIO};
vm.createContext(context);
let source = fs.readFileSync(process.argv[1], 'utf8');
assert.equal((source.match(/  initialize\(\);/g) || []).length, 1);
source = source.replace('  initialize();', `  globalThis.testAPI = {
  boundaryReviewProblem, renderBoundaryReview, renderResults, localURL, ui,
  setJob(value) { job = value; }
};`);
vm.runInContext(source, context, {timeout: 1000});
const api = context.testAPI, ui = api.ui;
function review() {
  const labels = ['Before edit', 'Edit begins', 'Final edited frame', 'Original frames resume'];
  return {schema: 'encoded-boundaries-v1', input_sha256: 'a'.repeat(64),
    prediction_sha256: 'b'.repeat(64), recipe_sha256: 'c'.repeat(64),
    output_hashes: {control: 'd'.repeat(64), edited: 'e'.repeat(64)}, crop_xywh: [12, 16, 80, 40],
    rows: labels.map((label, index) => ({label, frame: [8, 9, 29, 30][index],
      seconds: [8 / 30, 9 / 30, 29 / 30, 1][index], loop_wrap: false,
      images: Object.fromEntries(['original', 'control', 'edited'].map(key => [key, {
        filename: 'boundary-f' + index + '-' + key + '.png', sha256: 'f'.repeat(64),
        decoded_crop_rgb_sha256: '1'.repeat(64),
        url: '/api/jobs/job/review/boundary-f' + index + '-' + key + '.png'
      }]))})),
    strong_return_transition: {newly_timed: true, control_delta: 0.02, edited_delta: 0.45, criterion: 0.1}};
}
function setReview(value, extra = {}) {
  api.setJob({id: 'job', status: 'complete', frame_review: value, ...extra});
  api.renderBoundaryReview();
}
function imgs() { return ui.boundaryRows.querySelectorAll('img'); }
function loadAll() {
  imgs().forEach(img => { img.naturalWidth = 80; img.naturalHeight = 40; img.onload(); });
}
'''


class BoundarySourceContracts(unittest.TestCase):
    def setUp(self):
        self.html = (APP / 'static/index.html').read_text()
        self.js = SCRIPT.read_text()
        self.css = (APP / 'static/styles.css').read_text()
        self.document = Document(self.html)
        self.ids = {attrs['id']: (tag, attrs) for tag, attrs in self.document.elements if 'id' in attrs}

    def test_static_comparison_discloses_scope_and_tradeoff(self):
        text = ' '.join(self.document.text)
        for phrase in ['Four fixed moments', 'same region', 'do not show the full motion',
                       'limited selected-mean diagnostic', 'Count reduction does not remove that tradeoff',
                       'does not independently verify file hashes']:
            self.assertIn(phrase, text)
        self.assertEqual(self.ids['boundary-return-warning'][1]['role'], 'alert')
        self.assertEqual(self.ids['boundary-review-error'][1]['role'], 'alert')

    def test_provenance_is_collapsible_and_ids_are_bound(self):
        self.assertEqual(self.ids['boundary-provenance'][0], 'details')
        self.assertNotIn('open', self.ids['boundary-provenance'][1])
        self.assertEqual(self.ids['boundary-provenance-data'][0], 'pre')
        self.assertTrue(set(re.findall(r'byId\("([^"]+)"\)', self.js)) <= set(self.ids))
        ids = [attrs['id'] for _, attrs in self.document.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_motion_switching_or_markup_injection(self):
        renderer = self.js.split('  const BOUNDARY_VERSIONS =', 1)[1].split('  function renderResults()', 1)[0]
        for token in ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'requestAnimationFrame',
                      'setTimeout', 'setInterval', 'fetch(', 'request(', 'decision(', 'updateControls(']:
            self.assertNotIn(token, renderer)
        for tag, attrs in self.document.elements:
            self.assertNotIn(tag, {'video', 'audio', 'canvas', 'iframe', 'object', 'embed'})
            self.assertNotIn('autoplay', attrs)
        self.assertNotRegex(renderer, r'element\("(?:button|input|video|audio|canvas)"')
        self.assertNotRegex(self.css, r'(?<![\w-])(?:animation|transition)\s*:')

    def test_equal_responsive_columns_and_explicit_load_failures(self):
        self.assertIn('.boundary-images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))', self.css)
        self.assertIn('@media(max-width:600px)', self.css)
        self.assertIn('img.src = localURL(asset.url);', self.js)
        self.assertIn('img.onerror = () => fail(', self.js)
        self.assertIn('img.naturalWidth !== review.crop_xywh[2]', self.js)
        self.assertIn('img.naturalHeight !== review.crop_xywh[3]', self.js)


@unittest.skipUnless(NODE, 'Node is needed for dependency-free DOM-stub checks')
class BoundaryDOMStubContracts(unittest.TestCase):
    def run_js(self, assertions):
        result = subprocess.run([NODE, '-e', HARNESS + '\n' + assertions, str(SCRIPT)],
                                cwd=APP, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_four_aligned_labeled_rows_and_exact_provenance(self):
        self.run_js(r'''
const data = review(); setReview(data);
assert.equal(ui.boundaryRows.children.length, 4); assert.equal(imgs().length, 12);
ui.boundaryRows.children.forEach((row, i) => {
  assert.equal(row.children[0].textContent, data.rows[i].label);
  assert.match(row.children[1].textContent, /crop \[12, 16, 80, 40\]/);
  assert.ok(row.children[1].textContent.includes(String(data.rows[i].seconds)));
  assert.deepEqual(row.children[2].children.map(fig => fig.children[0].children[0].textContent),
    ['Original', 'Control', 'Edited']);
});
assert.equal(ui.boundaryWarning.hidden, false);
assert.match(ui.boundaryValues.textContent, /control 0.02 · edited 0.45 · criterion 0.1/);
assert.equal(ui.boundaryProvenance.hidden, false); assert.equal(ui.boundaryProvenance.open, false);
assert.deepEqual(JSON.parse(ui.boundaryData.textContent), data);
assert.match(ui.boundaryStatus.textContent, /^0 of 12/);
loadAll(); assert.match(ui.boundaryStatus.textContent, /^12 of 12/);
assert.equal(ui.boundaryError.hidden, true); assert.ok(imgs().every(img => !img.hidden));
''')

    def test_absent_historical_data_and_invalid_schema(self):
        self.run_js(r'''
for (const value of [undefined, null]) {
  setReview(value); assert.equal(imgs().length, 0);
  assert.match(ui.boundaryStatus.textContent, /No static boundary comparison/);
  assert.equal(ui.boundaryError.hidden, true); assert.equal(ui.boundaryProvenance.hidden, true);
}
for (const value of [{}, false, 2, 'bad', [], {...review(), schema: 'wrong'}]) {
  setReview(value); assert.equal(imgs().length, 0); assert.equal(ui.boundaryError.hidden, false);
  assert.match(ui.boundaryStatus.textContent, /unavailable/);
}
''')

    def test_malformed_contract_is_rejected_before_loading_any_image(self):
        self.run_js(r'''
const changes = [
  r => r.rows.pop(), r => r.rows.push(r.rows[0]), r => r.rows.reverse(),
  r => r.rows[0].label = '', r => r.rows[0].frame = -1, r => r.rows[0].frame = 1.5,
  r => r.rows[0].seconds = Infinity, r => r.rows[0].loop_wrap = 'false',
  r => r.rows[0].images.edited = null, r => r.crop_xywh[2] = 0,
  r => r.crop_xywh[0] = -1, r => r.crop_xywh.pop(), r => r.crop_xywh[3] = 1.5,
  r => r.input_sha256 = 'bad', r => r.prediction_sha256 = null,
  r => r.recipe_sha256 = [], r => r.output_hashes = {},
  r => r.rows[3].images.edited.sha256 = 'bad',
  r => r.rows[3].images.edited.decoded_crop_rgb_sha256 = 'bad',
  r => r.strong_return_transition = null, r => r.strong_return_transition.newly_timed = 1,
  r => r.strong_return_transition.edited_delta = NaN, r => r.strong_return_transition.control_delta = -1,
  r => r.strong_return_transition.criterion = 0.2
];
changes.forEach(change => {
  const data = review(); change(data); setReview(data);
  assert.equal(imgs().length, 0); assert.equal(ui.boundaryError.hidden, false);
  assert.equal(ui.boundaryProvenance.hidden, true);
});
''')

    def test_off_origin_non_png_and_network_path_urls_are_rejected(self):
        self.run_js(r'''
for (const url of ['https://other.test/a.png', '//other.test/a.png', 'data:image/png,x',
  'javascript:alert(1)', '\\other.test\a.png', '/a.mp4', '/a.gif', '/a.svg', '', ' /a.png']) {
  const data = review(); data.rows[3].images.edited.url = url; setReview(data);
  assert.equal(imgs().length, 0); assert.equal(ui.boundaryError.hidden, false);
}
for (const filename of ['a.gif', '../a.png', 'a\\b.png', 'a.png\n']) {
  const data = review(); data.rows[0].images.original.filename = filename; setReview(data);
  assert.equal(imgs().length, 0); assert.equal(ui.boundaryError.hidden, false);
}
''')

    def test_image_failure_is_visible_and_never_counts_as_loaded(self):
        self.run_js(r'''
setReview(review()); loadAll(); const first = imgs()[0]; first.onerror();
assert.equal(first.hidden, true); assert.equal(ui.boundaryError.hidden, false);
assert.match(ui.boundaryStatus.textContent, /^11 of 12.*incomplete: 1/);
assert.match(ui.boundaryRows.textContent, /Static PNG unavailable/);
first.onerror(); assert.match(ui.boundaryStatus.textContent, /^11 of 12.*incomplete: 1/);
''')

    def test_unexpected_crop_dimensions_fail_without_exposing_image(self):
        self.run_js(r'''
setReview(review()); const first = imgs()[0]; first.naturalWidth = 81; first.naturalHeight = 40; first.onload();
assert.equal(first.hidden, true); assert.equal(ui.boundaryError.hidden, false);
assert.match(ui.boundaryRows.textContent, /dimensions do not match/);
assert.match(ui.boundaryStatus.textContent, /^0 of 12.*incomplete: 1/);
''')

    def test_error_dominates_stale_review_and_old_image_callbacks(self):
        self.run_js(r'''
const data = review(); setReview(data); const stale = imgs();
setReview(data, {frame_review_error: '<img src=x onerror=alert(1)> manifest mismatch'});
assert.equal(imgs().length, 0); assert.equal(ui.boundaryProvenance.hidden, true);
assert.equal(ui.boundaryData.textContent, ''); assert.equal(ui.boundaryWarning.hidden, true);
assert.equal(ui.boundaryError.children.length, 0);
assert.match(ui.boundaryError.textContent, /<img src=x onerror=alert\(1\)> manifest mismatch/);
stale.forEach(img => {img.naturalWidth = 80; img.naturalHeight = 40; img.onload(); img.onerror();});
assert.match(ui.boundaryError.textContent, /manifest mismatch/);
assert.match(ui.boundaryStatus.textContent, /unavailable/);
setReview(undefined); stale[0].onerror();
assert.equal(ui.boundaryError.hidden, true); assert.match(ui.boundaryStatus.textContent, /No static/);
''')

    def test_loop_wrap_and_duplicate_frames_are_valid_and_optional_hash_can_be_absent(self):
        self.run_js(r'''
const data = review(); data.rows[0].frame = 30; data.rows[0].seconds = 1; data.rows[0].loop_wrap = true;
data.rows[3].frame = 30; data.rows[3].seconds = 1; data.rows[3].loop_wrap = true;
data.rows.forEach(row => Object.values(row.images).forEach(asset => delete asset.decoded_crop_rgb_sha256));
setReview(data); assert.equal(imgs().length, 12); assert.equal(ui.boundaryError.hidden, true);
assert.match(ui.boundaryRows.children[0].textContent, /loop wrap/);
assert.deepEqual(JSON.parse(ui.boundaryData.textContent), data);
''')

    def test_job_hash_mismatch_is_explicit(self):
        self.run_js(r'''
for (const extra of [{input_sha256: '2'.repeat(64)}, {prediction_sha256: '3'.repeat(64)}]) {
  setReview(review(), extra); assert.equal(imgs().length, 0);
  assert.match(ui.boundaryError.textContent, /does not match this job/);
}
const data = review(); setReview(data, {input_sha256: data.input_sha256, prediction_sha256: data.prediction_sha256});
assert.equal(imgs().length, 12);
''')

    def test_no_newly_timed_flag_means_no_warning_or_success_claim(self):
        self.run_js(r'''
const data = review(); data.strong_return_transition.newly_timed = false; setReview(data);
assert.equal(ui.boundaryWarning.hidden, true); loadAll();
assert.doesNotMatch(ui.boundaryStatus.textContent, /accepted|safe|preserved|pass/i);
''')

    def test_render_is_isolated_from_approval_and_preserves_summary_and_download_order(self):
        self.run_js(r'''
ui.approve.disabled = true; ui.reviewed.checked = true; ui.reviewed.disabled = false;
const summary = {selected_trigger_count: {control: 10, edited: 3, criterion_max: 3},
  checks: {selection: true}, warnings: ['Known measurement limitation']};
const artifacts = {'Original input': '/download/original.mp4', 'Control': '/download/control.mp4',
  'Edited': '/download/edited.mp4'};
api.setJob({frame_review: review(), summary, artifacts}); api.renderResults(); loadAll();
assert.equal(ui.results.hidden, false); assert.equal(ui.approve.disabled, true);
assert.equal(ui.reviewed.checked, true); assert.equal(ui.reviewed.disabled, false);
assert.deepEqual(JSON.parse(ui.raw.textContent), summary);
assert.match(ui.highlights.textContent, /Selected trigger count/);
assert.match(ui.highlights.textContent, /Known measurement limitation/);
assert.deepEqual(ui.artifacts.children.map(li => li.children[0].href), Object.values(artifacts));
api.setJob({frame_review_error: 'Missing PNG'}); api.renderResults();
assert.equal(ui.results.hidden, false); assert.equal(imgs().length, 0);
assert.match(ui.boundaryError.textContent, /Missing PNG/);
''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
