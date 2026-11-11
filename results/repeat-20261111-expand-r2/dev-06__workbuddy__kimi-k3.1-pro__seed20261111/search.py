"""Reproducible robust search used for dev-06 (requires gri_bench).
The objective averages meal-seed TIR and heavily penalizes approaching safety
limits. Checkpoints are written atomically only when every validation scenario
is feasible. Bounds are taken directly from the instance.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,numpy as np
from gri_bench.api import load_instance,Experiment,save_design,PARAMETERS
I=load_instance()
EXPERIMENTS=[Experiment(I,seeds=[s]) for s in [6111006,7111007,8111008]]
START=np.array([.0003025891864204504,.686132772424978,177.2910721212784,
                2.4801395680318077,6.557072270643922,2.098259158213907])
LO=np.array([.00015,.5125,120,1.2,2,.4]); HI=np.array([.00055,1.5,400,4,20,3])
def assess(x,checkpoint=False):
 d={'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
 ms=[e.evaluate(d) for e in EXPERIMENTS]
 tir=float(np.mean([m['mean_tir'] for m in ms]))
 penalty=sum(30*max(0,m['max_trajectory_tbr70']-2)+100*max(0,m['max_trajectory_tbr54']-.5)+max(0,50-m['minimum_glucose']) for m in ms)
 if checkpoint and all(m['feasible'] for m in ms): save_design(d)
 return -tir+penalty,ms
if __name__=='__main__':
 rng=np.random.default_rng(123);scale=np.array([.00004,.08,25,.3,1.5,.25])
 candidates=[START]+[np.clip(START+rng.normal(size=6)*scale,LO,HI) for _ in range(100)]
 scored=[(assess(x)[0],x) for x in candidates]
 score,x=min(scored,key=lambda z:z[0]);score,ms=assess(x,True)
 print(x,score,[(m['mean_tir'],m['max_trajectory_tbr70'],m['minimum_glucose']) for m in ms])
