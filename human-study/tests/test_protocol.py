"""Memory-only fixtures. These are not human participants or cloud records."""
from pathlib import Path
import copy,hashlib,json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study_server import Study,Forbidden,Conflict,canonical,digest
from analyze import summarize

class Memory:
    def __init__(self):self.data={}
    def put(self,key,value,once=False):
        if once and key in self.data:raise Conflict('Already recorded.')
        self.data[key]=copy.deepcopy(value)
    def media_url(self,key):return 'https://media.invalid/'+key+'.webm'

class Protocol(unittest.TestCase):
    def setUp(self):
        self.protocol=json.loads((Path(__file__).resolve().parents[1]/'protocol.json').read_text(encoding='utf-8'))
        self.codes={'human':'a'*32,'qa':'b'*32};self.invites={digest(v.encode()):{'kind':k,'cell':0} for k,v in self.codes.items()}
        variants={v:{'sha256':('c' if v=='source' else 'd')*64,'native_samples_exact':True,'all_teaching_rgb_digests_match_pinned_linux':True,'audio_tracks':0} for v in ('source','edited')}
        self.media={'complete':True,'cases':{c['id']:{**copy.deepcopy(variants),'matched_timestamp_sequences':True} for c in self.protocol['cases']}}
        self.store=Memory();self.clock=1792920000
        self.study=Study(self.protocol,self.media,self.invites,b'k'*48,self.store,opened=True,clock=lambda:self.clock)
    def start(self,kind='human',role='independent'):
        return self.study.start(dict(invite=self.codes[kind],consent=True,role=role,experience='sometimes',device='computer'))
    def response(self,start,pref='A'):
        rows=[]
        for c in start['cases']:
            rows.append(dict(id=c['id'],outcome='completed',answer=c['options'][0]['id'],answer_ms=1000,preference=pref,distraction_A=3,distraction_B=2,lost_information='neither',skip_reason=None,telemetry={s:{'ended':True,'watched_seconds':12,'plays':1,'error':False} for s in ('A','B')}))
        return {'session':start['session'],'cases':rows}
    def summary(self):
        records=[v for k,v in self.store.data.items() if k.startswith(('results/','qa-results/'))]
        starts=[v for k,v in self.store.data.items() if k.startswith(('starts/','qa-starts/'))]
        withdrawals={k.split('/')[1].split('.')[0] for k in self.store.data if k.startswith('withdrawals/')}
        return summarize(records,starts,withdrawals,self.study.protocol_hash,self.study.media_hash,list(self.study.cases),self.protocol['closes_utc'])
    def test_balanced_block_and_blinded_first_exposure(self):
        appearances={c:[0,0,0] for c in self.study.cases};source_a={c:0 for c in self.study.cases}
        for cell in range(12):
            order,a=self.study.layout({'cell':cell})
            for i,c in enumerate(order):appearances[c][i]+=1;source_a[c]+=int(a[c]=='source')
        self.assertTrue(all(v==[4,4,4] for v in appearances.values()));self.assertTrue(all(v==6 for v in source_a.values()))
        session=self.start();self.assertNotIn('correct',session['cases'][0]);self.assertNotIn('ground_truth',session['cases'][0]);self.assertNotIn('first_variant',session['cases'][0])
    def test_no_human_results_from_qa_and_no_duplicate_overwrite(self):
        start=self.start('qa');data=self.response(start)
        reply=self.study.submit(data);self.assertTrue(reply['is_qa'])
        before=copy.deepcopy(self.store.data)
        with self.assertRaises(Conflict):self.study.submit(self.response(start,'B'))
        self.assertEqual(before,self.store.data);s=self.summary();self.assertEqual(s['valid_human_submissions'],0);self.assertEqual(s['qa_records_excluded'],1)
    def test_negative_preference_and_wrong_answer_are_retained(self):
        start=self.start();data=self.response(start)
        for row in data['cases']:
            row['answer']='unreadable';row['preference']='A' if self.study.layout(self.invites[digest(self.codes['human'].encode())])[1][row['id']]=='source' else 'B'
        self.study.submit(data);s=self.summary();self.assertEqual(s['groups']['independent']['participant_majority']['source_majority'],1)
        self.assertEqual(sum(v.get('correct',0) for v in s['groups']['independent']['reading_first_exposure'].values()),0)
    def test_all_skips_are_no_majority_not_dropped(self):
        start=self.start();data=self.response(start)
        for row in data['cases']:row.update(outcome='skipped',answer=None,answer_ms=None,preference=None,distraction_A=None,distraction_B=None,lost_information=None,skip_reason='playback_error')
        self.study.submit(data);s=self.summary();self.assertEqual(s['groups']['independent']['submitted_people'],1);self.assertEqual(s['groups']['independent']['participant_majority']['no_majority'],1)
    def test_closed_collection_stale_session_extra_personal_fields_and_withdrawal(self):
        start=self.start();self.study.submit(self.response(start));self.study.withdraw({'invite':self.codes['human']});self.assertEqual(self.summary()['valid_human_submissions'],0)
        with self.assertRaises(Forbidden):self.study.session(start['session']+'tamper')
        self.clock+=3601
        with self.assertRaises(Forbidden):self.study.session(start['session'])
        with self.assertRaises(ValueError):self.study.start(dict(invite=self.codes['human'],consent=True,role='independent',experience='never',device='phone',email='must-not-be-collected'))
        self.study.opened=False
        with self.assertRaises(Conflict):self.start()
        self.assertTrue(self.start('qa')['is_qa'])
    def test_incomplete_playback_cannot_become_a_complete_trial(self):
        start=self.start();data=self.response(start);data['cases'][0]['telemetry']['A']['watched_seconds']=1
        with self.assertRaises(ValueError):self.study.submit(data)
        self.assertFalse(any(k.startswith('results/') for k in self.store.data))

if __name__=='__main__':unittest.main()
