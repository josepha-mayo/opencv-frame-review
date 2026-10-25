"""Descriptive participant-level pilot summary. Never promotes QA into human data."""
import collections
import datetime
import itertools
import json
import re
import statistics

def summarize(records,starts,withdrawals,protocol_sha256,media_sha256,case_ids,cutoff):
    counts=collections.Counter(r.get('participant_id') for r in records if isinstance(r,dict) and isinstance(r.get('participant_id'),str))
    excluded=collections.Counter();valid=[];qa=0
    stop=datetime.datetime.fromisoformat(cutoff.replace('Z','+00:00'))
    for r in records:
        if not isinstance(r,dict):excluded['malformed_record']+=1;continue
        pid=r.get('participant_id','')
        if r.get('kind')=='qa' or r.get('is_qa') is True:qa+=1;continue
        if r.get('kind')!='human' or r.get('is_qa') is not False:excluded['unknown_provenance']+=1;continue
        if not isinstance(pid,str) or not re.fullmatch('[0-9a-f]{64}',pid):excluded['invalid_participant_key']+=1;continue
        if counts[pid]!=1:excluded['duplicate_records_quarantined']+=1;continue
        if pid in withdrawals:excluded['withdrawn']+=1;continue
        if (r.get('schema')!='lesson-reading-response-v1' or r.get('protocol_sha256')!=protocol_sha256 or r.get('media_sha256')!=media_sha256):excluded['binding_mismatch']+=1;continue
        try:
            submitted=datetime.datetime.fromisoformat(r['submitted_utc'])
            if submitted>stop:excluded['after_cutoff']+=1;continue
            cell=r['allocation_cell'];assert type(cell) is int and 0<=cell<12
            assert r['role'] in ('independent','team') and r['consent'] is True
            order=list(itertools.permutations(case_ids))[cell%6]
            assert [c['id'] for c in r['cases']]==list(order)
            for c in r['cases']:
                first='source' if (cell//6+case_ids.index(c['id']))%2==0 else 'edited'
                pref=c['preference'];expected=first if pref=='A' else ('edited' if first=='source' else 'source') if pref=='B' else pref
                assert first==c['first_variant'] and expected==c['decoded_preference']
        except (KeyError,ValueError,TypeError,AssertionError):excluded['malformed_or_allocation_mismatch']+=1;continue
        valid.append(r)
    groups={}
    for role in ('independent','team'):
        people=[r for r in valid if r['role']==role];majority=collections.Counter();case_counts={cid:collections.Counter() for cid in case_ids};differences=[];timing={'source':[],'edited':[]};reading={v:collections.Counter() for v in ('source','edited')};harm=collections.Counter();skips=collections.Counter()
        for r in people:
            votes=collections.Counter(c['decoded_preference'] for c in r['cases'])
            majority['edited_majority' if votes['edited']>=2 else 'source_majority' if votes['source']>=2 else 'no_majority']+=1
            own=[]
            for c in r['cases']:
                case_counts[c['id']][c['decoded_preference'] or 'skipped']+=1
                if c['answer'] is not None:
                    reading[c['first_variant']]['answered']+=1;reading[c['first_variant']]['correct']+=int(c['answer_correct'] is True)
                    if c['answer_ms'] is not None:timing[c['first_variant']].append(c['answer_ms'])
                if c['outcome']=='skipped':skips[c['skip_reason']]+=1;continue
                source=c['distraction_A'] if c['first_variant']=='source' else c['distraction_B'];edited=c['distraction_B'] if c['first_variant']=='source' else c['distraction_A'];own.append(source-edited)
                lost=c['lost_information'];decoded=c['first_variant'] if lost=='A' else ('edited' if c['first_variant']=='source' else 'source') if lost=='B' else lost;harm[decoded]+=1
            if own:differences.append(statistics.mean(own))
        groups[role]={'submitted_people':len(people),'participant_majority':dict(majority),'case_preferences_descriptive_not_independent_people':{k:dict(v) for k,v in case_counts.items()},'participant_mean_source_minus_edit_distraction':{'n':len(differences),'median':statistics.median(differences) if differences else None,'values':differences},'reading_first_exposure':{k:dict(v) for k,v in reading.items()},'answer_latency_ms_descriptive':{k:{'n':len(v),'median':statistics.median(v) if v else None} for k,v in timing.items()},'perceived_information_loss':dict(harm),'skips':dict(skips)}
    human_starts={s.get('iid') for s in starts if s.get('kind')=='human' and s.get('protocol')==protocol_sha256 and s.get('media')==media_sha256}
    return {'schema':'lesson-reading-summary-v1','protocol_sha256':protocol_sha256,'media_sha256':media_sha256,'cutoff_utc':cutoff,'human_invites_started':len(human_starts),'valid_human_submissions':len(valid),'qa_records_excluded':qa,'other_exclusions':dict(excluded),'groups':groups,'interpretation':'Invited self-reported convenience pilot. Descriptive preference/reading-feasibility observations only; no significance test, population inference, learning gain, attention authentication, accessibility/safety certification or measured editing-time saving. Zero human responses means no measured human outcome.'}

if __name__=='__main__':
    raise SystemExit('Use the authenticated collection/export script; never treat test fixtures as human records.')
