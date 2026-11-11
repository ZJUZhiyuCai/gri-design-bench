"""Deterministic shared-formulation search and fresh-meal validation.
Run with OPENBLAS_NUM_THREADS=1 python /work/output/search.py.
Only public cohort physiology and public meal generation are used.
"""
import json, time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution, minimize
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design
OUT = Path('/work/output')
LEAK = .5124966150526034

def design(x):
    # Four shared shape variables; fastest permitted sensing and ample reservoir.
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,
        [float(x[0]),float(x[1]),float(x[2]),float(x[3]),.05,4.]))}

def compact(m):
    return {k:v for k,v in m.items() if k!='rows'}

def loss(m, margin=0):
    # Penalize approaching the safety boundary, as well as violating it.
    return (-m['mean_tir'] + 6*max(0,m['max_trajectory_tbr70']-margin)
            + 30*m['max_trajectory_tbr54']
            + 3*max(0,60-m['minimum_glucose']))

def main():
    start=time.process_time(); ins=load_instance(); train=Experiment(ins)
    history=[]
    def objective(x):
        d=design(x); m=train.evaluate(d); value=loss(m)
        history.append((value,x.copy(),compact(m)))
        return value
    bounds=[(.00032,.00085),(LEAK,1.2),(95,210),(1.3,16)]
    result=differential_evolution(objective,bounds,seed=2052,popsize=5,
        maxiter=7,polish=False,tol=0,workers=1)
    history.sort(key=lambda v:v[0])
    # Fresh seeds are separate from the instance's one training seed.
    robust=Experiment(ins,seeds=[6111002,824711,391204])
    robust_history=[]
    def robust_objective(x):
        if any(x[i]<bounds[i][0] or x[i]>bounds[i][1] for i in range(4)):
            return 1e4
        d=design(x); m=robust.evaluate(d); value=loss(m,0)
        robust_history.append((value,x.copy(),compact(m)))
        return value
    for _,x,_ in history[:8]:
        robust_objective(x)
    robust_history.sort(key=lambda v:v[0])
    x0=robust_history[0][1]
    # Nelder-Mead in scaled coordinates allows useful steps in all dimensions.
    scale=np.array([.0001,.3,30.,3.])
    minimize(lambda z:robust_objective(z*scale),x0/scale,method='Nelder-Mead',
        options={'maxfev':45,'xatol':.005,'fatol':.01})
    robust_history.sort(key=lambda v:v[0])
    validation=Experiment(ins,seeds=[104729,130363,155921,196613,262147,327673],
                          variants=ins['variants'])
    finalists=[]
    for _,x,_ in robust_history:
        if len(finalists)>=5: break
        if any(np.linalg.norm((x-v['x'])/scale)<.10 for v in finalists): continue
        d=design(x); vm=validation.evaluate(d); rm=robust.evaluate(d)
        # Zero TBR and minimum >=60 create margins for unseen meals/solver differences.
        score=min(loss(vm),0)*-1
        eligible=(vm['max_trajectory_tbr70']<=.25 and vm['max_trajectory_tbr54']==0
                  and vm['minimum_glucose']>=60 and rm['max_trajectory_tbr70']<=.25
                  and rm['minimum_glucose']>=60)
        finalists.append({'x':x,'design':d,'validation':vm,'robust':rm,
                          'eligible':eligible,'score':score})
    valid=[v for v in finalists if v['eligible']]
    if not valid:
        valid=sorted(finalists,key=lambda v:loss(v['validation']))[:1]
    best=max(valid,key=lambda v:v['validation']['mean_tir'])
    save_design(best['design'])
    record={'training_evaluations':len(history),'robust_evaluations':len(robust_history),
        'selected':{k:v for k,v in best.items() if k!='x'},
        'finalists':[{k:v for k,v in f.items() if k!='x'} for f in finalists],
        'cpu_seconds':time.process_time()-start}
    (OUT/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'design':best['design'],'validation':compact(best['validation']),
        'robust':compact(best['robust']),'cpu':record['cpu_seconds']},indent=2),flush=True)

if __name__=='__main__': main()


def stress_validation():
    """Larger independent scenario set; reduce amplitude if safety margin is thin."""
    ins=load_instance()
    with open(OUT/'design.json') as f: d=json.load(f)
    seeds=[7000001+7919*i for i in range(30)]
    ex=Experiment(ins,seeds=seeds)
    m=ex.evaluate(d)
    original=compact(m)
    if (m['max_trajectory_tbr70']>1 or m['max_trajectory_tbr54']>0
            or m['minimum_glucose']<57):
        d['parameters']['theta_a']*=.97
        m=ex.evaluate(d)
        save_design(d)
    (OUT/'stress.json').write_text(json.dumps({'seeds':seeds,'original':original,
        'design':d,'metrics':m},indent=2)+'\n')
    record=json.loads((OUT/'results.json').read_text())
    selected=record['selected']
    text=f'''# Shared glucose-responsive formulation

The submitted formulation uses one common set of six coefficients for all three known adolescents. Amplitude and reservoir scale only with the supplied native TDI. No individual fitting, external insulin, or meal boluses are used.

Final parameters: `{json.dumps(d['parameters'],sort_keys=True)}`.

The response combines basal leakage with glucose-dependent release. Fast sensing avoids adding filter lag to the existing interstitial and insulin-action delays. The Hill curve supplies additional insulin at high glucose while reducing release as glucose falls. The reservoir is set to the permitted maximum to avoid deliberately relying on early exhaustion.

## Search and validation

`search.py` performs deterministic differential evolution over amplitude, leakage, EC50 and Hill exponent, followed by local refinement on three public meal seeds. Sensing time and reservoir size are fixed at their permitted lower and upper limits, respectively. The objective penalizes any observed time below 70, all time below 54, and minimum glucose below 60. Candidates are screened on six further seeds, each with ordinary meals, missed lunch and larger dinner. The resulting design receives an additional 30-seed stress check (270 patient/scenario trajectories), with an explicit 3% amplitude reduction rule if hypoglycemia margins are thin. Atomic replacement writes the final design.

Before the stress check, the six-seed validation mean TIR was {selected['validation']['mean_tir']:.4f}%, maximum TBR70 {selected['validation']['max_trajectory_tbr70']:.4f}%, maximum TBR54 {selected['validation']['max_trajectory_tbr54']:.4f}%, and full-horizon minimum {selected['validation']['minimum_glucose']:.4f} mg/dL. Those figures describe the candidate before any stress-driven adjustment.

For the **final submitted formulation**, the additional 30-seed check gave mean TIR **{m['mean_tir']:.4f}%**, maximum trajectory TBR70 **{m['max_trajectory_tbr70']:.4f}%**, maximum trajectory TBR54 **{m['max_trajectory_tbr54']:.4f}%**, and full-horizon minimum **{m['minimum_glucose']:.4f} mg/dL**. Each seed covers all three patients and all three variants. TIR and TBR omit the first day; minimum glucose includes it.

These are public fast-RK4 simulation results, not native-dopri5 results or guarantees for unseen scenarios. No native integration was run within this compute budget. All observed outcomes are saved in `results.json` and `stress.json`; finite meal validation cannot establish universal safety. This is a simulation benchmark design, not a clinical recommendation.

Reproduce with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py` in the benchmark environment. It uses only public physiology and meal schedules, with fixed random seeds. The final design file alone controls the independent evaluation.
'''
    tmp=OUT/'rationale.tmp'; tmp.write_text(text); tmp.replace(OUT/'rationale.md')
    print(json.dumps({'stress':compact(m),'final_design':d},indent=2),flush=True)

if __name__=='__main__': stress_validation()
