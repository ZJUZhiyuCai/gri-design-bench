"""Independent arithmetic checks over saved query ledgers and chosen designs."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'private/search-validation-prescreen-2026-11-13'
EXP=ROOT/'experiments/search-validation-prescreen-2026-11-13'

def read(p):return json.loads(p.read_text())
def loss(m,margin=True):
    t70,t54,g=(3.,.5,45.) if margin else (4.,1.,40.)
    v=max(0.,m['max_trajectory_tbr70']-t70)+4*max(0.,m['max_trajectory_tbr54']-t54)+max(0.,g-m['minimum_glucose'])/5
    return (1000+100*v if v else 0)-m['mean_tir']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=read(EXP/'plan.json');files=[];count=0;events=0
    for case in p['cases']:
        for rep in range(1,6):
            path=BASE/'search'/f'{case}-r{rep}.json';x=read(path);files.append(path)
            assert x['plan_sha256']==sha(EXP/'plan.json')
            for label,expected in [('de',128),('sobol',64),('constant',128)]:
                d=x['details'][label];archive=d['archive'];assert len(archive)==expected
                for i,(r,e) in enumerate(zip(archive,d['training_events'],strict=True)):
                    assert r['index']==i and r['queries']==2*(i+1)
                    assert e['query_end']==2*(i+1) and e['seeds']==p['panels'][case]['training']
                    assert e['metrics']['trajectories']==18
                    assert r['design']==e['design'] and abs(r['loss']-loss(e['metrics']))<1e-10
                    assert r['training']==e['metrics']
                checked=d['fixed_validation']['candidates'];ev=d['fixed_validation']['events']
                assert len(checked)==len(ev)==8
                assert ev[-1]['query_end']==128
                for e in ev:
                    assert e['seeds']==p['panels'][case]['validation'][:16]
                    assert e['metrics']['trajectories']==144
                for r in checked:
                    assert r['candidate_index']<64 and r['design']==archive[r['candidate_index']]['design']
                    event=next(e for e in ev if e['design']==r['design']);assert event['metrics']==r['validation']
                best=min(checked,key=lambda r:(loss(r['validation']),r['candidate_index']))
                assert x['methods'][label+'_fixed']['design']==best['design']
                if label in ('de','constant'):
                    best=min(archive,key=lambda r:(loss(r['training']),r['index']))
                    assert x['methods'][label+'_search']['design']==best['design']
                events+=len(archive)+len(ev)
            d=x['details']['de'];early=min(d['archive'][:64],key=lambda r:(loss(r['training']),r['index']))
            assert x['methods']['de_early']['design']==early['design']
            best=min(d['fixed_validation']['candidates'],key=lambda r:(loss(r['validation'],False),r['candidate_index']))
            assert x['methods']['de_no_margin']['design']==best['design']
            stages=x['details']['racing']['stages'];ev=x['details']['racing']['events']
            assert [len(s['candidates']) for s in stages]==[8,4,2]
            assert ev[-1]['query_end']==128 and len(ev)==14
            assert all(r['candidate_index']<64 for s in stages for r in s['candidates'])
            best=min(stages[-1]['candidates'],key=lambda r:(loss(r['validation']),r['candidate_index']))
            assert x['methods']['de_racing']['design']==best['design']
            assert all(r['query_units']==(128 if name=='de_early' else 256) for name,r in x['methods'].items())
            count+=len(x['methods']);events+=len(ev)
    record={'plan_sha256':sha(EXP/'plan.json'),'jobs_checked':len(files),'method_outputs_checked':count,'query_event_records_checked':events,
            'search_file_hashes':{str(f.relative_to(BASE)):sha(f) for f in files},
            'checks':'Independent loss arithmetic, all common-prefix indices, declared seed panels, query costs, and selected output designs.'}
    output=BASE/'selection-audit.json'
    with output.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print({k:v for k,v in record.items() if k!='search_file_hashes'})

if __name__=='__main__':main()
