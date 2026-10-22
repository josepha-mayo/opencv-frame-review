"""Controlled adversarial derivative of an existing owned synthetic fixture."""
import pathlib,sys,json,numpy as np
APP=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
import engine as e,native_yuv as ny
out=APP.parent/'adversarial-input-v1';out.mkdir(exist_ok=False);e.verify_runtime();e.BOUNDS=e.Bounds(out,'export')
try:
 source=APP.parents[1]/'opencv-recovery/rerun/workshop';e.probe(source/'input.mp4','source')
 component=json.loads((source/'prediction.json').read_text())['components'][0];mask=e.unpack_mask(component['mask_rle'],component['mask_shape']);selected=np.flatnonzero(mask);lo,hi=[round(t*30) for t in component['interval']]
 frames=list(ny.decode_yuv(e,source/'input.mp4','source'))
 for t in range(lo,hi+1):
  pixel=selected[(t-lo)%len(selected)];frames[t][pixel]=255 if frames[t][pixel]<128 else 0
 ny.encode_yuv(e,out/'sparse-nonperiodic.mp4',iter(frames),'adversarial')
 e.probe(out/'sparse-nonperiodic.mp4','adversarial',output_codec='h264')
 e.write_json(out/'fixture.json',{'purpose':'negative gate test, not product benefit evidence','source_sha256':e.sha(source/'input.mp4'),'output_sha256':e.sha(out/'sparse-nonperiodic.mp4'),'mutation':'one moving selected-luma pixel set to opposite endpoint per frame within detected interval'})
finally:e.BOUNDS.close()
