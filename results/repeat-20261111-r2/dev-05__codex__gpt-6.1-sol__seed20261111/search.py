"""Deterministic cohort-wide search and independent meal-seed validation.
Run with PYTHONPATH=/opt python /work/output/search.py.
All designs use a shared set of coefficients; no patient-specific fitting.
"""
import json, time, os
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design
from gri_bench.physiology import meal_schedule, patient_parameters

OUT='/work/output'
def design(a, ec=150., n=24., tau=.05, leak=1.5, load=4.):
    return {'mode':'responsive','parameters':dict(theta_a=float(a), relative_leak=float(leak), ec50_mg_dl=float(ec), hill_n=float(n), tau_min=float(tau), theta_L=float(load))}

def brief(m):
    return {k:v for k,v in m.items() if k!='rows'}

def atomic_json(name, data):
    path=OUT+'/'+name
    with open(path+'.tmp','w') as f: json.dump(data,f,indent=2)
    os.replace(path+'.tmp',path)

def grid_stage():
    start=time.process_time()
    ins=load_instance(); ex=Experiment(ins)
    records=[]
    for ec in [80.,110.,140.,170.,200.,240.]:
        for n in [2.,6.,12.,24.]:
            for a in [.00026,.00029,.00032,.00035,.00038,.00041]:
                d=design(a,ec,n); m=ex.evaluate(d)
                records.append({'design':d,'metrics':m})
    atomic_json('grid.json',records)
    safe=[r for r in records if r['metrics']['max_trajectory_tbr70']<=2. and r['metrics']['max_trajectory_tbr54']==0 and r['metrics']['minimum_glucose']>=55.]
    safe.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    for r in safe[:18]: print(r['design']['parameters'],brief(r['metrics']),flush=True)
    if safe: save_design(safe[0]['design'])
    print('CPU',time.process_time()-start,flush=True)



def validation_stage():
    ins=load_instance()
    seeds=[6112001,6112002,6112003,6112004,6112005,6112006]
    ex=Experiment(ins,seeds=seeds)
    grid=json.load(open(OUT+'/grid.json'))
    safe=[r for r in grid if r['metrics']['feasible']]
    safe.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    candidates=[r['design'] for r in safe[:12]]
    # Additional smooth and low-threshold shapes between grid points.
    candidates += [design(a,ec,n) for a,ec,n in [(0.00027,100,6),(.00028,120,4),(.00031,150,2),(.00033,200,2),(.00028,90,2),(.00026,90,12),(.00027,100,24),(.00030,130,2)]]
    results=[]
    for d in candidates:
        m=ex.evaluate(d); results.append({'design':d,'metrics':m})
        print(d['parameters'],brief(m),flush=True)
    atomic_json('validation1.json',results)
    safe=[r for r in results if r['metrics']['max_trajectory_tbr70']<=2.5 and r['metrics']['max_trajectory_tbr54']==0 and r['metrics']['minimum_glucose']>=55]
    if safe:
        best=max(safe,key=lambda r:r['metrics']['mean_tir']); save_design(best['design'])
        print('SAVED',best['design'],brief(best['metrics']))

def efficient_experiment(ins,seeds):
    # Generate each native stochastic meal schedule once; challenges copy it.
    ex=Experiment.__new__(Experiment); ex.instance=ins; ex.evaluations=0; ex.jobs=[]
    schedules={}
    for seed in seeds:
        base=meal_schedule(seed,ins['days'],'ordinary')
        for variant in ins['variants']:
            meals=base.copy()
            if variant=='missed_lunch': meals[2040:2280]=0.
            if variant=='large_dinner': meals[2400:2641]*=1.5
            schedules[seed,variant]=meals
    for name in ins['patients']:
        p,initial=patient_parameters(name)
        for (seed,variant),base in schedules.items():
            ex.jobs.append((name,seed,variant,p,initial,base*p.BW/ins['reference_weight_kg']))
    return ex

def refine_stage():
    ins=load_instance(); start=time.process_time()
    ex=efficient_experiment(ins,[6111005,6112002,6112005])
    print('setup CPU',time.process_time()-start,flush=True)
    candidates=[]
    for ec,n in [(65,4),(65,6),(75,4),(75,6),(80,6),(85,6),(90,8),(100,12)]:
        for a in [.000257,.000263,.000269]: candidates.append(design(a,ec,n))
    results=[]
    for d in candidates:
        m=ex.evaluate(d); results.append({'design':d,'metrics':m})
    atomic_json('refine.json',results)
    safe=[r for r in results if r['metrics']['max_trajectory_tbr70']<=1. and r['metrics']['max_trajectory_tbr54']==0 and r['metrics']['minimum_glucose']>=68.5]
    safe.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    for r in safe[:8]: print(r['design'],brief(r['metrics']),flush=True)
    print('CPU',time.process_time()-start,flush=True)

def final_validation_stage():
    ins=load_instance(); start=time.process_time()
    seeds=list(range(7213001,7213041))
    ex=efficient_experiment(ins,seeds)
    print('prepared',len(ex.jobs),'CPU',time.process_time()-start,flush=True)
    candidates=[design(.000260,80,6),design(.000257,65,4),design(.000263,75,4)]
    results=[]
    for d in candidates:
        m=ex.evaluate(d); results.append({'design':d,'metrics':m})
        print(d,brief(m),'CPU',time.process_time()-start,flush=True)
    atomic_json('validation40.json',results)
    safe=[r for r in results if r['metrics']['max_trajectory_tbr70']<=1 and r['metrics']['max_trajectory_tbr54']==0 and r['metrics']['minimum_glucose']>=65]
    if safe:
        best=max(safe,key=lambda r:r['metrics']['mean_tir']); save_design(best['design'])
        worst=min(best['metrics']['rows'],key=lambda r:r['metrics']['minimum'])
        atomic_json('worst.json',worst)
        print('SAVED',best['design'],'WORST',worst,flush=True)

def native_check():
    from gri_bench.native import native_trace
    from gri_bench.api import individual_design, glucose_metrics
    from gri_bench.physiology import meal_schedule
    ins=load_instance()
    d=json.load(open(OUT+'/design.json'))
    worst=json.load(open(OUT+'/worst.json'))
    p,_=patient_parameters(worst['patient'])
    meals=meal_schedule(worst['seed'],3,worst['variant'])*p.BW/ins['reference_weight_kg']
    trace,minute=native_trace(worst['patient'],meals,individual_design(d,ins['tdi'][worst['patient']]),ins['patient_seed'])
    metrics=glucose_metrics(trace,ins['warmup_minutes'],minute)
    atomic_json('native_check.json',{'patient':worst['patient'],'seed':worst['seed'],'variant':worst['variant'],'metrics':metrics})
    print('Native cross-check',metrics,flush=True)
    with open(OUT+'/rationale.md','a') as out:
        out.write('\nNative dopri5 cross-check of the lowest-minimum final validation trajectory: '+json.dumps(metrics)+'. This is one trajectory, not an exhaustive native validation.\n')

if __name__=='__main__':
    import sys
    if '--native-check' in sys.argv:
        native_check()
    else:
        grid_stage()
        validation_stage()
        refine_stage()
        final_validation_stage()
