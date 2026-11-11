"""Reproducible multi-seed derivative-free search for cohort-shared GRI coefficients.
The verifier never executes this file. Checkpointing is atomic.
"""
import json, os, numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance, Experiment
P=['theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L']
BOUNDS=[(0.00003,0.007),(0.5124966150526034,5.518918645844859),(59.26305046791457,816.1143093473472),(0.5880395112623367,24.0),(0.05,20.0),(0.4,4.0)]
def design(x): return {'mode':'responsive','parameters':dict(zip(P,map(float,x)))}
def loss(m):
    return (-m['mean_tir'] + 2000*max(0,m['max_trajectory_tbr70']-1.5)
            + 4000*max(0,m['max_trajectory_tbr54']-.2)
            + 1000*max(0,65-m['minimum_glucose']))
def main():
    exp=Experiment(load_instance(),seeds=[6111002,7111002,8111002]); best=[1e99,None]
    def fun(x):
        m=exp.evaluate(design(x)); v=loss(m)
        if v<best[0]:
            best[:]=[v,x.copy()]; d=design(x)
            tmp='/work/output/design.tmp'
            with open(tmp,'w') as f: json.dump(d,f)
            os.replace(tmp,'/work/output/design.json')
            print(round(v,3),d,flush=True)
        return v
    x0=np.array([.0005750848856471615,.8273492990974423,306.313260608384,9.718448771475988,4.126538864088285,1.8528561619640584])
    differential_evolution(fun,BOUNDS,x0=x0,seed=20261112,popsize=4,maxiter=2,polish=False,tol=.01,updating='immediate')
    print('BEST',best)
if __name__=='__main__': main()
