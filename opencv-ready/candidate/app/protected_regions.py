"""Creator-declared fixed rectangles; no text recognition or tracking."""
import math
CRITERIA={'mean_rgb_code_error':0.1,'p99_rgb_code_error':1,'max_rgb_code_error':3}
def validate_regions(regions,shape,mask_rle=None):
 if regions is None:regions=[]
 if not isinstance(regions,list) or len(regions)>4:raise ValueError('Choose at most four fixed protected rectangles.')
 h,w=shape;out=[]
 for item in regions:
  if not isinstance(item,dict) or set(item)!={'label','xywh'}:raise ValueError('Each protected area needs only a label and [x,y,width,height].')
  label=item['label'];box=item['xywh']
  if not isinstance(label,str) or not 1<=len(label.strip())<=40 or any(ord(c)<32 for c in label):raise ValueError('Protected-area labels must be 1 to 40 plain characters.')
  if not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box):raise ValueError('Protected rectangles need four integer pixel coordinates.')
  x,y,bw,bh=box
  if x<0 or y<0 or bw<1 or bh<1 or x+bw>w or y+bh>h:raise ValueError('Protected rectangle is outside the admitted image.')
  if any(r['label']==label.strip() for r in out):raise ValueError('Protected-area labels must be distinct.')
  out.append({'label':label.strip(),'xywh':list(box)})
 if mask_rle is not None:
  end=0
  for start,n in mask_rle:
   if type(start) is not int or type(n) is not int or start<end or n<=0 or start+n>h*w:raise ValueError('Invalid edit mask runs.')
   end=start+n
   for r in out:
    x,y,bw,bh=r['xywh']
    if any(max(start,row*w+x)<min(end,row*w+x+bw) for row in range(y,y+bh)):raise ValueError('A protected rectangle overlaps the proposed edit. Choose another candidate or leave the original unchanged.')
 return out
class RegionMeasure:
 def __init__(self,regions,np,cv2):
  self.regions=regions;self.np=np;self.cv2=cv2;self.hist=[np.zeros(256,np.int64) for _ in regions];self.frames=0
 def add(self,control,edited):
  if control.shape!=edited.shape or len(control.shape)!=3 or control.shape[2]!=3 or control.dtype!=self.np.uint8 or edited.dtype!=self.np.uint8:raise ValueError('Protected comparison requires matching RGB8 frames.')
  for r,hist in zip(self.regions,self.hist):
   x,y,w,h=r['xywh'];d=self.cv2.absdiff(control[y:y+h,x:x+w],edited[y:y+h,x:x+w])
   if d.shape[:2]!=(h,w):raise ValueError('Protected crop exceeds decoded frame.')
   for channel in range(3):hist+=self.cv2.calcHist([d],[channel],None,[256],[0,256]).ravel().astype(self.np.int64)
  self.frames+=1
 def result(self):
  rows=[]
  for r,hist in zip(self.regions,self.hist):
   count=int(hist.sum())
   if count==0:raise ValueError('Protected region has no measured frames.')
   values={'mean_rgb_code_error':float(self.np.dot(hist,self.np.arange(256))/count),'p99_rgb_code_error':int(self.np.searchsorted(self.np.cumsum(hist),math.ceil(.99*count))),'max_rgb_code_error':int(self.np.flatnonzero(hist)[-1])}
   rows.append(dict(r,measurements=values,criteria=dict(CRITERIA),passed=all(values[k]<=v for k,v in CRITERIA.items()),channel_samples=count,histogram=hist.tolist()))
  return {'regions':rows,'frames':self.frames,'declared':bool(rows),'passed':all(r['passed'] for r in rows) if rows else None,'scope':'Fixed creator-declared rectangles, every decoded frame, edited versus unchanged re-encode. This does not track objects, prove meaning/readability, or measure the source-to-control loss.'}
