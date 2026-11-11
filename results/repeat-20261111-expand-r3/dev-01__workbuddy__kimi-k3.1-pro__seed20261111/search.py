"""Reproducible derivative-free search for the public GRI benchmark.

Usage: python search.py [evaluations].  Uses only public training scenarios and
writes improved feasible checkpoints atomically.  Parameter scales are logarithmic
where appropriate; the objective prioritizes every hard safety constraint.
"""
import json, sys, time
from pathlib import Path
import numpy as np
from scipy.stats import qmc
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance=load_instance(); experiment=Experiment(instance)
bounds=np.array([instance['bounds'][k] for k in PARAMETERS],float)
logscale=np.array([True,False,True,True,True,False])
def decode(u):
    u=np.asarray(u); out=np.empty(6)
    for j in range(6):
        if logscale[j]: out[j]=np.exp(np.log(bounds[j,0]+1e-12)*(1-u[j])+np.log(bounds[j,1])*u[j])
        else: out[j]=bounds[j,0]*(1-u[j])+bounds[j,1]*u[j]
    out=np.maximum(bounds[:,0],np.minimum(bounds[:,1],out))
    return dict(zip(PARAMETERS,out))
def design(u): return {'mode':'responsive','parameters':decode(u)}
def score(m):
    # Smoothly rank unsafe points, then maximize TIR among feasible points.
    v70=max(0,m['max_trajectory_tbr70']-3.2)
    v54=max(0,m['max_trajectory_tbr54']-0.5)
    vmin=max(0,48-m['minimum_glucose'])/10
    return m['mean_tir']-300*(v70+v54+vmin)
best=(-1e99,None,None); history=[]
def trial(u):
    global best
    m=experiment.evaluate(design(u)); s=score(m)
    history.append({'u':list(map(float,u)),'score':s,'mean_tir':m['mean_tir'],'feasible':m['feasible'],'tbr70':m['max_trajectory_tbr70'],'tbr54':m['max_trajectory_tbr54'],'minimum':m['minimum_glucose']})
    if s>best[0]:
        best=(s,np.array(u),m); save_design(design(u))
        print('BEST',len(history),s,m['mean_tir'],m['feasible'],decode(u),flush=True)
    return s

def main(n=150):
    n=int(n); rng=np.random.default_rng(20261111)
    # Include a broad low-discrepancy design, then mutate the current elite set.
    initial=qmc.Sobol(6,scramble=True,seed=20261111).random_base2(6)[:min(n,64)]
    elites=[]
    for u in initial: trial(u)
    elites=sorted(history,key=lambda h:h['score'],reverse=True)[:12]
    while len(history)<n:
        h=elites[int(rng.integers(len(elites)))]; u=np.array(h['u'])
        if rng.random()<0.5:
            u2=np.array(elites[int(rng.integers(len(elites)))]['u'])
            u=u+rng.normal(0,.16,6)+.35*(u-u2)
        else: u=u+rng.normal(0,.10,6)
        trial(np.clip(u,0,1))
        if len(history)%8==0: elites=sorted(history,key=lambda h:h['score'],reverse=True)[:12]
    Path('/work/output/search_history.json').write_text(json.dumps(history,indent=2))
    print('FINAL',best[0],json.dumps(design(best[1])),json.dumps({k:v for k,v in best[2].items() if k!='rows'}))
if __name__=='__main__': main(int(sys.argv[1]) if len(sys.argv)>1 else 150)
