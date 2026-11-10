"""Deterministic shared-formulation search. Run from the benchmark environment.
Stage 1 screens using RK4 with one substep/minute. Later stages use the
public four-substep integrator and independent meal seeds.
"""
import os, json, time
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, individual_design, glucose_metrics, summarize, save_design
from gri_bench.physiology import fast_trace
INSTANCE=load_instance()
def design(a, ec=150., n=12., tau=0.05, leak=None):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[a,INSTANCE['bounds']['relative_leak'][0] if leak is None else leak,ec,n,tau,1.25]))}
def evaluate(experiment,d,substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in experiment.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,INSTANCE['tdi'][name]),substeps)
        rows.append({'patient':name,'seed':int(seed),'variant':variant,'metrics':glucose_metrics(trace)})
    return dict(summarize(rows),rows=rows)
def record(d,m,stage):
    with open('/work/output/history.jsonl','a') as f:
        f.write(json.dumps({'stage':stage,'design':d,'metrics':m})+'\n')
if __name__=='__main__':
    Path('/work/output/history.jsonl').write_text('')
    t=time.process_time(); exp=Experiment(INSTANCE)
    print('setup',time.process_time()-t,flush=True)
    for a in [0.00025,0.00035,0.00045,0.00055,0.00065]:
        d=design(a); m=evaluate(exp,d);record(d,m,'initial amplitude')
        print(a,{k:v for k,v in m.items() if k!='rows'},'cpu',time.process_time()-t,flush=True)
    candidates=[]
    for a in np.linspace(.00020,.00062,15):
        for ec in [100.,130.,160.,200.,250.,320.,420.]:
            for n in [2.,6.,12.,24.]:
                d=design(float(a),ec,n);m=evaluate(exp,d)
                record(d,m,'grid')
                if m['feasible']:
                    candidates.append((m['mean_tir'],d,m))
    candidates.sort(key=lambda x:x[0],reverse=True)
    save_design(candidates[0][1])
    with open('/work/output/candidates.json','w') as f: json.dump(candidates[:40],f,indent=2)
    for score,d,m in candidates[:15]:
        print(round(score,3),d['parameters'], 'min',round(m['minimum_glucose'],2),'tbr',round(m['max_trajectory_tbr70'],2),flush=True)
    print('cpu',time.process_time()-t,flush=True)

    t=time.process_time();exp=Experiment(INSTANCE)
    candidates=json.load(open('/work/output/candidates.json'))
    for a in np.linspace(.00030,.00058,15):
        for ec in [59.26305046791457,75.,90.,110.]:
            for n in [.5880395112623367,2.,6.,24.]:
                d=design(float(a),ec,n);m=evaluate(exp,d);record(d,m,'refinement')
                if m['feasible']: candidates.append((m['mean_tir'],d,m))
    for a in np.linspace(.00025,.00065,25):
        d={'mode':'constant','parameters':{'theta_c':float(a),'theta_L':1.25}}
        m=evaluate(exp,d);record(d,m,'constant comparison')
        if m['feasible']: candidates.append((m['mean_tir'],d,m))
    candidates.sort(key=lambda x:x[0],reverse=True)
    save_design(candidates[0][1])
    print('REFINE',[(round(x[0],2),x[1]) for x in candidates[:6]],flush=True)
    # Independent scenarios, same cohort, all three challenge variants.
    validation=Experiment(INSTANCE,seeds=[31017,47023,59009,71011,89003,97001])
    ranked=[]
    for _,d,mtrain in candidates[:16]:
        m=evaluate(validation,d);record(d,m,'fresh screening')
        if m['feasible']:
            ranked.append((m['mean_tir'],d,m,mtrain))
    ranked.sort(key=lambda x:x[0],reverse=True)
    with open('/work/output/validation_candidates.json','w') as f:json.dump(ranked,f)
    save_design(ranked[0][1])
    for score,d,m,mt in ranked[:8]:print('VALIDATION',score,d,'minimum',m['minimum_glucose'],'tbr',m['max_trajectory_tbr70'],flush=True)
    print('cpu',time.process_time()-t,flush=True)

    t=time.process_time()
    exp=Experiment(INSTANCE,seeds=[6111004,31017,47023,59009])
    rank=[]
    for a in np.linspace(.00048,.00064,9):
        for ec in [59.26305046791457,110.,200.]:
            for n in [.5880395112623367,1.2]:
                d=design(float(a),ec,n);m=evaluate(exp,d);record(d,m,'pooled refinement')
                if m['feasible'] and m['minimum_glucose']>=65:
                    rank.append((m['mean_tir'],d,m))
    for a in np.linspace(.00048,.00064,9):
        d={'mode':'constant','parameters':{'theta_c':float(a),'theta_L':1.25}}
        m=evaluate(exp,d);record(d,m,'pooled constant')
        if m['feasible'] and m['minimum_glucose']>=65:rank.append((m['mean_tir'],d,m))
    rank.sort(key=lambda x:x[0],reverse=True)
    print('POOLED',[(round(x[0],2),x[1]) for x in rank[:6]],flush=True)
    # Additional independent seeds, evaluated with the default 0.25 minute RK4.
    seeds=[31017,47023,59009,71011,89003,97001,105019,119027,131009,149011,157007,173021]
    val=Experiment(INSTANCE,seeds=seeds)
    final=[]
    for _,d,mt in rank[:5]:
        m=evaluate(val,d,4);record(d,m,'fine validation')
        if m['feasible'] and m['minimum_glucose']>=60:final.append((m['mean_tir'],d,m,mt))
    final.sort(key=lambda x:x[0],reverse=True)
    chosen=final[0];save_design(chosen[1])
    with open('/work/output/final_metrics.json','w') as f:json.dump(chosen,f,indent=2)
    print('FINAL',chosen[1],{k:v for k,v in chosen[2].items() if k!='rows'},flush=True)
    print('cpu',time.process_time()-t,flush=True)

    reserve = Experiment(INSTANCE, seeds=[200003,220009,240007,260003,280001,300007])
    reserve_metrics = evaluate(reserve, chosen[1], 4)
    record(chosen[1], reserve_metrics, 'untouched reserve')
    Path('/work/output/reserve_metrics.json').write_text(json.dumps(reserve_metrics, indent=2)+'\n')
    print('Untouched reserve', {k:v for k,v in reserve_metrics.items() if k != 'rows'})
