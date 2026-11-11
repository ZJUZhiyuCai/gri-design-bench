"""Deterministic shared-formulation search using public benchmark physiology.
Screen with one-minute RK4; finalists are checked with default quarter-minute RK4.
All candidates use one shared parameter vector and native TDI scaling.
"""
import os, json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, save_design
from gri_bench.physiology import fast_trace
OUT='/work/output'

def design(a, ec=160., n=12., tau=.05, leak=.5124966150526034, load=4.):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load))}

def evaluate(ex, d, substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,ex.instance['tdi'][name]),substeps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace)))
    return dict(**summarize(rows),rows=rows)

def record(d,m,stage):
    with open(OUT+'/trials.jsonl','a') as f:
        f.write(json.dumps(dict(design=d,metrics=m,stage=stage))+'\n')

def initial_search():
    ex=Experiment(load_instance())
    best=-1
    for ec in [130.,170.,220.]:
        for a in [.00045,.00065,.00085,.00105]:
            d=design(a,ec)
            m=evaluate(ex,d)
            record(d,m,'initial-grid')
            print(a,ec,{k:round(m[k],3) if isinstance(m[k],float) else m[k] for k in ['mean_tir','max_trajectory_tbr70','max_trajectory_tbr54','minimum_glucose']},flush=True)
            if m['feasible'] and m['mean_tir']>best:
                best=m['mean_tir'];save_design(d)



def shape_search():
    ex=Experiment(load_instance())
    trials=[]
    for ec in [85.,105.,125.,145.,165.]:
     for n in [2.,5.,12.,24.]:
      for a in [.0004,.00048,.00056]:
       d=design(a,ec,n);m=evaluate(ex,d);record(d,m,'shape-grid')
       if m['max_trajectory_tbr70']<=2 and m['max_trajectory_tbr54']<=.2 and m['minimum_glucose']>=52:
        trials.append((m['mean_tir'],d,m))
    trials.sort(key=lambda x:x[0],reverse=True)
    for score,d,m in trials[:12]:print(json.dumps(dict(design=d,metrics={k:v for k,v in m.items() if k!='rows'})),flush=True)
    if trials:save_design(trials[0][1])
    with open(OUT+'/shortlist.json','w') as f:json.dump(trials[:15],f)


def fresh_validation():
    seeds=[802101,802102,802103,802104,802105,802106]
    ex=Experiment(load_instance(),seeds=seeds)
    alltr=[json.loads(l) for l in open(OUT+'/trials.jsonl')]
    alltr.sort(key=lambda t:t['metrics']['mean_tir'],reverse=True)
    chosen=[]
    for t in alltr:
     m=t['metrics']
     if m['max_trajectory_tbr70']<=4 and m['max_trajectory_tbr54']<=1 and m['minimum_glucose']>=48:
      if not any(t['design']==d for d in chosen): chosen.append(t['design'])
     if len(chosen)==10:break
    results=[]
    for d in chosen:
     m=evaluate(ex,d);record(d,m,'fresh-six-seeds');results.append((m['mean_tir'],d,m))
     print(json.dumps(dict(design=d,metrics={k:v for k,v in m.items() if k!='rows'})),flush=True)
    results.sort(key=lambda x:x[0],reverse=True)
    safe=[r for r in results if r[2]['max_trajectory_tbr70']<=2 and r[2]['max_trajectory_tbr54']<=.2 and r[2]['minimum_glucose']>=52]
    if safe:save_design(safe[0][1])
    with open(OUT+'/validation.json','w') as f:json.dump(results,f)


def robust_search():
    r=json.load(open(OUT+'/validation.json'))
    for _,d,m in r:
     if d['parameters']['theta_a']==.0004 and d['parameters']['hill_n']==5.:
      for row in sorted(m['rows'],key=lambda x:x['metrics']['minimum'])[:8]:print(row)
    ex=Experiment(load_instance(),seeds=[802101,802102,802103,802104,802105,802106])
    results=[]
    for ec in [85.,100.,115.,130.]:
     for n in [5.,12.,24.]:
      for a in [.00032,.00036,.00039]:
       d=design(a,ec,n);m=evaluate(ex,d);record(d,m,'robust-grid');results.append((m['mean_tir'],d,m))
    results.sort(key=lambda x:x[0],reverse=True)
    safe=[r for r in results if r[2]['max_trajectory_tbr70']<=1.5 and r[2]['max_trajectory_tbr54']==0 and r[2]['minimum_glucose']>=60]
    for score,d,m in safe[:10]:print(json.dumps(dict(design=d,metrics={k:v for k,v in m.items() if k!='rows'})),flush=True)
    if safe:save_design(safe[0][1])
    json.dump(results,open(OUT+'/robust.json','w'))


def margin_search():
    ex=Experiment(load_instance(),seeds=[802101,802102,802103,802104,802105,802106])
    results=[]
    for a in [.00034,.00035,.00036,.00037]:
     for ec in [75.,85.,95.,105.]:
      d=design(a,ec,24.);m=evaluate(ex,d);record(d,m,'local-margin');results.append((m['mean_tir'],d,m))
    safe=[r for r in results if r[2]['max_trajectory_tbr70']==0 and r[2]['minimum_glucose']>=73]
    safe.sort(key=lambda x:x[0],reverse=True)
    for r in safe[:5]: print(r[0],r[1],r[2]['minimum_glucose'],flush=True)
    if safe:save_design(safe[0][1])
    # New scenario seeds, not used for the preceding grids.
    vex=Experiment(load_instance(),seeds=list(range(913201,913213)))
    final=[]
    for _,d,_ in safe[:3]:
     m=evaluate(vex,d);record(d,m,'independent-twelve');final.append((m['mean_tir'],d,m))
     print('NEW',d,{k:v for k,v in m.items() if k!='rows'},flush=True)
    json.dump(final,open(OUT+'/independent.json','w'))
    passing=[r for r in final if r[2]['max_trajectory_tbr70']<=1 and r[2]['max_trajectory_tbr54']==0 and r[2]['minimum_glucose']>=60]
    if passing:save_design(max(passing,key=lambda r:r[0])[1])


def fine_and_native_check():
    from gri_bench.native import native_trace
    inst=load_instance(); d=json.load(open(OUT+'/design.json'))
    ex=Experiment(inst,seeds=inst['training_seeds']+list(range(802101,802107))+list(range(913201,913213)))
    m=evaluate(ex,d,4)
    json.dump(m,open(OUT+'/verification.json','w'),indent=2)
    print('QUARTER-MINUTE', {k:v for k,v in m.items() if k!='rows'},flush=True)
    worst=min(m['rows'],key=lambda r:r['metrics']['minimum'])
    job=next(j for j in ex.jobs if (j[0],j[1],j[2])==(worst['patient'],worst['seed'],worst['variant']))
    name,seed,variant,p,initial,meals=job
    trace,minute=native_trace(name,meals,individual_design(d,inst['tdi'][name]),inst['patient_seed'])
    nm=glucose_metrics(trace,inst['warmup_minutes'],minute)
    print('NATIVE',name,seed,variant,nm,flush=True)
    json.dump(dict(patient=name,seed=seed,variant=variant,metrics=nm,fast=worst['metrics']),open(OUT+'/native_check.json','w'),indent=2)


def extra_validation():
    d=json.load(open(OUT+'/design.json'))
    ex=Experiment(load_instance(),seeds=list(range(1244001,1244021)))
    m=evaluate(ex,d)
    json.dump(m,open(OUT+'/extra_validation.json','w'),indent=2)
    record(d,m,'final-twenty-seeds')
    print({k:v for k,v in m.items() if k!='rows'},flush=True)


def main():
    # Full deterministic research sequence; the benchmark does not execute this.
    # Start a fresh log so reruns produce the same candidate ordering.
    Path = __import__('pathlib').Path
    Path(OUT).mkdir(parents=True, exist_ok=True)
    Path(OUT+'/trials.jsonl').write_text('')
    initial_search()
    shape_search()
    fresh_validation()
    robust_search()
    margin_search()
    fine_and_native_check()
    extra_validation()

if __name__ == '__main__':
    main()
