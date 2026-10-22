import copy,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from audio_preserve import validate_streams,compare,validate_presentation
from acceptance import finalize_candidate
class AudioContract(unittest.TestCase):
 def setUp(self):
  self.meta={'streams':[{'codec_type':'video'},{'codec_type':'audio','codec_name':'aac','profile':'LC','codec_tag_string':'mp4a','sample_rate':'48000','channels':1,'channel_layout':'mono','time_base':'1/48000','start_pts':0,'duration_ts':144000}]}
 def test_canonical_presentation_and_rate_volume_rejections(self):
  source=pathlib.Path(__file__).resolve().parents[2]/'fixtures/p2-audio.mp4'
  self.assertTrue(all(validate_presentation(source,3).values()))
  raw=source.read_bytes()
  for old,new in [(bytes.fromhex('000000000000000100000bb80000040000010000'),bytes.fromhex('000000000000000100000bb80000040000020000')),(bytes.fromhex('000000030000000000000000000000020000000000000bb8'),bytes.fromhex('000000020000000000000000000000020000000000000bb8'))]:
   self.assertEqual(raw.count(old),1)
   with tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp)/'changed.mp4';p.write_bytes(raw.replace(old,new))
    with self.assertRaises(ValueError):validate_presentation(p,3)
 def test_supported(self):self.assertTrue(validate_streams(self.meta,3))
 def test_silent(self):self.assertFalse(validate_streams({'streams':self.meta['streams'][:1]},3))
 def test_unsupported(self):
  for key,value in [('codec_name','alac'),('profile','HE-AAC'),('sample_rate','44100'),('channels',2),('start_pts',1024),('duration_ts',143999),('time_base','1/1000')]:
   m=copy.deepcopy(self.meta);m['streams'][1][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):validate_streams(m,3)
  m=copy.deepcopy(self.meta);m['streams'].append(m['streams'][1])
  with self.assertRaises(ValueError):validate_streams(m,3)
 def test_each_evidence_change_rejected(self):
  a={'stream':{'time_base':'1/48000'},'packets':[{'pts':-1024,'data_hash':'abc','side_data_list':[{'skip_samples':1024}]}],'pcm_sha256':'abc','pcm_bytes':100}
  for field,value in [('stream',{}),('packets',[]),('pcm_sha256','bad'),('pcm_bytes',99)]:
   b=copy.deepcopy(a);b[field]=value
   with self.subTest(field=field):self.assertFalse(all(compare(a,b).values()))
 def test_gate_keeps_audio_failure_diagnostic(self):
  base=pathlib.Path(__file__).resolve().parents[2]/'api-audio-v1/result.json'
  outcomes=json.loads(base.read_text())['outcomes'];jid=outcomes['p2']['job_id']
  data=json.loads((base.parent/'jobs'/jid/'result.json').read_text())
  for key in ('stream_exact','packet_payload_timing_skip_exact','decoded_pcm_exact'):
   d=copy.deepcopy(data);d['audio_preservation']['checks']['edited'][key]=False
   with tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);pending=root/'pending.mp4';pending.write_bytes(b'diagnostic')
    self.assertFalse(finalize_candidate(d,pending,root,accepted_name='edited.mp4'))
    self.assertFalse((root/'edited.mp4').exists());self.assertTrue((root/'rejected-candidate.mp4').exists())
if __name__=='__main__':unittest.main()
