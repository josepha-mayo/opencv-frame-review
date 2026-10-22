"""Source-level interface contracts only; these are not browser interaction tests."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

APP = Path(__file__).resolve().parents[1]


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))

    def handle_data(self, data):
        self.text.append(data)


class StaticReviewContracts(unittest.TestCase):
    def setUp(self):
        self.html = (APP / 'static/index.html').read_text()
        self.js = (APP / 'static/app.js').read_text()
        self.document = Document(self.html)
        self.text = ' '.join(self.document.text)
        self.ids = {a['id']: (tag, a) for tag, a in self.document.elements if 'id' in a}

    def test_audio_contract_is_refusal_not_muting(self):
        self.assertIn('Optional AAC-LC mono 48 kHz only', self.html)
        self.assertNotIn('<dd>Muted</dd>', self.html)

    def test_generation_consent_and_tradeoff_are_explicit(self):
        for phrase in ['Generate comparison', 'want to generate this edit for comparison',
                       'each 10-frame block', 'changes the animation',
                       'abrupt change when the original frames resume',
                       'change pixels outside the region',
                       'does not accept the output for use']:
            self.assertIn(phrase, self.text)
        self.assertNotIn('Approve this candidate & encode', self.text)

    def test_summary_disclosure_matches_actual_payload(self):
        self.assertIn('<summary>Summary JSON</summary>', self.html)
        self.assertNotIn('Full result report', self.text)
        self.assertIn('JSON.stringify(summary, null, 2)', self.js)

    def test_static_only_elements_and_assets(self):
        for tag, attrs in self.document.elements:
            self.assertNotIn(tag, {'video', 'audio', 'canvas', 'iframe', 'object', 'embed'})
            self.assertNotIn('autoplay', attrs)
            if 'src' in attrs:
                self.assertTrue(attrs['src'].startswith('/static/'))
        self.assertNotRegex(self.js, r'\.play\s*\(')

    def test_unique_ids_and_script_bindings_remain_available(self):
        values = [a['id'] for _, a in self.document.elements if 'id' in a]
        self.assertEqual(len(values), len(set(values)))
        self.assertTrue(set(re.findall(r'byId\("([^"]+)"\)', self.js)) <= set(self.ids))

    def test_initial_consent_controls_are_disabled(self):
        for key in ['clip-file', 'analyze-button', 'approve-button']:
            self.assertIn('disabled', self.ids[key][1])
        self.assertEqual(self.ids['review-checkbox'][1]['type'], 'checkbox')
        self.assertIn('hidden', self.ids['candidate-area'][1])
        self.assertIn('hidden', self.ids['results-panel'][1])

    def test_source_contains_no_implicit_approval_or_autoretry(self):
        self.assertIn('if (ui.approve.disabled) return;', self.js)
        self.assertIn('!imageLoaded || !ui.reviewed.checked', self.js)
        self.assertIn('prediction_sha256: job.prediction_sha256', self.js)
        self.assertIn('recipe_sha256: protectionPlan.recipe_sha256', self.js)
        self.assertIn('The decision was not retried.', self.js)


if __name__ == '__main__':
    unittest.main(verbosity=2)
