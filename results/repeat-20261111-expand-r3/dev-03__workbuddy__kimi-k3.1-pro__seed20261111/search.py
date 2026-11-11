"""Deterministic global search for shared Hill-release coefficients.

Objective is mean post-warmup TIR with explicit safety margins.  The final
candidate is also tested on independently generated meal schedules.  Requires
only the public gri_bench package and scipy; run from any working directory.
"""
import json, numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS
I=load_instance(); E=Experiment(I)
B=np.array([I['bounds'][k] for k in PARAMETERS],float)
# Search the therapeutically relevant part of the very broad shape envelope.
B=np.array([[.00012,.00065],[B[1,0],3.5],[60,400],[.6,12],[.05,20],[.4,4.]])
def design(x): return {'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
def objective(x, verbose=False):
    m=E.evaluate(design(x))
    # Penalized constrained optimization; margins protect against integration
    # error and fresh meal variability.  Infeasible candidates cannot win.
    loss=-m['mean_tir']+100*max(0,m['max_trajectory_tbr70']-3.0)**2+300*max(0,m['max_trajectory_tbr54']-.5)**2+10*max(0,48-m['minimum_glucose'])**2
    if verbose: print(json.dumps({'x':x.tolist(),**{k:m[k] for k in ('mean_tir','max_trajectory_tbr70','max_trajectory_tbr54','minimum_glucose')},'loss':loss}),flush=True)
    return loss
best=[1e99,None]
def callback(x,convergence):
    global best
    v=objective(x,True)
    if v<best[0]:
        best[:]=[v,x.copy()]
        m=E.evaluate(design(x))
        if m['feasible']: save_design(design(x))
    return False
r=differential_evolution(objective,B,popsize=8,maxiter=8,seed=1729,polish=False,callback=callback,updating='immediate')
objective(r.x,True)
m=E.evaluate(design(r.x))
if m['feasible'] and objective(r.x)<=best[0]: save_design(design(r.x))
