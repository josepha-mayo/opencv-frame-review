import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rescue_pack import archive,offline_review
from html.parser import HTMLParser


class RescuePack(unittest.TestCase):
    def test_offline_proofs_embed_checked_images_and_escape_creator_labels(self):
        png=b'\x89PNG\r\n\x1a\nfixture';asset={'filename':'proof.png','sha256':hashlib.sha256(png).hexdigest()}
        report={'input_sha256':'a'*64,'recipe_sha256':'b'*64,'summary':{'stationary_detail':{'activity':{'source':5,'edited':0},'whole_clip_activity':{'source':8,'edited':2},'new_activity_events':0},'checks':{'audio_exact':True}},'frame_review':{'rows':[{'label':'Before edit','frame':2,'images':{'original':asset,'edited':asset}}]},'teaching_review':{'regions':[{'label':'<img src=x onerror=alert(1)>','xywh':[0,0,8,8],'frames':360,'ordered_rgb_sequence_exact':True,'ordered_rgb_sequence_sha256':{'source':'c'*64,'edited':'c'*64},'moments':[{'frame':3,'roles':['<script>bad()</script>'],'images':{'source':asset,'edited':asset}}]}]}}
        members={'proof.png':png,'report.json':b'{}','prepared-lesson.mp4':b'media'}
        page=offline_review(report,members).decode();tags=[]
        class Read(HTMLParser):
            def handle_starttag(self,tag,attrs):tags.append((tag,dict(attrs)))
        Read().feed(page)
        self.assertFalse(any(t in ('script','video','audio','iframe','form')for t,a in tags))
        self.assertTrue(all(not k.startswith('on')for t,a in tags for k in a))
        imgs=[a for t,a in tags if t=='img'];self.assertEqual(len(imgs),4)
        self.assertTrue(all(a['src'].startswith('data:image/png;base64,')for a in imgs))
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;',page);self.assertIn('&lt;script&gt;bad()&lt;/script&gt;',page)
        self.assertIn("default-src 'none'",page)
        self.assertIn('does not record creator acceptance',page);self.assertIn('manifest.json',page)
        with self.assertRaises(ValueError):offline_review(report,{**members,'proof.png':png+b'changed'})

    def test_portable_archive_has_exact_hashes_fixed_names_and_no_executable_members(self):
        members={'prepared-lesson.mp4':b'source bytes','report.json':b'{}'}
        payload=archive(members,{'input_sha256':'a'*64})
        self.assertEqual(payload,archive(members,{'input_sha256':'a'*64}))
        with zipfile.ZipFile(io.BytesIO(payload))as z:
            self.assertIsNone(z.testzip());self.assertEqual(set(z.namelist()),set(members)|{'manifest.json'})
            manifest=json.loads(z.read('manifest.json'))
            for name,data in members.items():
                self.assertEqual(z.read(name),data)
                self.assertEqual(manifest['files'][name],{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
                self.assertEqual((z.getinfo(name).external_attr>>16)&0o777,0o644)
                self.assertEqual(z.getinfo(name).compress_type,zipfile.ZIP_STORED)

    def test_archive_refuses_traversal_reserved_names_nonbytes_and_size_overrun(self):
        for members in ({'../owner.txt':b'x'},{'x\\owner.txt':b'x'},{'manifest.json':b'x'},{'.':b'x'},{'report.json':'text'},{}):
            with self.assertRaises(ValueError):archive(members,{})
        with self.assertRaises(ValueError):archive({'large.mp4':b'12345'},{},limit=4)
        with self.assertRaises(ValueError):archive({str(i):b'x'for i in range(65)},{})
