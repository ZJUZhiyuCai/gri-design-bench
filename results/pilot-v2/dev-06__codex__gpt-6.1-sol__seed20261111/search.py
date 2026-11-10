"""Deterministic shared-cohort search. Run stages with --stage (initial/refine/validate).
Uses public physiology only. Atomic checkpoints preserve the best feasible result.
"""
import argparse, json, os, time
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, validate_design, save_design
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')

def design(a,ec=160.,leak=0.5124966150526034,n=4.,tau=2.,load=4.):
    return dict(mode='responsive',parameters=dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load)))

def evaluate(ex,d,substeps=1):
    validate_design(d,ex.instance)
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        tr=fast_trace(p,initial,meals,individual_design(d,ex.instance['tdi'][name]),substeps=substeps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(tr)))
    return dict(**summarize(rows),rows=rows)

def record(d,m,label):
    r=dict(design=d,metrics=m,label=label)
    with (OUT/'results.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    print(json.dumps(dict(label=label,design=d,**{k:v for k,v in m.items() if k!='rows'})),flush=True)
    return r

def choose(ex, candidates, label, tbr_limit=2., minimum=50., substeps=1):
    best=None
    for i,d in enumerate(candidates):
        m=evaluate(ex,d,substeps);r=record(d,m,label+str(i))
        if m['max_trajectory_tbr70']<=tbr_limit and m['max_trajectory_tbr54']==0 and m['minimum_glucose']>=minimum:
            if best is None or m['mean_tir']>best['metrics']['mean_tir']:
                best=r;save_design(d)
    return best


def main():
    # All coefficients are shared. Native TDI is used only by individual_design.
    # Candidate grids and validation seeds are deterministic and public.
    inst=load_instance();train=Experiment(inst)
    choose(train,[design(a) for a in [.0005,.0007,.0009,.0011,.0013]],'initial')
    choose(train,[design(a,ec) for ec in [90,120,180,240,320] for a in [.0002,.0003,.0004,.0005]],'grid')
    local=[design(a,ec) for ec,aa in [(100,[.00026,.00028]),(120,[.00031,.00033,.00035]),(140,[.00034,.00036,.00038]),(160,[.00037,.00039,.00041]),(180,[.00040,.00042,.00044]),(200,[.00043,.00045])] for a in aa]
    shortlist=[]
    for i,d in enumerate(local):
        m=evaluate(train,d);r=record(d,m,'local'+str(i))
        if m['max_trajectory_tbr70']<=2 and m['minimum_glucose']>=60:shortlist.append(r)
    shortlist.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    fresh=Experiment(inst,seeds=list(range(6111007,6111011)),variants=inst['variants'])
    choose(fresh,[r['design'] for r in shortlist[:6]],'fresh')
    robust=Experiment(inst,seeds=list(range(6111007,6111023)),variants=inst['variants'])
    choose(robust,[design(.00030,120),design(.00032,135),design(.00033,140),design(.00034,150),design(.00036,160),design(.000325,130),design(.00033,140,tau=20),design(.00037,140,n=3)],'robust',2.5,55)
    prospective=Experiment(inst,seeds=list(range(6111023,6111055)),variants=inst['variants'])
    best=choose(prospective,[design(.00033,140),design(.00032,130),design(.000315,125)],'prospective',3,60)
    if best is None:raise RuntimeError('No candidate has the required safety margin')
    d=best['design'];save_design(d)
    # Repeat all 49 known seeds at the API default RK4 resolution.
    ex=Experiment(inst,seeds=list(range(6111006,6111055)),variants=inst['variants'])
    m=evaluate(ex,d,4);record(d,m,'final_RK4_quarter_minute')
    (OUT/'validation.json').write_text(json.dumps(m,indent=2))
    if not m['feasible']:raise RuntimeError('Quarter-minute validation failed')
    # Native dopri5 check on the most limiting measured trajectory.
    from gri_bench.native import native_trace
    worst=max(m['rows'],key=lambda r:(r['metrics']['tbr70'],-r['metrics']['minimum']))
    job=next(j for j in ex.jobs if j[:3]==(worst['patient'],worst['seed'],worst['variant']))
    name,seed,variant,p,initial,meals=job
    tr,minute=native_trace(name,meals,individual_design(d,inst['tdi'][name]),inst['patient_seed'])
    comparison=dict(patient=name,seed=seed,variant=variant,rk4=worst['metrics'],native=glucose_metrics(tr,inst['warmup_minutes'],minute))
    (OUT/'native_check.json').write_text(json.dumps(comparison,indent=2))
    stress=Experiment(inst,seeds=list(range(6111055,6111135)),variants=inst['variants'])
    sm=evaluate(stress,d);record(d,sm,'final_stress_80_seeds')
    (OUT/'stress_validation.json').write_text(json.dumps(sm,indent=2))
    if not sm['feasible']:
        d=design(.00033,140);fm=evaluate(stress,d);record(d,fm,'fallback_stress')
        if not fm['feasible']:raise RuntimeError('Fallback failed')
        save_design(d)
    else:save_design(d)
    validate_design(d,inst)
    print('FINAL',json.dumps(d),flush=True)

if __name__=='__main__':main()
