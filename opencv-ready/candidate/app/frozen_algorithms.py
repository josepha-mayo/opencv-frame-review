"""Original research functions, copied without changing their ASTs.
Globals are supplied by engine.py in an isolated serial worker.
"""

def detector(rgb_frames,timestamps):
 """Input boundary is only decoded pixels/timestamps. Never receives case/labels."""
 cfg=P['detector'];prev=None;events=[];oldest=0;processed=0
 for t,a in enumerate(rgb_frames):
  now=cv2.transform(cv2.LUT(a,LUT),WEIGHTS)
  if prev is None:
   sh=now.shape;lastdir=np.zeros(sh,np.int8);counts=np.zeros(sh,np.int16);union=np.zeros(sh,np.uint8);first=np.full(sh,np.inf,np.float64);ev=np.zeros(sh,np.uint8)
  else:
   delta=cv2.subtract(now,prev);directions=np.where(delta>0,1,-1).astype(np.int8)
   qualifies=(np.abs(delta)>=cfg['adjacent_delta_min'])&(np.minimum(now,prev)<cfg['darker_max_exclusive'])
   ev=(qualifies&(directions!=lastdir)).astype(np.uint8);lastdir[ev!=0]=directions[ev!=0]
  events.append(ev);counts+=ev
  while oldest<t and timestamps[oldest]<=timestamps[t]-cfg['window_seconds']:
   counts-=events[oldest];oldest+=1
  active=counts>=cfg['transition_min'];new=active&(union==0);first[new]=timestamps[t];union[active]=1;prev=now;processed+=1;guard()
 if processed!=len(timestamps):raise RuntimeError('DETECTOR_TIMESTAMP_LENGTH')
 n,lab,stats,centers=cv2.connectedComponentsWithStats(union,connectivity=cfg['connectivity']);components=[];discarded=[]
 for i in range(1,n):
  area=int(stats[i,cv2.CC_STAT_AREA]);bbox=[int(x) for x in stats[i,:4]]
  if area<cfg['component_area_min_pixels']:discarded.append({'area':area,'bbox':bbox});continue
  mask=(lab==i).astype(np.uint8);times=[timestamps[j] for j,ev in enumerate(events) if cv2.countNonZero(cv2.bitwise_and(ev,mask))>0]
  assert times
  components.append({'area':area,'bbox':bbox,'mask_shape':list(mask.shape),'mask_rle':packed_mask(mask),'first_candidate_timestamp':float(np.min(first[mask!=0])),'interval':[min(times),max(times)],'qualifying_adjacent_event_timestamps':times})
 return {'components':components,'discarded_components':discarded,'frames':processed,'pixel_shape':list(sh),'candidate_union_pixels':int(cv2.countNonZero(union)),'method':cfg}

def temporal(y, frames, adjacent_only=False):
    y=np.asarray(y, dtype=np.float64)
    frames=np.asarray(frames, dtype=np.int64)
    if adjacent_only:
        pairs=[(i-1,i) for i in range(1,len(y))]
    else:
        change=[0]+[i for i in range(1,len(y)) if y[i] != y[i-1]]
        extrema=[change[0]]
        for j in range(1,len(change)-1):
            a,b,c=change[j-1:j+2]
            if (y[b]-y[a])*(y[c]-y[b]) < 0:
                extrema.append(b)
        if change[-1] != extrema[-1]: extrema.append(change[-1])
        pairs=list(zip(extrema[:-1],extrema[1:]))
    candidates=[]
    emitted=[]
    for a,b in pairs:
        delta=float(y[b]-y[a])
        low=float(min(y[a],y[b]))
        if abs(delta) < .1 or low >= .8: continue
        direction=1 if delta>0 else -1
        cross=None
        for j in range(a+1,b+1):
            if abs(float(y[j]-y[a])) >= .1 and min(float(y[j]),float(y[a])) < .8:
                cross=j; break
        if cross is None: raise RuntimeError("QUALIFIED_WITHOUT_CROSSING")
        e={"frame":int(frames[cross]),"direction":direction,"start_frame":int(frames[a]),"end_frame":int(frames[b]),"amplitude":abs(delta),"threshold_margin":abs(delta)-.1,"darker_endpoint":low}
        e["counted"] = not emitted or direction != emitted[-1]["direction"]
        candidates.append(e)
        if e["counted"]: emitted.append(e.copy())
    ef=np.array([e["frame"] for e in emitted], dtype=np.int64)
    counts=[int(np.count_nonzero((ef>int(t)-30)&(ef<=int(t)))) for t in frames]
    flagged=[int(t) for t,n in zip(frames,counts) if n>=7]
    return {"flagged":bool(flagged),"flagged_frames":flagged,"max_count":max(counts,default=0),"counts":counts,"events":candidates}
