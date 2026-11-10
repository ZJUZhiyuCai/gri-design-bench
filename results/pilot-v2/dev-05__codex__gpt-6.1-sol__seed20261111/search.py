"""Deterministic shared-formulation search using the public physiology.
Run: OPENBLAS_NUM_THREADS=1 python /work/output/search.py all
Or run individual phases: screen, refine, shape, robust, polish, validate, native.
All candidate designs and scenario results are checkpointed in results.jsonl.
"""
import os, json, sys, time, subprocess
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, save_design, validate_design
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')
INSTANCE=load_instance()

def design(a, ec=150, n=12, tau=0.05, leak=1.5, load=4):
    return {'mode':'responsive','parameters':dict(theta_a=a,relative_leak=leak,ec50_mg_dl=ec,hill_n=n,tau_min=tau,theta_L=load)}

def evaluate(ex, d, substeps=1):
    validate_design(d, INSTANCE)
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,INSTANCE['tdi'][name]),substeps=substeps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace)))
    return dict(**summarize(rows),rows=rows)

def record(d,m,phase):
    r=dict(design=d,metrics=m,phase=phase)
    with (OUT/'results.jsonl').open('a') as f: f.write(json.dumps(r)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='metrics'}),json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
    return r

def select(records):
    # A deliberate margin protects against new meals and numerical differences.
    safe=[r for r in records if r['metrics']['max_trajectory_tbr70']<=1 and r['metrics']['max_trajectory_tbr54']==0 and r['metrics']['minimum_glucose']>=60]
    if safe:
        best=max(safe,key=lambda r:r['metrics']['mean_tir'])
        save_design(best['design'])
        (OUT/'selected.json').write_text(json.dumps(best,indent=2))
    return safe

if __name__=='__main__':
    phase=sys.argv[1] if len(sys.argv)>1 else 'screen'
    if phase=='all':
        for name in ['screen','refine','shape','robust','polish','validate','native']:
            subprocess.run([sys.executable,__file__,name],check=True)
        raise SystemExit
    if phase=='native':
        from gri_bench.native import native_trace
        chosen=json.loads((OUT/'selected.json').read_text())
        worst=min(chosen['metrics']['rows'],key=lambda r:r['metrics']['minimum'])
        ex=Experiment(INSTANCE,seeds=[worst['seed']],variants=[worst['variant']])
        job=next(j for j in ex.jobs if j[0]==worst['patient'])
        name,seed,variant,p,initial,meals=job
        trace,minute=native_trace(name,meals,individual_design(chosen['design'],INSTANCE['tdi'][name]),INSTANCE['patient_seed'])
        result=dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace,INSTANCE['warmup_minutes'],minute))
        (OUT/'native_check.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        raise SystemExit
    ex=Experiment(INSTANCE)
    records=[json.loads(line) for line in (OUT/'results.jsonl').read_text().splitlines()] if (OUT/'results.jsonl').exists() else []
    if phase=='polish':
        candidates=[design(a,ec,n) for a,ec,n in [(0.00026,90,24),(0.000265,90,24),(0.00028,110,4),(0.000285,110,4),(0.00027,100,8),(0.00028,120,8)]]
        ex=Experiment(INSTANCE,seeds=[6111005,6111021,6111137,6111251,6111409,6111613])
        records=[]
    elif phase=='robust':
        candidates=[design(a,ec,n) for a,ec,n in [(0.00026,110,4),(0.000275,110,4),(0.00029,150,4),(0.00025,90,24),(0.000285,130,4),(0.00027,130,4)]]
        ex=Experiment(INSTANCE,seeds=[6111005,6111021,6111137,6111251,6111409,6111613])
        records=[]
    elif phase=='screen':
        candidates=[design(a) for a in [0.00022,0.00026,0.00030,0.00034,0.00038,0.00042]]
    elif phase=='shape':
        candidates=[design(a,ec,n) for ec in [90,110,130,150] for a in [0.00025,0.000275,0.00030] for n in [4,24]]
    elif phase=='refine':
        candidates=[design(a,ec,24) for ec in [170,200,230,260] for a in [0.00030,0.00033,0.00036,0.00039]]
    else:
        candidates=[json.loads((OUT/'design.json').read_text())]
        ex=Experiment(INSTANCE,seeds=[6111005,6111021,6111137,6111251,6111409,6111613]+list(range(7320100,7320109)),variants=INSTANCE['variants'])
        records=[]
    for d in candidates:
        records.append(record(d,evaluate(ex,d,4 if phase=='validate' else 1),phase))
        select(records)
