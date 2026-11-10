import os,time,json
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from gri_bench.api import load_instance,Experiment,PARAMETERS,individual_design,glucose_metrics,summarize,save_design
from gri_bench.physiology import fast_trace
I=load_instance(); start=time.process_time()
E=Experiment(I)
def design(a,e=180,n=8,leak=None,tau=.05):
 return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[a,I['bounds']['relative_leak'][0] if leak is None else leak,e,n,tau,4.]))}
def evaluate(d,jobs,substeps=1):
 rows=[]
 for name,seed,v,p,x,meals in jobs:
  t=fast_trace(p,x,meals,individual_design(d,I['tdi'][name]),substeps)
  rows.append({'patient':name,'seed':seed,'variant':v,'metrics':glucose_metrics(t)})
 return dict(summarize(rows),rows=rows)
def brief(m): return {k:v for k,v in m.items() if k!='rows'}
if __name__=='__main__':
 for a in [.0004,.0006,.0008,.001]:
  d=design(a);m=evaluate(d,E.jobs)
  print(a,brief(m), 'cpu',time.process_time()-start,flush=True)
 from scipy.optimize import differential_evolution
 V=Experiment(I,seeds=[6111001,740213,982451],variants=I['variants'])
 best=[-1,None,None]; history=[]
 def unpack(z): return design(z[0],z[1],z[2],z[3])
 def objective(z):
  d=unpack(z);m=evaluate(d,V.jobs)
  penalty=10*max(0,65-m['minimum_glucose'])+30*max(0,m['max_trajectory_tbr70']-.5)+50*max(0,m['max_trajectory_tbr54'])
  score=m['mean_tir']-penalty
  history.append((score,d,brief(m)))
  if score>best[0]:
   best[:]=[score,d,m];save_design(d)
  return -score
 res=differential_evolution(objective,[(.00045,.00125),(105,260),(2,24),(.5124966150526034,1.15)],popsize=6,maxiter=14,seed=715,polish=False,tol=.0001)
 history.sort(key=lambda r:r[0],reverse=True)
 with open('/work/output/search_results.json','w') as f: json.dump(history[:20],f,indent=2)
 print('BEST',best[1],brief(best[2]),'cpu',time.process_time()-start,flush=True)
 check=evaluate(best[1],V.jobs,4)
 print('RK4check',brief(check),flush=True)
 with open('/work/output/validation.json','w') as f:json.dump(check,f,indent=2)
 save_design(best[1])
