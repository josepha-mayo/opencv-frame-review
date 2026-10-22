"""Standard-library guards for the CPU-independent reference lookup table."""
import ast,hashlib,pathlib,struct,unittest
APP=pathlib.Path(__file__).resolve().parents[1]
class DeterministicTable(unittest.TestCase):
 def values(self):
  tree=ast.parse((APP/'engine.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LUT' for t in n.targets));return ast.literal_eval(node.value.func.value.args[0])
 def test_exact_original_float32_bits(self):
  values=self.values();self.assertEqual(len(values),256);self.assertEqual(hashlib.sha256(struct.pack('<256I',*values)).hexdigest(),'5fb526639a8a5b1b9d026ef9ce67eb3d568ab9f7086150fad0e7b110261d16e2')
 def test_finite_monotonic_endpoints(self):
  values=struct.unpack('<256f',struct.pack('<256I',*self.values()));self.assertEqual(values[0],0.);self.assertEqual(values[-1],1.);self.assertTrue(all(a<=b for a,b in zip(values,values[1:])));self.assertTrue(all(0<=v<=1 for v in values))
if __name__=='__main__':unittest.main()
