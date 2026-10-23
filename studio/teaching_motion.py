"""Ordered decoded teaching-frame evidence; no semantic or human-benefit claim."""
import hashlib
import struct


class TeachingMotion:
    def __init__(self, regions, interval, frames, np):
        self.np=np;self.lo,self.hi=interval;self.frames=frames;self.seen=0
        if not 0<=self.lo<=self.hi<frames:raise ValueError('Invalid teaching proof interval')
        self.rows=[]
        for region in regions:
            self.rows.append({'label':region['label'],'xywh':list(region['xywh']),
                              'digests':{k:hashlib.sha256() for k in ('source','edited')},
                              'previous':{},'changed_pairs':{'source':0,'edited':0},
                              'hold_changed_pairs':{'source':0,'edited':0},
                              'absolute_change_sum':{'source':0,'edited':0},
                              'peak_change_mean':-1,'peak_frame':self.lo,'moments':{}})

    def add(self,t,source,edited):
        if t!=self.seen or t>=self.frames:raise ValueError('Teaching frames must be complete and ordered')
        self.seen+=1;np=self.np
        for row in self.rows:
            x,y,w,h=row['xywh'];patches={k:np.ascontiguousarray(frame[y:y+h,x:x+w]) for k,frame in [('source',source),('edited',edited)]}
            if any(p.shape!=(h,w,3) for p in patches.values()):raise ValueError('Teaching crop outside decoded frame')
            change=0
            for role,patch in patches.items():
                row['digests'][role].update(struct.pack('>I',t));row['digests'][role].update(patch.tobytes())
                if role in row['previous']:
                    delta=np.abs(patch.astype(np.int16)-row['previous'][role].astype(np.int16));total=int(delta.sum())
                    row['absolute_change_sum'][role]+=total;row['changed_pairs'][role]+=int(total>0)
                    if self.lo<t<=self.hi:
                        row['hold_changed_pairs'][role]+=int(total>0)
                        if role=='source':change=total/patch.size
                row['previous'][role]=patch.copy()
            if t in (self.lo,self.hi):row['moments'][t]={k:p.copy() for k,p in patches.items()}
            if self.lo<t<=self.hi and change>row['peak_change_mean']:
                previous_peak=row['peak_frame']
                if previous_peak not in (self.lo,self.hi):row['moments'].pop(previous_peak,None)
                row['peak_frame']=t;row['peak_change_mean']=change;row['moments'][t]={k:p.copy() for k,p in patches.items()}

    def result(self):
        if self.seen!=self.frames:raise ValueError('Teaching proof lacks decoded frames')
        rows=[]
        for row in self.rows:
            sequence={k:d.hexdigest() for k,d in row['digests'].items()};x,y,w,h=row['xywh']
            rows.append({'label':row['label'],'xywh':row['xywh'],'frames':self.frames,
                         'ordered_rgb_sequence_sha256':sequence,'ordered_rgb_sequence_exact':sequence['source']==sequence['edited'],
                         'changed_adjacent_frame_pairs':row['changed_pairs'],'changed_pairs_inside_hold':row['hold_changed_pairs'],
                         'adjacent_pairs':self.frames-1,'hold_adjacent_pairs':self.hi-self.lo,
                         'mean_absolute_temporal_rgb_codes':{k:v/max(1,(self.frames-1)*w*h*3) for k,v in row['absolute_change_sum'].items()},
                         'peak_change_frame_inside_hold':row['peak_frame'],'peak_change_mean_rgb_codes':max(0,row['peak_change_mean'])})
        return {'schema':'teaching-motion-v1','frames':self.frames,'interval_frames':[self.lo,self.hi],'regions':rows,
                'all_ordered_rgb_sequences_exact':all(r['ordered_rgb_sequence_exact'] for r in rows),
                'meaning':'Decoded sample changes, including codec variation; not semantic progress ticks, legibility or learning measurements. Source and edited teaching regions are compared at their original frame times.'}

    def write_review(self,job,cv2,binding):
        review=self.result();review.update(binding)
        for i,(row,measured) in enumerate(zip(self.rows,review['regions'])):
            measured['moments']=[]
            for t,patches in sorted(row['moments'].items()):
                moment={'frame':t,'seconds':t/30,'roles':[],'images':{}}
                if t==self.lo:moment['roles'].append('Hold begins')
                if t==row['peak_frame']:moment['roles'].append('Largest measured teaching change inside hold')
                if t==self.hi:moment['roles'].append('Hold ends')
                for role,patch in patches.items():
                    name=f'teaching-r{i}-f{t:05d}-{role}.png';path=job/name
                    if not cv2.imwrite(str(path),cv2.cvtColor(patch,cv2.COLOR_RGB2BGR)):raise ValueError('Teaching PNG could not be written')
                    moment['images'][role]={'filename':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'decoded_rgb_sha256':hashlib.sha256(patch.tobytes()).hexdigest(),'width':patch.shape[1],'height':patch.shape[0]}
                measured['moments'].append(moment)
        return review
