"""Deterministic static formulation search and independent scenario validation.
Uses the unmodified public RK4 simulator. Run with OPENBLAS_NUM_THREADS=1.
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

ROOT = '/work/output/'

def design(a, ec, n=24., leak=0.5124966150526034, tau=0.05):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=4.)}

def score(m):
    # Penalize low minima even within nominal feasibility, for new-scenario margin.
    return m['mean_tir'] - 2.*max(0.,75.-m['minimum_glucose']) - 12.*m['max_trajectory_tbr70'] - 30.*m['max_trajectory_tbr54']

def main():
    e = Experiment(load_instance())
    records=[]
    best=-1e9
    for a in [0.0004,0.0005,0.0006,0.0007,0.0008,0.001]:
        for ec in [110.,140.,170.,200.]:
            d=design(a,ec)
            m=e.evaluate(d)
            s=score(m)
            records.append({'design':d,'metrics':m,'score':s})
            print(a,ec,round(m['mean_tir'],2),round(m['minimum_glucose'],2),round(m['max_trajectory_tbr70'],2),round(s,2),flush=True)
            if s>best:
                best=s
                save_design(d)
    with open(ROOT+'search_records.json','w') as f: json.dump(records,f)


# Refinement stage; invoked explicitly for a reproducible continuation.
def refine():
    from scipy.optimize import differential_evolution
    e=Experiment(load_instance())
    records=json.load(open(ROOT+'search_records.json'))
    best=max(r['score'] for r in records)
    def objective(x):
        nonlocal best
        d=design(x[0],x[1],x[2],x[3])
        m=e.evaluate(d); s=score(m)
        records.append({'design':d,'metrics':m,'score':s})
        if s>best:
            best=s;save_design(d)
            print('best',json.dumps(d), 'metrics', {k:v for k,v in m.items() if k!='rows'},'score',s,flush=True)
        return -s
    differential_evolution(objective,[(0.00036,0.00062),(65.,155.),(2.,24.),(0.5124966150526034,0.85)],popsize=5,maxiter=4,seed=1938,polish=False,workers=1)
    with open(ROOT+'search_records.json','w') as f:json.dump(records,f)

def validate():
    seeds=[730001,730019,730043,730079,730111,730153]
    e=Experiment(load_instance(),seeds=seeds)
    records=json.load(open(ROOT+'search_records.json'))
    candidates=sorted(records,key=lambda r:r['score'],reverse=True)[:8]
    out=[]
    best=-1e9
    for r in candidates:
        d=r['design'];m=e.evaluate(d)
        s=score(m)
        out.append({'design':d,'metrics':m,'score':s})
        print(json.dumps({'design':d,'summary':{k:v for k,v in m.items() if k!='rows'},'score':s}),flush=True)
        if s>best:
            best=s;save_design(d)
    with open(ROOT+'validation_records.json','w') as f:json.dump(out,f)

def safety_refine():
    e=Experiment(load_instance(),seeds=[730001,730019,730043,730079,730111,730153])
    out=[]
    def robust_score(m):
        if not m['feasible']: return -10000.
        # Reserve 2 percentage points of TBR70 and 0.75 of TBR54.
        return m['mean_tir']-10.*max(0.,m['max_trajectory_tbr70']-2.)-30.*max(0.,m['max_trajectory_tbr54']-.25)-max(0.,60.-m['minimum_glucose'])
    best=-1e9
    for a in [.00043,.00045,.00047,.00049]:
        for ec in [65.,80.,95.]:
            d=design(a,ec,n=24.,leak=.6092591382374652)
            m=e.evaluate(d);s=robust_score(m)
            out.append({'design':d,'metrics':m,'score':s})
            print(a,ec,{k:round(v,3) if isinstance(v,float) else v for k,v in m.items() if k!='rows'},'score',s,flush=True)
            if s>best:
                best=s;save_design(d)
    with open(ROOT+'safety_refine_records.json','w') as f:json.dump(out,f)

def final_refine():
    e=Experiment(load_instance(),seeds=[730001,730019,730043,730079,730111,730153])
    records=[]
    for a,ec,leak in [(0.00044,80.,.6092591382374652),(.00046,95.,.6092591382374652),(.00050,110.,.5124966150526034),(.000465,100.,.5124966150526034)]:
        d=design(a,ec,24.,leak)
        m=e.evaluate(d)
        s=m['mean_tir'] if m['minimum_glucose']>=70.5 and m['max_trajectory_tbr70']<=.5 and m['max_trajectory_tbr54']==0 else -1e6
        records.append({'design':d,'metrics':m,'score':s})
        print(json.dumps({'design':d,'summary':{k:v for k,v in m.items() if k!='rows'},'score':s}),flush=True)
    chosen=max(records,key=lambda r:r['score'])
    save_design(chosen['design'])
    with open(ROOT+'final_refine_records.json','w') as f:json.dump(records,f)


def audit():
    from gri_bench.api import individual_design, glucose_metrics
    from gri_bench.native import native_trace
    instance=load_instance()
    d=json.load(open(ROOT+'design.json'))
    e=Experiment(instance,seeds=[910003,910019,910033,910051,910073,910091,910111,910139,910163,910199,910223,910249])
    m=e.evaluate(d)
    train=Experiment(instance).evaluate(d)
    result={'training':train,'additional_fresh_scenarios':m}
    with open(ROOT+'final_metrics.json','w') as f:json.dump(result,f,indent=2)
    print('TRAINING', {k:v for k,v in train.items() if k!='rows'},flush=True)
    print('FRESH', {k:v for k,v in m.items() if k!='rows'},flush=True)
    worst=min(m['rows'],key=lambda r:r['metrics']['minimum'])
    job=next(j for j in e.jobs if j[0]==worst['patient'] and j[1]==worst['seed'] and j[2]==worst['variant'])
    name,seed,variant,p,initial,meals=job
    trace,minute=native_trace(name,meals,individual_design(d,instance['tdi'][name]),instance['patient_seed'])
    result['native_spot_check']={'patient':name,'seed':seed,'variant':variant,'metrics':glucose_metrics(trace,instance['warmup_minutes'],minute)}
    with open(ROOT+'final_metrics.json','w') as f:json.dump(result,f,indent=2)
    print('NATIVE',result['native_spot_check'],flush=True)

if __name__=='__main__':
    main()
    refine()
    validate()
    safety_refine()
    final_refine()
    audit()
