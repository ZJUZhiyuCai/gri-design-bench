"""Reproducible derivative-free search for the shared GRI coefficients.

Usage: OPENBLAS_NUM_THREADS=1 python search.py [--validate]
The search uses only the public training scenarios.  Safety is a hard filter;
unsafe candidates receive a smooth penalty to guide subsequent local samples.
--validate evaluates the saved design on additional, freshly generated meal
seeds.  No patient-specific coefficients or online control are used.
"""
import json, sys, numpy as np
from scipy.stats import qmc
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design
INSTANCE=load_instance()
BOUNDS=np.array([INSTANCE['bounds'][k] for k in PARAMETERS],float)
def design(x): return {'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
def unpack(d): return np.array([d['parameters'][k] for k in PARAMETERS])
def summary(m):
    return dict(tir=round(m['mean_tir'],4),feasible=m['feasible'],
                tbr70=round(m['max_trajectory_tbr70'],4),
                tbr54=round(m['max_trajectory_tbr54'],4),minimum=round(m['minimum_glucose'],3))
def merit(m):
    # Strongly prefer feasibility; smooth terms guide sampling away from failure.
    return m['mean_tir']-3*max(0,m['max_trajectory_tbr70']-4)-5*max(0,m['max_trajectory_tbr54']-1)-max(0,40-m['minimum_glucose'])
def main():
    ex=Experiment(INSTANCE); records=[]
    def trial(x):
        x=np.minimum(np.maximum(x,BOUNDS[:,0]),BOUNDS[:,1]); m=ex.evaluate(design(x))
        records.append((merit(m),m['feasible'],m['mean_tir'],x.copy(),summary(m)))
        return records[-1]
    # Physiologically useful subregion found by coarse one-factor probes.
    lo=np.array([0.00012,1.5,80.,0.5880395112623367,.05,.4])
    hi=np.array([0.00045,3.5,300.,20.,20.,4.])
    u=qmc.Sobol(6,scramble=True,seed=20261111).random_base2(6)[:56]
    xs=lo+(hi-lo)*u
    xs[:,0]=np.exp(np.log(lo[0])+u[:,0]*(np.log(hi[0])-np.log(lo[0])))
    xs[:,2]=np.exp(np.log(lo[2])+u[:,2]*(np.log(hi[2])-np.log(lo[2])))
    xs[:,3]=np.exp(np.log(lo[3])+u[:,3]*(np.log(hi[3])-np.log(lo[3])))
    xs[:,4]=np.exp(np.log(lo[4])+u[:,4]*(np.log(hi[4])-np.log(lo[4])))
    # Include the interpretable low-leak family explicitly.
    xs[:8,1]=1.5; xs[:8,5]=4.
    for x in xs: trial(x)
    rng=np.random.default_rng(20261111)
    scale=np.array([.000035,.35,30.,2.,3.,.4])
    for k in range(24):
        feasible=[r for r in records if r[1]]
        pool=feasible if feasible and rng.random()<.8 else records
        pool=sorted(pool,key=lambda r:r[0],reverse=True)[:8]
        base=pool[k%len(pool)][3]
        trial(base+rng.normal(size=6)*scale*(.65**(k//8)))
    feasible=[r for r in records if r[1]]
    best=max(feasible or records,key=lambda r:r[2] if r[1] else r[0])
    save_design(design(best[3])); print('BEST',best[3],best[4],flush=True)
    for r in sorted(feasible,key=lambda r:r[2],reverse=True)[:8]: print(r[3],r[4],flush=True)
    if '--validate' in sys.argv:
        vx=Experiment(INSTANCE,seeds=[1729,8675309,424242,987654321])
        print('FRESH',json.dumps(vx.evaluate(design(best[3])),indent=2),flush=True)
if __name__=='__main__': main()
