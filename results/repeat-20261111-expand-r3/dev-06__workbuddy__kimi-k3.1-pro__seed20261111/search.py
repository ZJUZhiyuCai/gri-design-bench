"""Reproducible deterministic global/local search for GRI dev-06.

Full audit workflow (fixed seeds and ordering):
  python search.py       # stratified training global search + local search
  python refine.py       # local search on three scenario seeds
  python validate.py     # final local search on five scenario seeds

All stages use only public gri_bench APIs, fixed RNG seeds, and deterministic
candidate ordering. Every improved incumbent is atomically checkpointed with
save_design. The trusted verifier never executes these search files.
"""
import json, numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS
LO=np.array([.00032,.5124966150526034,180.,.5880395112623367,2.,.65])
HI=np.array([.00052,1.4,470.,3.5,20.,1.6])
def design(x): return {'mode':'responsive','parameters':dict(zip(PARAMETERS,map(float,x)))}
def score(m):
    # Feasibility dominates, then training TIR. Small margins discourage boundary designs.
    return (m['mean_tir'] - 12*max(0,m['max_trajectory_tbr70']-3.5)
            - 35*max(0,m['max_trajectory_tbr54']-.7)
            - 1.5*max(0,45-m['minimum_glucose']))
def main():
    ex=Experiment(load_instance()); rng=np.random.default_rng(20261106)
    # Stratified random global search, followed by shrinking coordinate-free local search.
    u=(np.arange(76)[:,None]+rng.random((76,6)))/76
    for j in range(6): rng.shuffle(u[:,j])
    xs=LO+(HI-LO)*u; best=(-1e9,None,None)
    for stage in range(2):
        for x in xs:
            d=design(x); m=ex.evaluate(d); s=score(m)
            if s>best[0]:
                best=(s,d,m); save_design(d)
                print('BEST',stage,round(s,3),d,{k:round(v,4) for k,v in m.items() if k!='rows'},flush=True)
        center=np.array([best[1]['parameters'][k] for k in PARAMETERS])
        scale=(HI-LO)*(.12/(stage+1))
        xs=np.clip(center+rng.normal(size=(24,6))*scale,LO,HI)
    print('FINAL',best,flush=True)
if __name__=='__main__': main()
