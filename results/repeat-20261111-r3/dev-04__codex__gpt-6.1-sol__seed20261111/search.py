"""Reproduce the dev-04 search. Run with PYTHONPATH=/opt and one BLAS thread.
Search uses one-minute RK4; final selection is checked with quarter-minute RK4.
All parameters are shared, with amplitude/load scaled only by native TDI.
The optional extra checks recorded in rationale.md do not change selection.
"""
import json, time, os
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, individual_design, glucose_metrics, summarize
from gri_bench.physiology import fast_trace
OUT='/work/output'
def design(a=0.00025,leak=0.5124966150526034,ec=160,n=8,tau=5,load=1.25):
    return {'mode':'responsive','parameters':dict(zip(('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L'),[a,leak,ec,n,tau,load]))}
def evaluate(exp,d,substeps=1):
    rows=[]
    for name,seed,var,p,initial,meals in exp.jobs:
        tr=fast_trace(p,initial,meals,individual_design(d,exp.instance['tdi'][name]),substeps)
        rows.append({'patient':name,'seed':seed,'variant':var,'metrics':glucose_metrics(tr), 'remaining':float(tr[-1,3])})
    return dict(summarize(rows),rows=rows)
def checkpoint(d,m,label):
    save_design(d)
    with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':label,'design':d,'metrics':m})+'\n')

def shape_sweep():
    ins=load_instance(); exp=Experiment(ins)
    candidates=[]
    for a in [0.00045,0.0006,0.0008,0.001]:
        for ec in [120,180,240,320]:
            candidates.append(design(a=a,ec=ec,n=24,tau=0.05))
    for a in [0.00045,0.0006,0.0008]:
        for n in [2,6]:
            candidates.append(design(a=a,ec=180,n=n,tau=0.05))
    records=[]
    for i,d in enumerate(candidates):
        m=evaluate(exp,d); records.append((d,m))
        with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'shape sweep','design':d,'metrics':m})+'\n')
        print(i,d['parameters'],{k:v for k,v in m.items() if k!='rows'},flush=True)
    safe=[(d,m) for d,m in records if m['feasible'] and m['minimum_glucose']>=65 and m['max_trajectory_tbr70']<1]
    d,m=max(safe,key=lambda r:r[1]['mean_tir']);checkpoint(d,m,'provisional best')


def fresh_comparison():
    ins=load_instance()
    exp=Experiment(ins,seeds=[812031,49321,6111005])
    cs=[design(a=.001,ec=320,n=24,tau=.05),design(a=.001,ec=240,n=24,tau=.05),design(a=.00045,ec=120,n=24,tau=.05),design(a=.0006,ec=180,n=2,tau=.05)]
    cs += [{'mode':'constant','parameters':{'theta_c':a,'theta_L':1.25}} for a in [.0004,.0005,.0006,.0007]]
    for d in cs:
     m=evaluate(exp,d)
     with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'fresh validation','design':d,'metrics':m})+'\n')
     print(d,{k:v for k,v in m.items() if k!='rows'},flush=True)


def optimization():
    ins=load_instance();exp=Experiment(ins,seeds=[6111004,812031])
    rng=np.random.default_rng(2026111101)
    cs=[]
    for a in [.00038,.00042,.00046,.0005,.00054]:
     for ec in [75,100,130,160]:cs.append(design(a=a,ec=ec,n=24,tau=.05))
    for _ in range(28):
     cs.append(design(a=rng.uniform(.00038,.00078),ec=rng.uniform(65,230),n=np.exp(rng.uniform(np.log(.6),np.log(24))),tau=.05))
    for _ in range(12):
     cs.append(design(a=rng.uniform(.0007,.00125),ec=rng.uniform(200,500),n=rng.uniform(4,24),tau=.05))
    best=-1
    for i,d in enumerate(cs):
     m=evaluate(exp,d)
     with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'two-seed optimization','design':d,'metrics':m})+'\n')
     if m['minimum_glucose']>=70 and m['max_trajectory_tbr70']==0 and m['mean_tir']>best:
      best=m['mean_tir'];checkpoint(d,m,'two-seed best')
      print(i,d,{k:v for k,v in m.items() if k!='rows'},flush=True)


def validation():
    ins=load_instance()
    records=[json.loads(s) for s in open(OUT+'/results.jsonl')]
    valid=[r for r in records if r['label']=='two-seed optimization' and r['metrics']['minimum_glucose']>=75 and r['metrics']['max_trajectory_tbr70']==0]
    valid.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    cs=[r['design'] for r in valid[:10]]
    cs += [{'mode':'constant','parameters':{'theta_c':a,'theta_L':1.25}} for a in [.00056,.00058,.0006]]
    seeds=[49321,6111005,198713,77801,291846,532101,90124,172305,421876,653219,811201,959203]
    exp=Experiment(ins,seeds=seeds)
    best=-1
    for i,d in enumerate(cs):
     m=evaluate(exp,d)
     with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'12-seed validation','design':d,'metrics':m})+'\n')
     print(i,d,{k:v for k,v in m.items() if k!='rows'},flush=True)
     if m['minimum_glucose']>=65 and m['max_trajectory_tbr70']<=1 and m['max_trajectory_tbr54']==0 and m['mean_tir']>best:
      best=m['mean_tir'];checkpoint(d,m,'validated best')


def local_refinement():
    ins=load_instance(); exp=Experiment(ins,seeds=[6111004,812031,49321,6111005,198713,77801])
    cs=[]
    for a in [.00038,.000395,.00041,.000425,.00044]:
     for ec in [65,80,95,110]:cs.append(design(a=a,ec=ec,n=24,tau=.05))
    for a in [.00103,.00108,.00113,.00118]:
     for ec in [300,340,380]:cs.append(design(a=a,ec=ec,n=14,tau=.05))
    for a in [.0004,.00042,.00044]:
     for n in [4,10]:cs.append(design(a=a,ec=85,n=n,tau=.05))
    for i,d in enumerate(cs):
     m=evaluate(exp,d)
     with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'six-seed refinement','design':d,'metrics':m})+'\n')
     if m['minimum_glucose']>=70 and m['max_trajectory_tbr70']==0:
      print(i,d['parameters'],round(m['mean_tir'],3),round(m['minimum_glucose'],2),flush=True)


def final_validation():
    ins=load_instance()
    seeds=np.random.default_rng(9041703).integers(10000,10000000,size=24).tolist()
    exp=Experiment(ins,seeds=seeds)
    cs=[design(a=.000395,ec=65,n=24,tau=.05),design(a=.000395,ec=80,n=24,tau=.05),design(a=.00113,ec=340,n=14,tau=.05),design(a=.00113,ec=380,n=14,tau=.05),design(a=.0010747392756051159,ec=337.9722340865593,n=13.851352491857226,tau=.05),{'mode':'constant','parameters':{'theta_c':.0006,'theta_L':1.25}}]
    records=[]
    for d in cs:
     m=evaluate(exp,d)
     records.append((d,m))
     with open(OUT+'/results.jsonl','a') as f:f.write(json.dumps({'label':'24-new-seed validation','design':d,'metrics':m})+'\n')
     print(d,{k:v for k,v in m.items() if k!='rows'},flush=True)
    safe=[r for r in records if r[1]['minimum_glucose']>=65 and r[1]['max_trajectory_tbr70']<=1 and r[1]['max_trajectory_tbr54']==0]
    d,m=max(safe,key=lambda r:r[1]['mean_tir'])
    checkpoint(d,m,'selected 24-seed best')
    m=evaluate(exp,d,substeps=4)
    checkpoint(d,m,'final quarter-minute RK4')
    open(OUT+'/validation.json','w').write(json.dumps({'seeds':seeds,'design':d,'metrics':m},indent=2))
    print('FINAL',d,{k:v for k,v in m.items() if k!='rows'},flush=True)


if __name__ == "__main__":
    os.makedirs(OUT,exist_ok=True)
    open(OUT+"/results.jsonl","w").close()
    shape_sweep()
    fresh_comparison()
    optimization()
    validation()
    local_refinement()
    final_validation()
