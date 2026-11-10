"""Recompute reported scores directly from saved traces, without grader helpers."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from gri_bench.runner import ROOT, dump, verify_runtime_lock


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='pilot-v1')
    p.add_argument('--expected',type=int,default=72);args=p.parse_args()
    verify_runtime_lock()
    trials=sorted((ROOT/'private/runs'/args.tag).glob('*/metadata.json'))
    if len(trials)!=args.expected:raise AssertionError(f'Expected {args.expected} attempts, found {len(trials)}')
    checked=0;failed=0;max_error=0.;max_cpu=0.;keys=set();errors=[]
    for mpath in trials:
        folder=mpath.parent;meta=json.loads(mpath.read_text());score=json.loads((folder/'score.json').read_text())
        key=(meta['instance_id'],meta['requested_model'] or meta['method'])
        assert key not in keys;keys.add(key)
        max_cpu=max(max_cpu,meta.get('cpu_seconds',0.))
        for name,expected in meta.get('artifact_sha256',{}).items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==expected
        if score['status']!='verified':
            assert score['safe_tir'] in (0.,None)
            failed+=1;continue
        archive=folder/'native-traces.npz'
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==score['native_traces_sha256']
        computed=[]
        with np.load(archive,allow_pickle=False) as z:
            assert len(z.files)==36
            for i,row in enumerate(score['rows']):
                a=z[f'trace_{i:02d}'];minute=z[f'minute_{i:02d}']
                assert a.shape==(1440,5) and minute.shape==(4321,)
                assert np.isfinite(a).all() and np.isfinite(minute).all()
                g=a[480:,0]
                raw={'tir':100*np.count_nonzero((g>=70)&(g<=180))/len(g),
                     'tbr70':100*np.count_nonzero(g<70)/len(g),
                     'tbr54':100*np.count_nonzero(g<54)/len(g),'minimum':float(minute.min()),
                     'mean_glucose':float(np.sum(g)/len(g))}
                for k,v in raw.items():
                    delta=abs(v-row['metrics'][k]);max_error=max(max_error,delta);assert delta<1e-9
                computed.append(raw)
        feasible=all(r['tbr70']<=4 and r['tbr54']<=1 and r['minimum']>=40 for r in computed)
        tir=sum(r['tir'] for r in computed)/18
        assert feasible==score['feasible']
        assert abs(score['mean_tir']-tir)<1e-9
        assert abs(score['safe_tir']-(tir if feasible else 0.))<1e-9
        public=json.loads((ROOT/'results'/args.tag/folder.name/'result.json').read_text())
        assert public['score']=={k:v for k,v in score.items() if k!='rows'}
        if meta['split']=='sealed':
            assert sorted(p.name for p in (ROOT/'results'/args.tag/folder.name).iterdir())==['result.json']
        checked+=1
    report={'passed':True,'attempts':len(trials),'verified_designs':checked,'failed_attempts_retained':failed,
            'native_trajectories_recomputed':checked*18,'maximum_metric_error':max_error,'maximum_measured_cpu_seconds':max_cpu,
            'note':'Independent arithmetic from saved native arrays; no submitted code executed and no model judge used.'}
    dump(ROOT/'results'/args.tag/'audit.json',report);print(json.dumps(report))


if __name__=='__main__':main()
