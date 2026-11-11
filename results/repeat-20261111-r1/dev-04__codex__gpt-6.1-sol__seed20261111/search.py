"""Deterministic bounded search and fresh-seed screening for dev-04.
Run with OPENBLAS_NUM_THREADS=1. Writes checkpoints atomically.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json, time
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design
OUT=Path('/work/output')

def design(a, leak, ec, n, tau, load=1.25):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load))}

def compact(m):
    return {k:v for k,v in m.items() if k!='rows'}

def initial_search():
    instance=load_instance(); exp=Experiment(instance); rng=np.random.default_rng(44204)
    candidates=[]; best=-1
    # Cover rates and glucose thresholds; lower leak permits stronger modulation.
    proposals=[]
    for _ in range(110):
        leak = 0.5124966150526034 if rng.random()<0.7 else rng.uniform(0.5124966150526034,3.0)
        effective=rng.uniform(0.00048,0.0012)
        proposals.append(design(effective/(1+leak),leak,rng.uniform(100,330),rng.choice([4.,8.,16.,24.]),rng.choice([0.05,2.,10.,20.])))
    for _ in range(10):
        proposals.append({'mode':'constant','parameters':{'theta_c':float(rng.uniform(.00035,.0008)),'theta_L':1.25}})
    for i,d in enumerate(proposals):
        m=exp.evaluate(d); candidates.append({'design':d,'training':compact(m)})
        if m['feasible'] and m['minimum_glucose']>=65 and m['max_trajectory_tbr70']<=1 and m['mean_tir']>best:
            best=m['mean_tir']; save_design(d)
            print('best',i,json.dumps(candidates[-1]),flush=True)
    (OUT/'candidates.json').write_text(json.dumps(candidates,indent=2))
    print('evaluations',exp.evaluations,flush=True)



def validate_candidates():
    cs=json.load(open('/work/output/candidates.json'))
    cs=[c for c in cs if c['training']['feasible'] and c['training']['minimum_glucose']>=65]
    cs.sort(key=lambda c:c['training']['mean_tir'],reverse=True)
    e=Experiment(load_instance(),seeds=[827531,193749,508213,978041])
    results=[]
    for c in cs[:12]:
     m=e.evaluate(c['design']); c['validation']=compact(m); results.append(c)
     print(json.dumps(c),flush=True)
    json.dump(results,open('/work/output/validation.json','w'),indent=2)
    safe=[c for c in results if c['validation']['feasible'] and c['validation']['minimum_glucose']>=60 and c['validation']['max_trajectory_tbr70']<=2]
    if safe:
     c=max(safe,key=lambda c:c['validation']['mean_tir']);save_design(c['design']);print('SELECTED',json.dumps(c),flush=True)

def refine_candidates():
    rng=np.random.default_rng(44205); inst=load_instance(); exp=Experiment(inst)
    cs=json.load(open('/work/output/candidates.json')); base=json.load(open('/work/output/design.json'))
    for i in range(60):
     if i<48:
      basal=rng.uniform(.00043,.00057); peak=rng.uniform(.00063,.00080)
      a=peak-basal; leak=basal/a
      if leak>inst['bounds']['relative_leak'][1]: continue
      d=design(a,leak,rng.uniform(140,220),rng.choice([12.,20.,24.]),rng.choice([.05,5.,20.]))
     else:
      p=base['parameters'];d=design(p['theta_a']*rng.uniform(.93,1.07),p['relative_leak']*rng.uniform(.9,1.1),p['ec50_mg_dl']*rng.uniform(.85,1.15),24.,rng.uniform(.05,20))
     m=exp.evaluate(d);cs.append({'design':d,'training':compact(m)})
    cs=[c for c in cs if c['training']['feasible'] and c['training']['minimum_glucose']>=72]
    cs.sort(key=lambda c:c['training']['mean_tir'],reverse=True)
    val=Experiment(inst,seeds=[827531,193749,508213,978041]);results=[]
    for c in cs[:7]:
     m=val.evaluate(c['design']);c['validation']=compact(m);results.append(c);print(json.dumps(c),flush=True)
    prev=json.load(open('/work/output/validation.json'));results+=prev
    safe=[c for c in results if c['validation']['feasible'] and c['validation']['minimum_glucose']>=72 and c['validation']['max_trajectory_tbr70']==0]
    best=max(safe,key=lambda c:c['validation']['mean_tir']);save_design(best['design'])
    json.dump(cs,open('/work/output/refinement.json','w'),indent=2)
    json.dump(results,open('/work/output/refined_validation.json','w'),indent=2)
    print('BEST',json.dumps(best),flush=True)
    # Additional independent seeds, not used for fitting.
    seeds=[613501,762947,119083,420173,882761,210359,355901,901277,658219,741031]
    held=Experiment(inst,seeds=seeds);m=held.evaluate(best['design'])
    json.dump(m,open('/work/output/heldout_metrics.json','w'),indent=2)
    print('HELDOUT',json.dumps(compact(m)),flush=True)
    print('WORST',json.dumps(sorted(m['rows'],key=lambda r:r['metrics']['minimum'])[:3]),flush=True)

def final_assessment():
    from gri_bench.native import native_trace
    from gri_bench.api import individual_design, glucose_metrics, summarize
    inst=load_instance(); d=json.loads((OUT/'design.json').read_text())
    seeds=[1000003+7919*i for i in range(20)]
    ex=Experiment(inst,seeds=seeds); metrics=ex.evaluate(d)
    (OUT/'additional_metrics.json').write_text(json.dumps(metrics,indent=2))
    print('ADDITIONAL',json.dumps(compact(metrics)),flush=True)
    ex=Experiment(inst,seeds=[420173],variants=['ordinary']); rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace,minute=native_trace(name,meals,individual_design(d,inst['tdi'][name]),inst['patient_seed'])
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace,inst['warmup_minutes'],minute)))
    result={**summarize(rows),'rows':rows}
    (OUT/'native_cohort_metrics.json').write_text(json.dumps(result,indent=2))
    print('NATIVE',json.dumps(result),flush=True)

def main():
    initial_search()
    validate_candidates()
    refine_candidates()
    final_assessment()

if __name__ == "__main__":
    main()
