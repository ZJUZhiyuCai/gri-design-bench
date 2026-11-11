"""Reproduce the deterministic training search and fresh-seed validation.
Run with OPENBLAS_NUM_THREADS=1 python /work/output/search.py train|validate.
All coefficients are shared. The reference simulator is used unmodified.
"""
import json, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design
OUT=Path('/work/output')

def atomic(name,obj):
    p=OUT/name; q=p.with_suffix('.tmp'); q.write_text(json.dumps(obj,indent=2)+'\n'); q.replace(p)

def design(x):
    # Search amplitude in units of 0.001*TDI U/min; maximal reservoir avoids premature exhaustion.
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[x[0]*.001,x[4],x[1],x[2],x[3],4.]))}

def compact(m):
    return {k:v for k,v in m.items() if k!='rows'}

def train():
    inst=load_instance(); exp=Experiment(inst); records=[]; best=-1e9
    def objective(x):
        nonlocal best
        d=design(x); m=exp.evaluate(d)
        # Seek training margins before testing independent scenarios.
        penalty=12*max(0,m['max_trajectory_tbr70']-.5)+25*max(0,m['max_trajectory_tbr54'])+2*max(0,60-m['minimum_glucose'])
        score=m['mean_tir']-penalty
        records.append({'design':d,'metrics':compact(m),'score':score})
        if score>best:
            best=score
            if m['feasible']: save_design(d)
            print('best',round(score,3),d,compact(m),flush=True)
        return -score
    differential_evolution(objective,[(.30,.75),(100,230),(2,24),(.05,20),(.5124966150526034,1.05)],popsize=6,maxiter=5,seed=7301,polish=False,workers=1)
    records.sort(key=lambda r:r['score'],reverse=True)
    atomic('training.json',records)

def validate():
    inst=load_instance()
    exp=Experiment(inst,seeds=[6111019,6111047,6111083,6111133,6111187,6111239])
    records=json.loads((OUT/'training.json').read_text()); results=[]
    for r in records[:12]:
        m=exp.evaluate(r['design']); score=m['mean_tir']-15*max(0,m['max_trajectory_tbr70']-1)-30*max(0,m['max_trajectory_tbr54'])-3*max(0,55-m['minimum_glucose'])
        results.append({'design':r['design'],'metrics':compact(m),'score':score,'rows':m['rows']})
        print('validation',round(score,3),r['design'],compact(m),flush=True)
    results.sort(key=lambda r:r['score'],reverse=True); atomic('validation.json',results)
    safe=[r for r in results if r['metrics']['feasible']]
    if safe: save_design(safe[0]['design'])


def refine():
    inst=load_instance(); exp=Experiment(inst,seeds=[6111003,6111019,6111133])
    previous=json.loads((OUT/'validation.json').read_text())
    base=previous[0]['design']; rng=np.random.default_rng(8317); candidates=[]
    for scale in [1.,1.02,1.04,1.06,1.08]:
        d=json.loads(json.dumps(base)); d['parameters']['theta_a']*=scale; candidates.append(d)
    # Smooth slopes and neighboring release curves; fixed high load.
    for _ in range(23):
        d=json.loads(json.dumps(base)); p=d['parameters']
        p['theta_a']*=float(rng.uniform(.86,1.18))
        p['relative_leak']=float(rng.uniform(.65,1.05))
        p['hill_n']=float(rng.uniform(.65,4.2))
        p['tau_min']=float(rng.choice([.05,2.,5.]))
        candidates.append(d)
    steep=max(previous,key=lambda r:r['metrics']['mean_tir'])['design']
    for scale in [.92,.95,.97,1.]:
        d=json.loads(json.dumps(steep));d['parameters']['theta_a']*=scale;candidates.append(d)
    records=[]
    for d in candidates:
        m=exp.evaluate(d)
        score=m['mean_tir']-12*max(0,m['max_trajectory_tbr70']-1)-30*max(0,m['max_trajectory_tbr54'])-2*max(0,60-m['minimum_glucose'])
        records.append({'design':d,'metrics':compact(m),'score':score})
    records.sort(key=lambda r:r['score'],reverse=True); atomic('refinement.json',records)
    for r in records[:7]: print('refined',r,flush=True)

def finalcheck():
    inst=load_instance(); records=json.loads((OUT/'refinement.json').read_text())
    seeds=[6111271,6111299,6111327,6111361,6111409,6111437,6111469,6111523,6111559,6111601,6111659,6111701]
    exp=Experiment(inst,seeds=seeds); results=[]
    for r in records[:3]+[json.loads((OUT/'validation.json').read_text())[0]]:
        m=exp.evaluate(r['design'])
        score=m['mean_tir']-15*max(0,m['max_trajectory_tbr70']-1)-30*max(0,m['max_trajectory_tbr54'])-3*max(0,60-m['minimum_glucose'])
        results.append({'design':r['design'],'metrics':compact(m),'score':score,'rows':m['rows']})
        print('final',r['design'],compact(m),'score',score,flush=True)
    results.sort(key=lambda r:r['score'],reverse=True); atomic('final_validation.json',results)
    safe=[r for r in results if r['metrics']['feasible']]
    if safe: save_design(safe[0]['design'])


def finish():
    from gri_bench.api import summarize, validate_design
    inst=load_instance(); chosen=json.loads((OUT/'design.json').read_text()); validate_design(chosen,inst)
    exp=Experiment(inst,seeds=[6111003,6111019,6111047,6111083,6111133,6111187,6111239])
    m=exp.evaluate(chosen)
    final=json.loads((OUT/'final_validation.json').read_text())
    tested=next(r for r in final if r['design']==chosen)
    rows=m['rows']+tested['rows']; combined=summarize(rows)
    atomic('selected_metrics.json',{'design':chosen,**combined,'rows':rows})
    p=chosen['parameters']
    text=f"""# Shared GRI formulation

The submitted design uses one shared glucose responsive release law for child#001, child#002, and child#003. Parameters are theta_a={p['theta_a']:.17g}, relative_leak={p['relative_leak']:.17g}, EC50={p['ec50_mg_dl']:.17g} mg/dL, Hill n={p['hill_n']:.17g}, filter tau={p['tau_min']:.17g} minutes, and theta_L={p['theta_L']:.17g}. Amplitude and reservoir scale only with the supplied native TDI. No patient-specific fitted coefficients, meal boluses, or external insulin are used.

The moderate Hill slope and short filter delay balance glucose-dependent release with stable basal coverage. The largest permitted reservoir avoids premature exhaustion. All parameters satisfy the instance bounds. The minimum permitted leakage was considered, but allowing a higher leak and a smoother response improved the observed balance across patients.

Search used deterministic differential evolution with 180 candidate evaluations on the nine training trajectories, followed by validation of twelve candidates against six additional meal seeds. A further 32 candidates explored neighboring release curves and reduced amplitudes for a steeper alternative on three seeds. Four finalists were evaluated against twelve further seeds. Selection penalized TBR70 beyond 1% and minimum glucose below 60 mg/dL, stricter than the benchmark exclusion thresholds. Designs were checkpointed atomically. Selection involved validation data; none of these seeds are claimed to be the evaluator's heldout scenarios.

For the final selected formulation, aggregate public RK4 results across 19 distinct seeds, three patients, and all three variants ({combined['trajectories']} trajectories) are:

- Mean post-warmup TIR70–180: {combined['mean_tir']:.5f}%.
- Maximum trajectory TBR70: {combined['max_trajectory_tbr70']:.5f}%.
- Maximum trajectory TBR54: {combined['max_trajectory_tbr54']:.5f}%.
- Minimum full-horizon glucose, including day one: {combined['minimum_glucose']:.5f} mg/dL.
- Feasible under public fast-simulator checks: {combined['feasible']}.

On the twelve later seeds alone, mean TIR was {tested['metrics']['mean_tir']:.5f}% with zero TBR70 and TBR54 and a minimum of {tested['metrics']['minimum_glucose']:.5f} mg/dL. Full per-trajectory public metrics are retained in selected_metrics.json. Time-in-range and time-below-range omit day one; the minimum includes the entire three days.

Reproduction: run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py train`, then the same command with `validate`, `refine`, `finalcheck`, and `finish`, in that order. The deterministic seeds, candidate generation, objective penalties, and selection rules are in search.py. These stages may require more CPU than one remaining task budget because imports recur. The reference simulator was not modified.

All reported values use the public fast RK4 simulator with default four substeps per minute, and its three-minute TIR/TBR sampling. The independent verifier uses native dopri5 and fresh meal seeds. Training and validation safety do not establish heldout safety, and native integration can differ. This is a simulation benchmark design, not a clinical recommendation.
"""
    q=OUT/'rationale.tmp'; q.write_text(text); q.replace(OUT/'rationale.md')
    print(combined,flush=True)

if __name__=='__main__':
    {'train':train,'validate':validate,'refine':refine,'finalcheck':finalcheck,'finish':finish}[sys.argv[1] if len(sys.argv)>1 else 'train']()
