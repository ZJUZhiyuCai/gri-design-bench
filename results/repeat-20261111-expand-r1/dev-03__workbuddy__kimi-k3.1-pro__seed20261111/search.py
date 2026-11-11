"""Reproducible search used for the dev-03 static GRI formulation.

Run from the benchmark container. Candidates are evaluated with the supplied
fast RK4 experiment. Search is first broad and then local; finalists are ranked
on three fresh meal seeds rather than selecting solely on the training seed.
No candidate-specific simulator modifications are used.
"""
import json, os
import numpy as np
from scipy.stats import qmc
from gri_bench.api import load_instance, Experiment

OUT = '/work/output/design.json'
NAMES = ['theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L']

def candidate(x, lo, hi):
    z = np.asarray(lo) + np.asarray(x)*(np.asarray(hi)-np.asarray(lo))
    return {'mode':'responsive', 'parameters':dict(zip(NAMES, map(float,z)))}

def objective(m):
    # Lexicographic intent: feasible first, then TIR. Smooth terms guide the
    # search away from severe violations while retaining near-boundary designs.
    return (m['mean_tir']
            - 100*max(0, m['max_trajectory_tbr70']-2)
            - 300*m['max_trajectory_tbr54']
            - max(0, 62-m['minimum_glucose']))

def atomic_save(d):
    with open(OUT+'.tmp','w') as f: json.dump(d,f,separators=(',',':'))
    os.replace(OUT+'.tmp',OUT)

def stage(exp, seed, count, lo, hi):
    records=[]
    for x in qmc.LatinHypercube(6,seed=seed).random(count):
        d=candidate(x,lo,hi); m=exp.evaluate(d)
        records.append((objective(m),m,d))
    return sorted(records,key=lambda r:r[0],reverse=True)

def main():
    ins=load_instance(); train=Experiment(ins)
    # Broad shape discovery. The zero-amplitude endpoint is excluded only in
    # exploratory sampling; all final parameters satisfy the instance bounds.
    broad=stage(train,88,56,
        [.00015,.65,100.,.8,2.,.5],[.0012,3.,400.,6.,20.,2.5])
    # Regions suggested by broad search, with fixed seeds for reproducibility.
    local=stage(train,991,35,
        [.00025,.8,170.,3.,5.,1.2],[.00045,1.5,260.,10.,20.,2.])
    refine=stage(train,1203,23,
        [.00023,1.,180.,2.5,4.,1.55],[.00034,1.55,230.,12.,16.,2.1])
    finalists=[r for r in broad[:4]+local[:4]+refine[:3]
               if r[1]['max_trajectory_tbr70'] <= 4
               and r[1]['max_trajectory_tbr54'] <= 1
               and r[1]['minimum_glucose'] >= 40]
    fresh=Experiment(ins,seeds=[7111003,8111003,9111003])
    validated=[]
    for _,_,d in finalists:
        m=fresh.evaluate(d)
        # Require a validation margin on TBR70, strict TBR54, and >=40 mg/dL.
        if m['max_trajectory_tbr70'] <= 3 and m['max_trajectory_tbr54'] == 0 \
                and m['minimum_glucose'] >= 40:
            validated.append((m['mean_tir'],d,m))
    validated.sort(key=lambda z:z[0],reverse=True)
    if validated:
        atomic_save(validated[0][1])
        print('selected',validated[0])

if __name__=='__main__': main()
