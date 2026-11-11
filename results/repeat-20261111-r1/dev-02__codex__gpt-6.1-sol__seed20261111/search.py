"""Reproducible shared-formulation search for dev-02.
Run with OPENBLAS_NUM_THREADS=1. Uses public physiology unchanged, RK4 1-minute
steps for search and API-default 0.25-minute steps for final verification.
"""
import json, time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import (load_instance, Experiment, PARAMETERS, individual_design,
                           glucose_metrics, summarize, save_design)
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')
INSTANCE=load_instance()
LEAK=INSTANCE['bounds']['relative_leak'][0]

def design_for(x):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,
        [float(x[0]),LEAK,float(x[1]),float(x[2]),float(x[3]),4.0]))}

def evaluate(exp, design, substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in exp.jobs:
        trace=fast_trace(p,initial,meals,individual_design(design,INSTANCE['tdi'][name]),substeps)
        rows.append({'patient':name,'seed':seed,'variant':variant,
                     'metrics':glucose_metrics(trace,INSTANCE['warmup_minutes'])})
    return {**summarize(rows),'rows':rows}

def atomic_json(name, value):
    p=OUT/name; t=p.with_suffix('.tmp')
    t.write_text(json.dumps(value,indent=2)+'\n'); t.replace(p)

def coarse_search():
    exp=Experiment(INSTANCE,seeds=[6111002,84211,23253])
    records=[]; best=[-1e9]; start=time.process_time()
    def objective(x):
        d=design_for(x); m=evaluate(exp,d)
        # Penalize even subthreshold hypoglycemia to reduce new-seed failures.
        penalty=3*max(0,65-m['minimum_glucose']) + 8*m['max_trajectory_tbr70'] + 15*m['max_trajectory_tbr54']
        score=m['mean_tir']-penalty
        records.append({'x':list(map(float,x)),'score':score,'metrics':{k:v for k,v in m.items() if k!='rows'}})
        if score>best[0]:
            best[0]=score; save_design(d); atomic_json('search_checkpoint.json',{'design':d,'metrics':m,'evaluations':len(records)})
        return -score
    result=differential_evolution(objective,[(.00035,.0011),(95,300),(.6,24),(.05,20)],
        popsize=8,maxiter=8,polish=False,seed=19427,workers=1,updating='immediate',tol=0)
    atomic_json('search_history.json',records)
    print(json.dumps({'evaluations':len(records),'cpu_seconds':time.process_time()-start,
        'best':sorted(records,key=lambda z:-z['score'])[:8]},indent=2),flush=True)



import json,time
import numpy as np


def refine_search():
    start=time.process_time()
    exp=Experiment(INSTANCE,seeds=[6111002,84211,23253])
    candidates=[]
    for ec in [60.,75.,90.,110.,140.,180.]:
      for a in np.linspace(.00030,.00058,10):
       for n in [4.,20.]:
        d=design_for([a,ec,n,.05]); m=evaluate(exp,d)
        score=m['mean_tir']-3*max(0,67-m['minimum_glucose'])-8*m['max_trajectory_tbr70']-15*m['max_trajectory_tbr54']
        candidates.append({'design':d,'score':score,'metrics':{k:v for k,v in m.items() if k!='rows'}})
    previous=json.loads((OUT/'search_history.json').read_text())
    for r in previous:
      if r['metrics']['minimum_glucose']>=67 and r['metrics']['max_trajectory_tbr70']==0:
        candidates.append({'design':design_for(r['x']),'score':r['score'],'metrics':r['metrics']})
    candidates.sort(key=lambda r:-r['score'])
    atomic_json('refinement.json',candidates)
    print('grid best',json.dumps(candidates[:6]),'cpu',time.process_time()-start,flush=True)
    # Separate fresh seed bank; every seed includes all three challenge variants.
    seeds=[918273,270119,398401,784013,129905,456071,932153,681033,144827,507091,380117,220913,709249,852113,639781,472169]
    val=Experiment(INSTANCE,seeds=seeds)
    finalists=[]
    for r in candidates[:6]:
        m=evaluate(val,r['design'])
        r={**r,'validation':m}
        finalists.append(r)
        print('validation',r['design'],{k:v for k,v in m.items() if k!='rows'},flush=True)
    # Prefer fully observed absence of hypoglycemia, and margin for unseen meals.
    safe=[r for r in finalists if r['validation']['minimum_glucose']>=65 and r['validation']['max_trajectory_tbr70']==0]
    if not safe:
        safe=[r for r in finalists if r['validation']['feasible']]
    if safe:
        chosen=max(safe,key=lambda r:r['validation']['mean_tir'])
    else:
        chosen=min(finalists,key=lambda r:r['validation']['max_trajectory_tbr70'])
        chosen['design']['parameters']['theta_a']*=.92
    save_design(chosen['design'])
    atomic_json('finalists.json',finalists)
    train=evaluate(exp,chosen['design'],4)
    valid=evaluate(val,chosen['design'],4)
    atomic_json('verification.json',{'training_and_search_seeds':train,'fresh_validation':valid,'design':chosen['design']})
    print('FINAL',json.dumps(chosen['design']),{k:v for k,v in train.items() if k!='rows'},{k:v for k,v in valid.items() if k!='rows'},'cpu',time.process_time()-start,flush=True)



import json,time


def tune_search():
    seeds=[918273,270119,398401,784013,129905,456071,932153,681033,144827,507091,380117,220913,709249,852113,639781,472169]
    exp=Experiment(INSTANCE,seeds=seeds)
    records=[]
    for a in [.0003622222222222222,.00037,.000375,.00038,.000385,.00039]:
        d=design_for([a,90.,20.,.05]); m=evaluate(exp,d)
        records.append({'design':d,'metrics':m})
        print('dose',a,{k:v for k,v in m.items() if k!='rows'},flush=True)
    eligible=[r for r in records if r['metrics']['minimum_glucose']>=65 and r['metrics']['max_trajectory_tbr70']==0]
    chosen=max(eligible,key=lambda r:r['metrics']['mean_tir'])['design']
    save_design(chosen)
    # Final new bank is not used in coarse or refinement search.
    fresh_seeds=[104729+7919*k for k in range(32)]
    fresh=Experiment(INSTANCE,seeds=fresh_seeds)
    stress=evaluate(fresh,chosen)
    if not stress['feasible'] or stress['minimum_glucose']<60:
        chosen['parameters']['theta_a']*=.97
        save_design(chosen)
        stress=evaluate(fresh,chosen)
    train_exp=Experiment(INSTANCE)
    training=evaluate(train_exp,chosen,4)
    validation=evaluate(exp,chosen,4)
    # Fine-step cross-check on the worst observed fresh trajectory.
    worst=min(stress['rows'],key=lambda r:r['metrics']['minimum'])
    fine_worst=Experiment(INSTANCE,seeds=[worst['seed']],variants=[worst['variant']])
    check=evaluate(fine_worst,chosen,4)
    atomic_json('dose_tuning.json',records)
    atomic_json('final_verification.json',{'design':chosen,'training':training,'selection_bank':validation,'fresh_32_seeds':stress,'fine_step_worst_seed':check})
    save_design(chosen)
    summary={key:{k:v for k,v in value.items() if k!='rows'} for key,value in [('training',training),('selection_bank',validation),('fresh_32_seeds',stress),('fine_step_worst_seed',check)]}
    text='''# Shared responsive formulation for dev-02\n\nThe final design uses one coefficient set for all three known adolescent profiles. Amplitude and reservoir load scale only with native TDI, as required.\n\n```json\n'''+json.dumps(chosen,indent=2)+'''\n```\n\nMinimum permitted relative leak provides the greatest available reduction in release at low glucose. The steep response near 90 mg/dL reduces delivery as glucose falls; rapid filtering avoids additional material delay. Insulin absorption and action still have physiological delays. The maximum permitted reservoir (4 times TDI) avoids premature exhaustion during the three-day experiment.\n\nSearch used unchanged public physiology with RK4 at one-minute steps, followed by checks at the API-default quarter-minute steps. Differential evolution (288 candidates, deterministic seed 19427) used the supplied seed and two additional seeds, with all three variants. A 120-candidate grid extended the search toward lower EC50. Six finalists were evaluated on 16 different seeds; the selected shape then underwent a local dose sweep. Selection penalized hypoglycemia and required minimum glucose at least 65 mg/dL with zero TBR70 in the 16-seed bank. A final bank of 32 additional seeds tested all patients and variants (288 trajectories). The worst fresh seed and variant received a quarter-minute integration cross-check for all patients.\n\nObserved results:\n\n| Bank | Trajectories | Mean TIR (%) | Worst TBR70 (%) | Worst TBR54 (%) | Full-horizon minimum (mg/dL) |\n|---|---:|---:|---:|---:|---:|\n'''
    for key,label in [('training','Supplied training seed, quarter-minute RK4'),('selection_bank','16-seed selection bank, quarter-minute RK4'),('fresh_32_seeds','32 fresh seeds, one-minute RK4'),('fine_step_worst_seed','Worst fresh seed/variant, quarter-minute RK4')]:
        m=summary[key]
        text+=f"| {label} | {m['trajectories']} | {m['mean_tir']:.4f} | {m['max_trajectory_tbr70']:.4f} | {m['max_trajectory_tbr54']:.4f} | {m['minimum_glucose']:.4f} |\n"
    text+='''\nTIR/TBR omit day one; minimum glucose includes all three days and all minute endpoints. These are public fast-integrator observations, not results from the trusted native dopri5 verifier. Unobserved meal seeds can still violate safety constraints; sampled feasibility is not a held-out safety guarantee. This is a simulation benchmark formulation, not a clinical recommendation.\n\nReproduction: run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`. The combined script repeats coarse search, grid refinement, validation, local dose tuning, and atomic final design saving. Detailed observed trajectories and seed banks are stored in final_verification.json.\n'''
    p=OUT/'rationale.md'; tmp=p.with_suffix('.tmp'); tmp.write_text(text); tmp.replace(p)
    print('FINAL',json.dumps(chosen),json.dumps(summary),flush=True)



if __name__ == '__main__':
    coarse_search()
    refine_search()
    tune_search()
