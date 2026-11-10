import os, json, time
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, individual_design, glucose_metrics, summarize
from gri_bench.physiology import fast_trace
I=load_instance()
start=time.process_time()
E=Experiment(I)
def design(a,e,n=10,l=None,t=.05):
 return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=I['bounds']['relative_leak'][0] if l is None else float(l),ec50_mg_dl=float(e),hill_n=float(n),tau_min=float(t),theta_L=1.25)}
def evaluate(d,exp=E,steps=1):
 rows=[]
 for name,seed,var,p,x,meals in exp.jobs:
  tr=fast_trace(p,x,meals,individual_design(d,I['tdi'][name]),steps)
  rows.append(dict(patient=name,seed=seed,variant=var,metrics=glucose_metrics(tr)))
 return dict(**summarize(rows),rows=rows)
def score(m):
 return m['mean_tir']-30*max(0,m['max_trajectory_tbr70']-1)-50*max(0,m['max_trajectory_tbr54'])-5*max(0,55-m['minimum_glucose'])
if __name__=='__main__':
 results=[]
 for a in [.00022,.0003,.0004,.0005,.00065]:
  for e in [110,150,200]:
   d=design(a,e);m=evaluate(d);results.append((score(m),d,m))
   print(a,e,round(m['mean_tir'],2),round(m['max_trajectory_tbr70'],2),round(m['minimum_glucose'],1),flush=True)
 best=max(results,key=lambda z:z[0]);save_design(best[1])
 with open('/work/output/results.json','w') as f:json.dump(results,f)
 print('BEST',best,'CPU',time.process_time()-start,flush=True)
