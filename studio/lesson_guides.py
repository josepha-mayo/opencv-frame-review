"""Source-matched starting rectangles for reviewed examples, never approval."""
import re
from protected_regions import validate_regions

def guide_for(input_sha256, candidate, credit, shape):
    if not isinstance(input_sha256,str) or not re.fullmatch('[0-9a-f]{64}',input_sha256):return None
    if input_sha256!=credit.get('prepared_sample_sha256') or candidate.get('action')!='steady-detail-v1':return None
    spec=credit.get('reading_pause_guide')
    if not isinstance(spec,dict) or candidate.get('bbox')!=spec.get('candidate_bbox'):return None
    regions=validate_regions(spec.get('teaching_regions'),shape)
    if not regions:return None
    influence=candidate.get('influence_xywh')
    if not isinstance(influence,list) or len(influence)!=4 or any(type(v)is not int for v in influence):return None
    x,y,w,h=influence
    for area in regions:
        a,b,c,d=area['xywh']
        if max(x,a)<min(x+w,a+c) and max(y,b)<min(y+h,b+d):return None
    return {'source_sha256':input_sha256,'candidate_id':candidate['id'],'candidate_bbox':list(candidate['bbox']),
            'title':credit.get('label','Reviewed lesson example'),'focus':spec['focus'],'regions':regions,
            'scope':'Example starting areas matched to these prepared bytes and this candidate. Inspect and edit them, check the plan, and decide separately. No semantic detection or approval.'}
