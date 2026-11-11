"""Reproducible static-formulation search; uses only public gri_bench API."""
import json, time, os
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def design(x):
    a, leak, ec50, n, tau, load = x
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,
        [10**a,leak,ec50,n,tau,load]))}
def score(r):
    # Smooth penalty strongly prioritizes feasibility, then mean TIR.
    return r['mean_tir'] - 8*max(0,r['max_trajectory_tbr70']-2.5) - 20*max(0,r['max_trajectory_tbr54']-.5) - max(0,55-r['minimum_glucose'])
def main():
    rng=np.random.default_rng(2026111101); instance=load_instance(); exp=Experiment(instance)
    best=(-1e9,None,None); rows=[]; start=time.time()
    # Log-uniform global exploration. All coefficients remain cohort-shared.
    for k in range(1000):
        x=[rng.uniform(np.log10(8e-5),np.log10(2e-3)),rng.uniform(1.5,5.518918645844859),
           np.exp(rng.uniform(np.log(60),np.log(300))),np.exp(rng.uniform(np.log(.59),np.log(16))),
           np.exp(rng.uniform(np.log(.05),np.log(20))),rng.uniform(2.5,4)]
        d=design(x); r=exp.evaluate(d); s=score(r)
        rows.append((s,r['mean_tir'],r['max_trajectory_tbr70'],r['max_trajectory_tbr54'],r['minimum_glucose'],d))
        if s>best[0]:
            best=(s,d,r); save_design(d)
            print(k,'BEST',s,r['mean_tir'],r['max_trajectory_tbr70'],r['max_trajectory_tbr54'],r['minimum_glucose'],d,flush=True)
    rows.sort(key=lambda z:z[0],reverse=True)
    with open('/work/output/search_results.json','w') as f: json.dump(rows[:50],f)
    print('TOP');
    for z in rows[:15]: print(z,flush=True)
    print('elapsed',time.time()-start,'evaluations',exp.evaluations)
if __name__=='__main__': main()
