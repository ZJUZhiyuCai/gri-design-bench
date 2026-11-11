"""Reproducible dev-04 search (audit code; not used by the verifier).
Uses the public cached RK4 API. Deterministic random seed and checkpoints.
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design
instance=load_instance()
experiment=Experiment(instance)
rng=np.random.default_rng(2026111101)
lo=np.array([0.,.5124966150526034,59.26305046791457,.5880395112623367,.05,.4])
hi=np.array([.007,5.518918645844859,816.1143093473472,24.,20.,1.25])
def make_design(x):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
def objective(m):
    # Lexicographic intent: reject unsafe candidates; smooth penalties guide exploration.
    return (m['mean_tir']-3*max(0,m['max_trajectory_tbr70']-3.5)
            -10*max(0,m['max_trajectory_tbr54']-.8)
            -2*max(0,50-m['minimum_glucose']))
best=(-np.inf,None)
def trial(x):
    global best
    x=np.clip(np.asarray(x,dtype=float),lo,hi)
    metrics=experiment.evaluate(make_design(x)); value=objective(metrics)
    if value>best[0]:
        best=(value,x.copy()); save_design(make_design(x))
        print('checkpoint',value,x.tolist(),metrics['mean_tir'],metrics['minimum_glucose'])
# Broad exploration, including the strong basal/weak-feedback family.
for _ in range(55):
    trial([10**rng.uniform(-3.8,-3.1),rng.uniform(.52,2.5),
           rng.uniform(90,220),10**rng.uniform(0,1),rng.uniform(1,15),rng.uniform(.65,1.25)])
# Alternative high-amplitude/high-switching-threshold family.
for a in [.0008,.0011]:
    for ec50 in [190.,240.,300.]:
        for n in [3.,6.]: trial([a,lo[1],ec50,n,8.,1.25])
# Refined incumbent found by coordinate and log-normal local searches.
trial([.00038840357100622955,.8974970117785624,156.9124602254804,
       1.4835170168738452,13.920134776044947,1.25])
# Independent fresh-seed robustness checks used during development:
# [6111005], [6111006], [6111007], [6111008], and [42,137].
print('final',best[0],make_design(best[1]))
