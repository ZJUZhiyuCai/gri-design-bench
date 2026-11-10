"""Deterministic cohort search and fresh-scenario validation.
Run stages sequentially: python search.py initial|refine|validate.
Uses the public physiology, with one-minute RK4 during search.
"""
import os, json, time, pickle, sys
import numpy as np
from gri_bench import api
from gri_bench.physiology import fast_trace
OUT='/work/output'
def design(a, ec=150, n=8, tau=1, leak=0.5124966150526034, load=4):
    return {'mode':'responsive','parameters':dict(zip(api.PARAMETERS,[a,leak,ec,n,tau,load]))}
def experiment(seeds=None):
    return api.Experiment(api.load_instance(),seeds=seeds)
def evaluate(ex,d,steps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        tr=fast_trace(p,initial,meals,api.individual_design(d,ex.instance['tdi'][name]),substeps=steps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=api.glucose_metrics(tr)))
    return dict(api.summarize(rows),rows=rows)
def record(d,m,label):
    with open(OUT+'/trials.jsonl','a') as f: f.write(json.dumps(dict(design=d,metrics=m,label=label))+'\n')
    print(label,json.dumps(d['parameters']),json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
def run(ds,ex,label,steps=1):
    results=[]
    for d in ds:
        m=evaluate(ex,d,steps); record(d,m,label); results.append((d,m))
    return results
if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else 'initial'
    if stage=='initial':
        ex=experiment()
        with open(OUT+'/training.pkl','wb') as f: pickle.dump(ex,f)
        run([design(a) for a in [0.00035,0.00045,0.00055,0.00065,0.00075]],ex,stage)
    elif stage=='refine':
        with open(OUT+'/training.pkl','rb') as f: ex=pickle.load(f)
        ds=[design(a,ec,n=24,tau=0.05) for ec in [100,130,180,220,270] for a in [0.0004,0.0005,0.0006]]
        rs=run(ds,ex,stage)
        feasible=[(d,m) for d,m in rs if m['feasible']]
        if feasible:
            d,m=max(feasible,key=lambda x:x[1]['mean_tir'])
            api.save_design(d)
    elif stage=='robust':
        ex=experiment([6111003,93017,240819])
        with open(OUT+'/robust.pkl','wb') as f: pickle.dump(ex,f)
        ds=[design(a,ec,n=n,tau=0.05) for n in [2,4,8,24] for ec in [130,180] for a in [0.00042,0.00048]]
        rs=run(ds,ex,stage)
        feasible=[(d,m) for d,m in rs if m['feasible']]
        if feasible:
            d,m=max(feasible,key=lambda x:x[1]['mean_tir'])
            api.save_design(d)
    elif stage=='stress':
        ex=experiment([6111003,93017,240819,760031,85091,410257,90731,120113])
        with open(OUT+'/stress.pkl','wb') as f: pickle.dump(ex,f)
        ds=[design(0.00040,130,n=4,tau=0.05),design(0.00042,130,n=4,tau=0.05),design(0.00043,130,n=3,tau=0.05),design(0.00044,150,n=4,tau=0.05),design(0.00046,150,n=3,tau=0.05),design(0.00049,180,n=2,tau=0.05),design(0.00040,110,n=2,tau=0.05)]
        rs=run(ds,ex,stage)
        feasible=[(d,m) for d,m in rs if m['feasible']]
        if feasible:
            d,m=max(feasible,key=lambda x:x[1]['mean_tir'])
            api.save_design(d)
    elif stage=='broad':
        seeds=[int(x) for x in np.random.default_rng(20250719).integers(1,10000000,20)]
        ex=experiment(seeds)
        with open(OUT+'/broad.pkl','wb') as f: pickle.dump(ex,f)
        ds=[design(0.0004,110,n=2,tau=0.05),design(0.00042,130,n=3,tau=0.05),design(0.0004,130,n=4,tau=0.05),design(0.000385,100,n=2,tau=0.05)]
        rs=run(ds,ex,stage)
        feasible=[(d,m) for d,m in rs if m['feasible']]
        if feasible:
            d,m=max(feasible,key=lambda x:x[1]['mean_tir'])
            api.save_design(d)
    elif stage=='polish':
        with open(OUT+'/broad.pkl','rb') as f: ex=pickle.load(f)
        ds=[design(0.000405,110,n=2,tau=0.05),design(0.0004,110,n=2.5,tau=0.05),design(0.00041,120,n=2.5,tau=0.05)]
        run(ds,ex,stage)
    elif stage=='validate':
        d=design(0.000398,110,n=2.5,tau=0.05)
        api.save_design(d)
        seeds=[int(x) for x in np.random.default_rng(876125).integers(1,10000000,12)]
        ex=experiment(seeds)
        with open(OUT+'/stress.pkl','rb') as f: stress=pickle.load(f)
        ex.jobs+=stress.jobs
        m=evaluate(ex,d,steps=4); record(d,m,stage)
        if not m['feasible']:
            d=design(0.0004,110,n=2,tau=0.05)
            api.save_design(d)
        with open(OUT+'/validation.json','w') as f: json.dump(m,f,indent=2)
        worst=min(m['rows'],key=lambda r:r['metrics']['minimum'])
        print('WORST',json.dumps(worst),flush=True)
    elif stage=='native_check':
        from gri_bench.native import native_trace
        d=json.load(open(OUT+'/design.json'))
        ins=api.load_instance()
        ex=experiment([2363590])
        job=next(j for j in ex.jobs if j[0]=='child#001' and j[2]=='large_dinner')
        name,seed,variant,p,initial,meals=job
        tr,minutes=native_trace(name,meals,api.individual_design(d,ins['tdi'][name]),ins['patient_seed'])
        nm=api.glucose_metrics(tr,ins['warmup_minutes'],minutes)
        with open(OUT+'/native_check.json','w') as f: json.dump(nm,f,indent=2)
        print('NATIVE',json.dumps(nm),flush=True)
        with open(OUT+'/rationale.md','a') as f:
            f.write('\nNative dopri5 spot check of this lowest-glucose validation trajectory: '+json.dumps(nm)+'. This checks one trajectory, not the entire validation cohort.\n')
        api.validate_design(d,ins)
    elif stage=='audit':
        d=json.load(open(OUT+'/design.json'))
        api.validate_design(d,api.load_instance())
        with open(OUT+'/broad.pkl','rb') as f: ex=pickle.load(f)
        m=evaluate(ex,d,steps=1); record(d,m,'final_broad')
        with open(OUT+'/training.pkl','rb') as f: ex=pickle.load(f)
        t=evaluate(ex,d,steps=4); record(d,t,'final_training')
        with open(OUT+'/rationale.md','a') as f:
            f.write('\nExact submitted design on the twenty earlier fresh comparison seeds (180 trajectories, one-minute RK4): '+json.dumps({k:v for k,v in m.items() if k!='rows'})+'.\n')
            f.write('\nExact submitted design on the original training seed (nine trajectories, standard four-substep RK4): '+json.dumps({k:v for k,v in t.items() if k!='rows'})+'.\n')
