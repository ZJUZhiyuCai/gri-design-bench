"""Reproducible search for GRI dev-06: pattern search over responsive formulation.
Objective: mean TIR on post-warmup plasma glucose, heavy penalties for hypo excursions
(stricter than verifier limits) across training seed plus extra meal seeds."""
import json, numpy as np
from gri_bench.api import load_instance, Experiment, save_design

TRAIN_SEEDS=[6111006]; VAL_SEEDS=[6111006,20261101,424242]
B={'theta_a':None}
def row_score(m):
    return (m['tir'] - 100*max(0.,m['tbr54']-0.2) - 30*max(0.,m['tbr70']-2.5)
            - 10*max(0.,50.-m['minimum']))
def design_score(exp,mode,par):
    r=exp.evaluate({'mode':mode,'parameters':par})
    s=np.mean([row_score(x['metrics']) for x in r['rows']])
    worst=min(row_score(x['metrics']) for x in r['rows'])
    return s, worst, r['mean_tir'], r
def clip(p,b):
    return {k:float(min(max(v,b[k][0]),b[k][1])) for k,v in p.items()}
def main():
    inst=load_instance(); b=inst['bounds']
    expT=Experiment(inst,seeds=TRAIN_SEEDS)
    expV=Experiment(inst,seeds=VAL_SEEDS)
    best=(None,-1e9,None)
    grid=[(ta,lk,ec,n,tau) for ta in (3e-4,4e-4,5e-4,6e-4,8e-4)
          for lk in (0.5125,0.8,1.5) for ec in (100.,180.,260.)
          for n in (1.5,3.0) for tau in (15.0,)]
    for ta,lk,ec,n,tau in grid:
        p=dict(theta_a=ta,relative_leak=lk,ec50_mg_dl=ec,hill_n=n,tau_min=tau,theta_L=4.0)
        s,w,tir,_=design_score(expT,'responsive',p)
        if min(s,w)>best[1]: best=(p,min(s,w),'grid')
    print('grid best',best[1],best[0])
    # pattern search on validation seeds around grid best
    p=dict(best[0]); step=dict(theta_a=0.25,relative_leak=0.3,ec50_mg_dl=0.25,hill_n=0.4,tau_min=0.4,theta_L=0.0)
    cur=design_score(expV,'responsive',clip(p,b)); print('val start',cur[0],cur[1])
    for it in range(6):
        improved=False
        for k in ['theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min']:
            for f in (1+step[k],1/(1+step[k])):
                q=dict(p); q[k]*=f
                sc=design_score(expV,'responsive',clip(q,b))
                if min(sc[0],sc[1])>min(cur[0],cur[1])+1e-6 or (abs(min(sc[0],sc[1])-min(cur[0],cur[1]))<1e-9 and sc[0]>cur[0]):
                    p,q_=clip(q,b),q; cur=sc; improved=True
        if not improved:
            for k in step: step[k]*=0.5
            if max(step.values())<0.03: break
    print('val tuned',cur[0],cur[1],cur[2],p)
    fin=design_score(expV,'responsive',clip(p,b))
    save_design({'mode':'responsive','parameters':clip(p,b)})
    json.dump({'best':p,'score':fin[0],'worst_row':fin[1],'mean_tir':fin[2]},
              open('/work/output/search_results.json','w'),indent=1)
    for r in fin[3]['rows']: print(r['patient'],r['seed'],r['variant'],{k:round(v,2) for k,v in r['metrics'].items()})
if __name__=='__main__': main()
