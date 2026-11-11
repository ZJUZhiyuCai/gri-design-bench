"""Shared formulation search using public physiology and reproducible meal seeds.
Run stages in order: python search.py coarse; python search.py refine;
python search.py validate. Results and atomic checkpoints are saved alongside code.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json, time, sys
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, save_design
from gri_bench.physiology import fast_trace
ROOT=Path('/work/output')
INSTANCE=load_instance()
def design(a,ec,n=4,leak=None,tau=.05,load=4):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(INSTANCE['bounds']['relative_leak'][0] if leak is None else leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load))}
def evaluate(exp,d,steps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in exp.jobs:
        t=fast_trace(p,initial,meals,individual_design(d,INSTANCE['tdi'][name]),substeps=steps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(t)))
    return {**summarize(rows),'rows':rows}
def score(m):
    return m['mean_tir']-30*max(0,m['max_trajectory_tbr70']-1)-60*max(0,m['max_trajectory_tbr54'])-5*max(0,60-m['minimum_glucose'])
def record(d,m,stage):
    with (ROOT/'history.jsonl').open('a') as f:f.write(json.dumps(dict(design=d,metrics=m,stage=stage))+'\n')
    print(json.dumps(dict(p=d['parameters'],**{k:v for k,v in m.items() if k!='rows'})),flush=True)
def history():
    return [json.loads(x) for x in (ROOT/'history.jsonl').read_text().splitlines()] if (ROOT/'history.jsonl').exists() else []
if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else 'coarse'
    exp=Experiment(INSTANCE)
    if stage=='coarse':
        candidates=[design(a,ec,n) for a,ec,n in [(0.0004,150,4),(0.0006,150,4),(0.0008,150,4),(0.0006,200,4),(0.0008,200,4),(0.001,200,4),(0.0008,250,4),(0.001,250,4),(0.0008,150,12),(0.0008,180,2)]]
    elif stage=='refine':
        candidates=[design(a,ec,n) for a,ec,n in [(0.00055,100,4),(0.0006,120,4),(0.00065,150,4),(0.0007,175,4),(0.00055,120,8),(0.0006,140,8),(0.00065,160,8),(0.00055,110,12),(0.0006,130,12),(0.0006,150,2),(0.00065,175,2),(0.0005,100,8),(0.00055,140,24),(0.0006,160,24),(0.00065,180,12)]]
    elif stage=='local':
        candidates=[design(a,ec,n) for a,ec,n in [(0.00048,85,4),(0.0005,90,4),(0.00052,110,6),(0.0005,110,4),(0.00048,90,8),(0.0005,110,12),(0.00048,100,8),(0.00048,100,16),(0.0005,110,24),(0.00046,85,8)]]
    elif stage=='stress':
        exp=Experiment(INSTANCE,seeds=[7320101,7320102,7320103,7320104,7320105,7320106,7320107,7320108])
        candidates=[design(.00048,70,4),design(.000475,70,4),design(.00046,59.26305046791457,4),design(.00047,65,4)]
    elif stage=='final_search':
        exp=Experiment(INSTANCE,seeds=[6111107,6111219,6111341])
        candidates=[design(.00048,70,4),design(.0005,80,4),design(.00046,75,8),design(.00055,110,2),design(.00055,100,2),design(.00052,85,2)]
    elif stage=='fresh_search':
        exp=Experiment(INSTANCE,seeds=[6111107,6111219,6111341])
        candidates=[design(.0005,90,4),design(.00048,90,8),design(.0005,90,8),design(.0005,85,4),design(.00052,100,4)]
    elif stage=='validate':
        exp=Experiment(INSTANCE,seeds=[6111107,6111219,6111341])
        candidates=[design(.0005,100,8),design(.00048,100,8),design(.0005,110,4)]
    else:
        candidates=[]
    prev=history()
    best=max([score(x['metrics']) for x in prev],default=-1e9)
    for d in candidates:
        m=evaluate(exp,d);record(d,m,stage)
        if score(m)>best and stage not in ('validate','fresh_search','final_search','stress'):best=score(m);save_design(d)
    if stage=='finish':
        # Choose on the eight stress seeds, retaining zero observed TBR and a
        # full-horizon minimum >=71 mg/dL. Do not select on training TIR alone.
        eligible=[x for x in history() if x['stage']=='stress' and x['metrics']['minimum_glucose']>=71 and x['metrics']['max_trajectory_tbr70']==0]
        chosen=max(eligible,key=lambda x:x['metrics']['mean_tir'])['design']
        save_design(chosen)
        final_exp=Experiment(INSTANCE,seeds=[6111001,6111107,6111219,6111341,7320101,7320102,7320103,7320104,7320105,7320106,7320107,7320108])
        final=evaluate(final_exp,chosen,steps=4)
        (ROOT/'validation.json').write_text(json.dumps(final,indent=2)+'\n')
        record(chosen,final,'fine_validation')
        training=summarize([r for r in final['rows'] if r['seed']==6111001])
        fresh=summarize([r for r in final['rows'] if r['seed']!=6111001])
        text=f'''# Shared responsive formulation

The submitted coefficients are shared across adult#001, adult#002, and adult#003. Native TDI provides the only patient scaling. Parameters: {json.dumps(chosen['parameters'])}.

The search screened amplitude, EC50, and Hill exponent on the public training scenarios using one-minute RK4 steps, then compared candidates on three additional meal seeds. Four conservative candidates were compared on eight further seeds. The final selection maximizes mean TIR on those eight seeds among candidates with zero observed TBR70 and full-horizon minimum at least 71 mg/dL. This is a finite heuristic search, not a proof of optimality.

The leak is at its permitted minimum to preserve glucose-dependent dose reduction. A low EC50 and moderate Hill slope support sustained delivery while retaining some reduction near low glucose. The minimum filter time avoids added sensing delay. The reservoir load is 4 times native TDI. Even the theoretical maximum release over 4320 minutes is only {chosen['parameters']['theta_a']*(1+chosen['parameters']['relative_leak'])*4320:.6f} times TDI, so the reservoir cannot exhaust during the horizon.

Final validation uses the standard four RK4 substeps per minute on all 12 tested seeds and all three variants: 108 patient/scenario trajectories. Training summary: {json.dumps(training)}. Additional-seed summary (99 trajectories): {json.dumps(fresh)}. Metrics omit day one for TIR/TBR, but retain its minute minima. Detailed per-trajectory evidence is in validation.json.

Fresh seeds used for selection are validation evidence, not sealed heldout safety guarantees. The hidden evaluator uses native dopri5, and arbitrary unseen meals may differ. This is solely a simulation benchmark design, not a clinical recommendation.

Reproduce the search by running search.py with stages coarse, refine, local, validate, fresh_search, final_search, stress, finish, in that order. Each stage appends history.jsonl; start in a clean output directory for a fresh run. finish atomically saves the selected design. The exact grid and seed lists are embedded in the code.
'''
        (ROOT/'rationale.md').write_text(text)
        print('TRAINING',json.dumps(training),flush=True)
        print('FRESH',json.dumps(fresh),flush=True)
        worst=min(final['rows'],key=lambda r:r['metrics']['minimum'])
        (ROOT/'worst.json').write_text(json.dumps(worst)+'\n')
    if stage=='native':
        from gri_bench.native import native_trace
        chosen=json.loads((ROOT/'design.json').read_text())
        worst=json.loads((ROOT/'worst.json').read_text())
        one=Experiment(INSTANCE,seeds=[worst['seed']],variants=[worst['variant']])
        job=next(j for j in one.jobs if j[0]==worst['patient'])
        name,seed,variant,p,initial,meals=job
        trace,minute=native_trace(name,meals,individual_design(chosen,INSTANCE['tdi'][name]),INSTANCE['patient_seed'])
        result=dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace,INSTANCE['warmup_minutes'],minute))
        (ROOT/'native_check.json').write_text(json.dumps(result,indent=2)+'\n')
        with (ROOT/'rationale.md').open('a') as f:
            f.write('\nNative dopri5 check of the trajectory with the lowest RK4 full-horizon glucose: '+json.dumps(result)+'. This checks one trajectory, not the entire native ensemble. Reproduce with the native stage after finish.\n')
        print(json.dumps(result),flush=True)
