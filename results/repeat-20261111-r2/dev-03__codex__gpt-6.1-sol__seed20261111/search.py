"""Reproducible staged search. Run with OPENBLAS_NUM_THREADS=1.
Uses public physiology only; 1-minute RK4 search, default RK4 final checks.
Every candidate shares its six coefficients across the cohort.
"""
import json, time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import (load_instance,Experiment,PARAMETERS,individual_design,
                           glucose_metrics,summarize,save_design)
from gri_bench.physiology import fast_trace
ROOT=Path('/work/output')
INSTANCE=load_instance()
LEAK=INSTANCE['bounds']['relative_leak'][0]

def design_of(x):
    # Amplitude is optimized in units of 0.001 TDI/min.
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,
            [float(x[0])*0.001,LEAK,float(x[1]),float(x[2]),float(x[3]),4.0]))}

def evaluate(ex,design,substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace=fast_trace(p,initial,meals,individual_design(design,INSTANCE['tdi'][name]),substeps)
        rows.append({'patient':name,'seed':seed,'variant':variant,
                     'metrics':glucose_metrics(trace,INSTANCE['warmup_minutes'])})
    return {**summarize(rows),'rows':rows}

def loss(m, floor=65):
    return (-m['mean_tir']+12*max(0,floor-m['minimum_glucose'])
            +12*m['max_trajectory_tbr70']+25*m['max_trajectory_tbr54'])

def main():
    start=time.process_time(); rng=np.random.default_rng(20261111)
    train=Experiment(INSTANCE)
    archive=[]
    best=[float('inf')]
    def objective(x):
        d=design_of(x); m=evaluate(train,d); score=loss(m)
        archive.append({'x':list(map(float,x)),'design':d,'metrics':m,'loss':score})
        if score < best[0]:
            best[0]=score
            if m['feasible']: save_design(d)
        return score
    bounds=[(.18,.9),(65,260),(.6,24),(.05,20)]
    opt=differential_evolution(objective,bounds,seed=42,popsize=9,maxiter=12,
                               polish=False,tol=.001,workers=1)
    archive.sort(key=lambda a:a['loss'])
    (ROOT/'training_archive.json').write_text(json.dumps(archive))
    print('training',len(archive),'cpu',time.process_time()-start,'best',archive[0],flush=True)
    # Fresh seeds include ordinary days and both intervention variants.
    validation=Experiment(INSTANCE,seeds=[6111004,6111005,6111011,6111023,6111047])
    ranked=[]
    # Evaluate distinct promising response curves and nearby safer amplitudes.
    xs=[a['x'] for a in archive[:18]]
    xs += [[opt.x[0]*f,*opt.x[1:]] for f in [.88,.92,.96,1.0]]
    for x in xs:
        d=design_of(x); m=evaluate(validation,d)
        ranked.append({'x':x,'design':d,'metrics':m,'loss':loss(m,65)})
    ranked.sort(key=lambda a:a['loss'])
    (ROOT/'validation_archive.json').write_text(json.dumps(ranked))
    save_design(ranked[0]['design'])
    print('validation cpu',time.process_time()-start,'best',ranked[0],flush=True)
    # Leave the selected design and complete metrics available even if interrupted.
    (ROOT/'stage_result.json').write_text(json.dumps({'training':archive[0], 'validation':ranked[0]},indent=2))



# Final refinement is also independently reproducible with --refine.
def refine():
    start=time.process_time()
    ex=Experiment(INSTANCE,seeds=[6111004,6111011,6111023])
    prior=json.loads((ROOT/'validation_archive.json').read_text())
    records=[]
    def robust_loss(m):
        return (-m['mean_tir'] + 15*max(0,60-m['minimum_glucose'])
                +15*max(0,m['max_trajectory_tbr70']-1.0)
                +30*m['max_trajectory_tbr54'])
    def objective(x):
        d=design_of(x);m=evaluate(ex,d)
        score=robust_loss(m)
        records.append({'x':list(map(float,x)),'design':d,'metrics':m,'loss':score})
        return score
    bounds=[(.28,.55),(60,125),(3,24),(.05,10)]
    rng=np.random.default_rng(54321)
    pop=np.array([[rng.uniform(*b) for b in bounds] for _ in range(20)])
    for j,a in enumerate(prior[:8]): pop[j]=np.clip(a['x'],np.array(bounds)[:,0],np.array(bounds)[:,1])
    differential_evolution(objective,bounds,init=pop,seed=123,maxiter=5,polish=False,tol=.001)
    records.sort(key=lambda r:r['loss'])
    # Include the zero-TBR design in the final independent comparison.
    records.append(prior[0])
    (ROOT/'refinement_archive.json').write_text(json.dumps(records))
    save_design(records[0]['design'])
    print('refinement cpu',time.process_time()-start,flush=True)
    for r in records[:6]: print(r['x'],{k:v for k,v in r['metrics'].items() if k!='rows'},flush=True)


def finalize():
    seeds=np.random.default_rng(20260303).integers(1,2**30,size=20).tolist()
    ex=Experiment(INSTANCE,seeds=seeds)
    refined=json.loads((ROOT/'refinement_archive.json').read_text())
    prior=json.loads((ROOT/'validation_archive.json').read_text())
    candidates=[refined[0],refined[1],prior[0]]
    results=[]
    for candidate in candidates:
        d=candidate['design']; m=evaluate(ex,d,substeps=4)
        results.append({'design':d,'metrics':m})
        print(d,{k:v for k,v in m.items() if k!='rows'},flush=True)
    eligible=[r for r in results if r['metrics']['feasible'] and
              r['metrics']['minimum_glucose']>=60 and
              r['metrics']['max_trajectory_tbr70']<=1]
    chosen=max(eligible or results,key=lambda r:r['metrics']['safe_tir'])
    save_design(chosen['design'])
    # Archive the entire fresh scenario comparison and seeds for audit.
    (ROOT/'final_validation.json').write_text(json.dumps({'seeds':seeds,'results':results,'selected':chosen},indent=2))
    training=evaluate(Experiment(INSTANCE),chosen['design'],substeps=4)
    (ROOT/'final_training.json').write_text(json.dumps(training,indent=2))
    m=chosen['metrics']; p=chosen['design']['parameters']
    text=f'''# Shared responsive GRI formulation

The submitted design uses the minimum permitted relative leak, a smooth Hill response, and the maximum permitted reservoir. The exact shared parameters are in design.json. The amplitude is scaled only by each child's supplied native TDI; no patient-specific fitted coefficient or meal bolus is used.

The final amplitude is {p['theta_a']:.12g} TDI/min, relative leak {p['relative_leak']:.12g}, EC50 {p['ec50_mg_dl']:.8g} mg/dL, Hill exponent {p['hill_n']:.8g}, filter time constant {p['tau_min']:.8g} minutes, and load 4 TDI. The minimum leak provides the greatest allowed response contrast. The response remains high during hyperglycemia and falls as glucose decreases. Search jointly adjusted threshold, slope, amplitude, and filtering to balance meal coverage against delayed insulin action. A large reservoir avoids depletion during this three-day experiment. Even the theoretical maximum three-day release is only {p['theta_a']*(p['relative_leak']+1)*4320:.5f} TDI, below the 4 TDI load.

## Search and reproducibility

Run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`, then the same script with `--refine`, then with `--finalize`. Fixed seeds, population sizes, iterations, and candidate selection rules are embedded in the code. The initial differential evolution explored 468 candidates on the public training scenarios. Twenty-two candidates were checked on five additional meal seeds. A 120-candidate refinement used three of those additional seeds. The final three candidates were compared on 20 further, reproducibly sampled meal seeds, each with all three variants and all three patients (180 trajectories per candidate). These final scenarios were independent of the optimization scenarios, but their results were used for the final candidate selection.

Search used the public RK4 physiology with one-minute steps. Final comparisons used its default four substeps per minute. Each evaluation starts from the native initial state. Time-in-range and time-below-range exclude day one, while the minimum includes the full horizon. Objectives penalized low minima and excess trajectory TBR; final eligibility additionally required minimum >=60 mg/dL and TBR70 <=1%, stricter than benchmark limits.

## Observed validation results

For the selected formulation over the 180 final comparison trajectories:

- Mean post-warmup TIR70–180: {m['mean_tir']:.4f}%.
- Worst trajectory TBR70: {m['max_trajectory_tbr70']:.4f}%.
- Worst trajectory TBR54: {m['max_trajectory_tbr54']:.4f}%.
- Full-horizon minimum glucose: {m['minimum_glucose']:.4f} mg/dL.

On the original nine training trajectories, the selected formulation produced mean TIR {training['mean_tir']:.4f}%, maximum TBR70 {training['max_trajectory_tbr70']:.4f}%, maximum TBR54 {training['max_trajectory_tbr54']:.4f}%, and minimum glucose {training['minimum_glucose']:.4f} mg/dL.

All reported results use the public fast integrator, not the trusted native dopri5 verifier. Numerical agreement and safety on new held-out meals are not guaranteed. The strict observed safety margin supports this choice but does not prove held-out safety or global optimality. Full scenario rows and exact comparison seeds are archived in final_validation.json. This formulation is solely for the stated simulation benchmark, not clinical use.
'''
    (ROOT/'rationale.md').write_text(text)

if __name__=='__main__':
    import sys
    if '--refine' in sys.argv: refine()
    elif '--finalize' in sys.argv: finalize()
    else: main()
