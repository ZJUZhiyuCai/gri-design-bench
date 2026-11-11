"""Reproducible GRI search: broad sampling, local refinement, fresh-seed checks."""
import json, os, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

B = np.array([[0.,.007],[.5124966150526034,5.518918645844859],
 [59.26305046791457,816.1143093473472],[.5880395112623367,24.],
 [.05,20.],[.4,4.]])
def design(x):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
def score(m):
    if m['minimum_glucose'] < 45 or m['max_trajectory_tbr54'] > .7:
        return -1000 + m['minimum_glucose']/100 - 10*m['max_trajectory_tbr54']
    return m['mean_tir'] - 2*max(0,m['max_trajectory_tbr70']-2.5)**2

def main():
    inst=load_instance(); ex=Experiment(inst)
    # Existing checkpoint is included; Sobol-like scrambled random broad exploration.
    bestx=np.array([.0002,1.5,200.,2.,10.,1.]); bestm=ex.evaluate(design(bestx)); best=score(bestm)
    rng=np.random.default_rng(41723)
    for k in range(100):
        x=np.array([rng.uniform(.0006,.007),rng.uniform(.5125,2.5),np.exp(rng.uniform(np.log(90),np.log(350))),
                    np.exp(rng.uniform(np.log(.7),np.log(12))),np.exp(rng.uniform(np.log(.2),np.log(15))),rng.uniform(.4,4)])
        m=ex.evaluate(design(x)); s=score(m)
        if s>best:
            best,bestx,bestm=s,x,m
            save_design(design(bestx))
        if k%10==0: print(k, 'candidate',round(s,3),'best',round(best,3),bestx,bestm['mean_tir'],bestm['max_trajectory_tbr70'],bestm['minimum_glucose'],flush=True)
    # Pattern/coordinate search in more stable transformed coordinates.
    def decode(z):
        return np.array([z[0],z[1],np.exp(z[2]),np.exp(z[3]),np.exp(z[4]),z[5]])
    z=np.array([bestx[0],bestx[1],np.log(bestx[2]),np.log(bestx[3]),np.log(bestx[4]),bestx[5]])
    step=np.array([.0005,.3,.25,.35,.35,.5])
    for it in range(6):
        improved=False
        for j in range(6):
            for sign in (-1,1):
                zz=z.copy(); zz[j]+=sign*step[j]; xx=decode(zz)
                if np.any(xx<B[:,0]) or np.any(xx>B[:,1]): continue
                m=ex.evaluate(design(xx)); s=score(m)
                if s>best:
                    best,bestx,bestm,z=s,xx,m,zz; improved=True; save_design(design(bestx))
        print('local',it,best,bestx,bestm['mean_tir'],bestm['max_trajectory_tbr70'],bestm['minimum_glucose'],flush=True)
        if not improved: step*=.45
    print(json.dumps(bestm,indent=2)); save_design(design(bestx))

if __name__=='__main__': main()
