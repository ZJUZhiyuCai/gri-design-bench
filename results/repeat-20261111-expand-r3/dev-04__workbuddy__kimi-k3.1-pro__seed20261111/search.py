"""Reproducible deterministic search for the dev-04 GRI formulation."""
import json, sys, numpy as np
from scipy.optimize import minimize
sys.path.insert(0, '/opt')
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance = load_instance()
experiment = Experiment(instance)
bounds = instance['bounds']

def design(x):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS, map(float,x)))}

def merit(m):
    # TIR with increasingly severe costs as a trajectory approaches safety limits.
    return (m['mean_tir'] - 30*max(0,m['max_trajectory_tbr70']-2.5)
            - 50*max(0,m['max_trajectory_tbr54']-.5)
            - 2*max(0,48-m['minimum_glucose']))

rng=np.random.default_rng(404)
records=[]
def trial(x):
    m=experiment.evaluate(design(x)); s=merit(m)
    records.append((s,m['mean_tir'],m['feasible'],x.tolist(),m))
    return s
# Broad log-scaled coverage; the load is sampled uniformly.
lo=np.array([bounds[k][0] for k in PARAMETERS]); hi=np.array([bounds[k][1] for k in PARAMETERS])
loglo=np.log(np.maximum(lo,[1e-5,1e-5,1e-5,1e-5,1e-5,1e-5])); loghi=np.log(hi)
for _ in range(65):
    x=np.exp(rng.uniform(loglo,loghi)); x[-1]=rng.uniform(lo[-1],hi[-1]); trial(x)
records.sort(key=lambda r:r[0],reverse=True)
# Bound-constrained local searches from the strongest diverse candidates.
for seed in records[:4]:
    start=np.array(seed[3]); scale=np.array([.001,1.,100.,2.,5.,.3])
    def obj(z):
        x=start+z*scale
        if np.any(x<lo) or np.any(x>hi): return 1e4+np.sum(np.maximum(lo-x,0)+np.maximum(x-hi,0))
        return -trial(x)
    minimize(obj,np.zeros(6),method='Nelder-Mead',options={'maxfev':16,'xatol':1e-3,'fatol':1e-3})
records.sort(key=lambda r:r[0],reverse=True)
best=records[0]
save_design(design(best[3]))
with open('/work/output/search_log.json','w') as f:
    json.dump(records,f)
print('evaluations',len(records),'best score/TIR/feasible',best[:3])
print(json.dumps(design(best[3])))
print({k:v for k,v in best[4].items() if k not in ('rows','trajectories')})
for r in best[4]['rows']: print(r['patient'],r['variant'],r['metrics'])
