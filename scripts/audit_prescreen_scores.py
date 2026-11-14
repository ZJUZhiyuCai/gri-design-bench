"""Recompute saved scores independently from rows and native numeric arrays."""
import argparse
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'private/search-validation-prescreen-2026-11-13'
PLAN=ROOT/'experiments/search-validation-prescreen-2026-11-13/plan.json'

def close(a,b):
    if abs(float(a)-float(b))>1e-10:raise AssertionError((a,b))
def aggregate(rows):
    mm=[r['metrics'] for r in rows];tir=float(np.mean([m['tir'] for m in mm]));t70=max(m['tbr70'] for m in mm);t54=max(m['tbr54'] for m in mm);g=min(m['minimum'] for m in mm)
    feasible=t70<=4 and t54<=1 and g>=40
    return {'mean_tir':tir,'safe_tir':tir if feasible else 0.,'feasible':feasible,'max_trajectory_tbr70':t70,'max_trajectory_tbr54':t54,'minimum_glucose':g}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    plan=json.loads(PLAN.read_text());screen_count=0;native_count=0;max_error=0.
    for p in sorted((BASE/'screen').glob('*.json')):
        x=json.loads(p.read_text());seeds=plan['panels'][x['case']]['evaluation'];assert len(x['rows'])==288
        for which,rows in [('primary',[r for r in x['rows'] if r['seed'] in seeds[:16]]),('expanded',x['rows'])]:
            computed=aggregate(rows)
            for k,v in computed.items():close(v,x[which][k])
            failed=sum(not(m['metrics']['tbr70']<=4 and m['metrics']['tbr54']<=1 and m['metrics']['minimum']>=40) for m in rows)
            close(failed,x[which]['failed_trajectories']);close(failed/len(rows),x[which]['violation_fraction'])
        screen_count+=1
    for p in sorted((BASE/'native').glob('*/*.json')):
        x=json.loads(p.read_text());npz=p.with_suffix('.npz');assert hashlib.sha256(npz.read_bytes()).hexdigest()==x['trace_sha256']
        with np.load(npz) as data:
            trace=data['trace'];minute=data['minute'];assert trace.shape==(1440,5) and minute.shape==(4321,)
            assert np.isfinite(trace).all() and np.isfinite(minute).all()
            bg=trace[480:,0]
            m={'tir':100*float(np.count_nonzero((bg>=70)&(bg<=180)))/len(bg),'tbr70':100*float(np.count_nonzero(bg<70))/len(bg),
               'tbr54':100*float(np.count_nonzero(bg<54))/len(bg),'minimum':float(np.min(minute)),'mean_glucose':float(np.mean(bg))}
            for k,v in m.items():close(v,x['metrics'][k]);max_error=max(max_error,abs(v-x['metrics'][k]))
        native_count+=1
    result={'screen_designs_recomputed':screen_count,'native_trajectories_recomputed_from_arrays':native_count,'maximum_metric_discrepancy':max_error,
            'scope':'Independent arithmetic; not an independent biological model.'}
    with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(result)
if __name__=='__main__':main()
