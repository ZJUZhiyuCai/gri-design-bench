"""Deterministic static-formulation search. All parameters shared by cohort.
Fast screen uses 1-minute RK4, final checks use API default quarter-minute RK4.
"""
import json, os, time, argparse
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, validate_design
from gri_bench.physiology import fast_trace
OUT='/work/output'
def atomic_save(obj, filename='design.json'):
    path=f'{OUT}/{filename}'
    with open(path+'.tmp','w') as f: json.dump(obj,f,indent=2)
    os.replace(path+'.tmp',path)
def design(a,ec=180,n=4,tau=2,leak=0.5124966150526034,load=4):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load))}
def evaluate(ex,d,substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,ex.instance['tdi'][name]),substeps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace,ex.instance['warmup_minutes'])))
    return dict(**summarize(rows),rows=rows)
def compact(m): return {k:v for k,v in m.items() if k!='rows'}
def run():
    inst=load_instance()
    training=Experiment(inst)
    # Broad training screen: material shape at strongest allowed response,
    # minimum leak and minimum filter lag. Reservoir remains finite.
    grid=[]
    for ec in [85,100,115,130,145,160,180,210,250]:
        for a in np.arange(.00025,.000551,.000025):
            d=design(a,ec); m=evaluate(training,d)
            grid.append(dict(design=d,metrics=m))
    atomic_save(grid,'grid.json')
    feasible=[r for r in grid if r['metrics']['feasible']]
    atomic_save(max(feasible,key=lambda r:r['metrics']['mean_tir'])['design'])

    fresh_seeds=[104729,130363,155921,196613,228017,262147,314159,350377,399989,444443,499979]
    fresh=Experiment(inst,seeds=fresh_seeds)
    # Compare the dose/EC50 frontier on the entire known cohort.
    comparisons=[]
    frontier=[(115,.0003),(130,.000325),(145,.00035),(160,.000375),
              (180,.0004),(200,.000425),(145,.0003425),(160,.0003675)]
    for ec,a in frontier:
        d=design(a,ec); m=evaluate(fresh,d)
        comparisons.append(dict(design=d,metrics=m))
    atomic_save(comparisons,'full_fresh.json')
    eligible=[r for r in comparisons if r['metrics']['feasible']]
    winner=max(eligible,key=lambda r:r['metrics']['mean_tir'])
    atomic_save(winner['design'])

    # Extra scenarios to expose rare post-dinner excursions in limiting child.
    stress_seeds=[int(x) for x in np.random.default_rng(20260217).integers(1,2000000000,size=60)]
    stress=Experiment(inst,seeds=stress_seeds)
    limited=Experiment.__new__(Experiment)
    limited.instance=inst
    limited.jobs=[j for j in stress.jobs if j[0]=='child#005']
    stress_frontier=[(130,.00032),(140,.000335),(145,.0003425),
                     (145,.00035),(150,.00035),(160,.0003675)]
    stress_results=[]
    for ec,a in stress_frontier:
        d=design(a,ec); m=evaluate(limited,d)
        stress_results.append(dict(design=d,metrics=m))
    atomic_save(stress_results,'stress.json')

    # Refine the EC50 chosen by full-cohort comparison. Require safety
    # margins tighter than the benchmark gates on these selection scenarios.
    ec=winner['design']['parameters']['ec50_mg_dl']
    refinement=[]
    for a in [.0003425,.000345,.0003475,.00035]:
        d=design(a,ec); m=evaluate(limited,d)
        refinement.append(dict(design=d,metrics=m))
    atomic_save(refinement,'final_refinement.json')
    qualified=[r for r in refinement
               if r['metrics']['max_trajectory_tbr70']<=3
               and r['metrics']['max_trajectory_tbr54']==0
               and r['metrics']['minimum_glucose']>=68]
    if not qualified:
        raise RuntimeError('No candidate meets the additional sampled safety margins')
    selected=max(qualified,key=lambda r:r['design']['parameters']['theta_a'])['design']
    validate_design(selected,inst)
    atomic_save(selected)

    # Final fine integration, including every cohort patient and challenge.
    validation=evaluate(stress,selected,4)
    atomic_save(validation,'final_validation.json')
    atomic_save(evaluate(training,selected,4),'final_training.json')
    print('Fine stress validation:',compact(validation),flush=True)
    worst=max(validation['rows'],key=lambda r:r['metrics']['tbr70'])
    job=next(j for j in stress.jobs if j[:3]==(worst['patient'],worst['seed'],worst['variant']))
    name,seed,variant,p,initial,meals=job
    from gri_bench.native import native_trace
    tr,minutes=native_trace(name,meals,individual_design(selected,inst['tdi'][name]),inst['patient_seed'])
    native=dict(patient=name,seed=seed,variant=variant,
                metrics=glucose_metrics(tr,inst['warmup_minutes'],minutes))
    atomic_save(native,'native_check.json')

    # Fixed-design independent check. These seeds do not enter selection.
    independent_seeds=[int(x) for x in np.random.default_rng(20260829).integers(1,2000000000,size=100)]
    independent=Experiment(inst,seeds=independent_seeds)
    independent_metrics=evaluate(independent,selected,1)
    atomic_save(independent_metrics,'independent_validation.json')
    print('Independent validation:',compact(independent_metrics),flush=True)
    worst=max(independent_metrics['rows'],key=lambda r:r['metrics']['tbr70'])
    job=next(j for j in independent.jobs if j[:3]==(worst['patient'],worst['seed'],worst['variant']))
    name,seed,variant,p,initial,meals=job
    trace=fast_trace(p,initial,meals,individual_design(selected,inst['tdi'][name]),4)
    atomic_save(dict(patient=name,seed=seed,variant=variant,
                     metrics=glucose_metrics(trace,inst['warmup_minutes'])),
                'independent_worst_fine.json')
    assert validation['feasible'] and independent_metrics['feasible']
    atomic_save(selected)
    return selected

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
