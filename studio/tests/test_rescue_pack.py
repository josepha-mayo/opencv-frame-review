import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rescue_pack import archive


class RescuePack(unittest.TestCase):
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
