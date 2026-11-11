"""Deterministic shared formulation optimization and independent scenario checks.
Run with OPENBLAS_NUM_THREADS=1 PYTHONPATH=/opt python search.py --stage search
then --stage stress, boundary, final, and native (or --stage all). Uses unmodified public physiology, RK4 screening followed
by quarter-minute RK4 validation. Every checkpoint uses atomic replacement.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance,Experiment,PARAMETERS,individual_design,glucose_metrics,summarize,save_design
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')
INST=load_instance()
SEARCH_SEEDS=[6111005,1729,2741,3907,5101]
STRESS_SEEDS=[81001+104729*i for i in range(32)]
def design(x):
    a,e,n=x
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[float(a),1.5,float(e),float(n),0.05,4.]))}
def evaluate(ex,d,substeps=1):
    rows=[]
    for name,seed,v,p,x,m in ex.jobs:
        tr=fast_trace(p,x,m,individual_design(d,INST['tdi'][name]),substeps)
        rows.append({'patient':name,'seed':seed,'variant':v,'metrics':glucose_metrics(tr,INST['warmup_minutes'])})
    return dict(summarize(rows),rows=rows)
def compact(m): return {k:v for k,v in m.items() if k!='rows'}
def write(name,obj):
    p=OUT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(obj,indent=2)+'\n');t.replace(p)
def search():
    ex=Experiment(INST,seeds=SEARCH_SEEDS);history=[];best=-1
    def objective(x):
        nonlocal best
        d=design(x);m=evaluate(ex,d)
        # Reserve margin against unseen meals and numerical integration differences.
        penalty=8*max(0,m['max_trajectory_tbr70']-1)+12*max(0,m['max_trajectory_tbr54'])+1.5*max(0,60-m['minimum_glucose'])
        value=m['mean_tir']-penalty
        history.append({'design':d,'metrics':compact(m),'objective':value})
        if value>best:
            best=value;save_design(d);write('search_results.json',sorted(history,key=lambda r:-r['objective'])[:30])
        return -value
    differential_evolution(objective,[(.00020,.00040),(85,250),(2,24)],seed=505,popsize=7,maxiter=9,polish=False,tol=0,workers=1,x0=[.00030,160,16])
    write('search_results.json',sorted(history,key=lambda r:-r['objective'])[:60])
    print(json.dumps(sorted(history,key=lambda r:-r['objective'])[:5],indent=2),flush=True)
def stress():
    ex=Experiment(INST,seeds=STRESS_SEEDS)
    candidates=json.loads((OUT/'search_results.json').read_text())
    selected=[]
    for r in candidates:
        x=r['design']['parameters']
        if all(abs(x['theta_a']-q['parameters']['theta_a'])>0.000004 or abs(x['ec50_mg_dl']-q['parameters']['ec50_mg_dl'])>8 for q in selected):selected.append(r['design'])
        if len(selected)>=5:break
    results=[]
    for d in selected:
        m=evaluate(ex,d);results.append({'design':d,'metrics':compact(m),'rows':m['rows']})
        print(json.dumps({'design':d,'metrics':compact(m)}),flush=True)
        write('stress_results.json',results)
    safe=[r for r in results if r['metrics']['feasible']]
    if safe:
        best=max(safe,key=lambda r:r['metrics']['mean_tir']);save_design(best['design'])
# Additional deterministic boundary scan, used after the broad evolutionary pass.
def boundary_scan():
    ex=Experiment(INST,seeds=SEARCH_SEEDS[:3]);results=[]
    for e in [60.,70.,80.,90.]:
        for n in [4.,12.,24.]:
            lo,hi=.00022,.00032
            for _ in range(6):
                a=(lo+hi)/2;d=design([a,e,n]);m=evaluate(ex,d)
                if m['max_trajectory_tbr70']<=2.0 and m['max_trajectory_tbr54']==0 and m['minimum_glucose']>=60:
                    lo=a;results.append({'design':d,'metrics':compact(m)})
                else:hi=a
    results.sort(key=lambda r:-r['metrics']['mean_tir']);write('boundary_results.json',results)
    print(json.dumps(results[:5],indent=2),flush=True)

def final_compare():
    ex=Experiment(INST,seeds=STRESS_SEEDS)
    boundary=json.loads((OUT/'boundary_results.json').read_text())
    ds=[json.loads((OUT/'design.json').read_text()),boundary[0]['design'],boundary[1]['design']]
    results=[]
    for d in ds:
        m=evaluate(ex,d,4);r={'design':d,'metrics':compact(m),'rows':m['rows']};results.append(r)
        print(json.dumps({'design':d,'metrics':compact(m)}),flush=True)
        write('final_validation.json',results)
    # Margin limits selected using independent stress scenarios.
    eligible=[r for r in results if r['metrics']['feasible'] and r['metrics']['max_trajectory_tbr70']<=2 and r['metrics']['minimum_glucose']>=60]
    if eligible:
        peak=max(r['metrics']['mean_tir'] for r in eligible)
        near=[r for r in eligible if r['metrics']['mean_tir']>=peak-0.2]
        best=min(near,key=lambda r:(r['metrics']['max_trajectory_tbr70'],-r['metrics']['minimum_glucose']))
        save_design(best['design'])


def native_check():
    from gri_bench.native import native_trace
    from gri_bench.physiology import meal_schedule,patient_parameters
    d=json.loads((OUT/'design.json').read_text())
    results=json.loads((OUT/'final_validation.json').read_text())
    r=next(r for r in results if r['design']==d)
    w=min(r['rows'],key=lambda x:x['metrics']['minimum'])
    name=w['patient'];p,_=patient_parameters(name)
    meals=meal_schedule(w['seed'],3,w['variant'])*p.BW/INST['reference_weight_kg']
    tr,minute=native_trace(name,meals,individual_design(d,INST['tdi'][name]),INST['patient_seed'])
    report={'patient':name,'seed':w['seed'],'variant':w['variant'],'metrics':glucose_metrics(tr,1440,minute)}
    write('native_validation.json',report)
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--stage',choices=['search','stress','boundary','final','native','all'],default='all')
    args=ap.parse_args()
    actions={'search':search,'stress':stress,'boundary':boundary_scan,'final':final_compare,'native':native_check}
    for key,fn in actions.items():
        if args.stage in [key,'all']:fn()
