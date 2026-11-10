import os, json, time
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design, individual_design, glucose_metrics, summarize
from gri_bench.physiology import fast_trace
OUT='/work/output'
I=load_instance()
def design(a=.00055,e=150,n=8,leak=.5124966150526034,tau=.05,load=4.):
 return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[a,leak,e,n,tau,load]))}
def evaluate(ex,d,substeps=1):
 rows=[]
 for name,seed,variant,p,initial,meals in ex.jobs:
  tr=fast_trace(p,initial,meals,individual_design(d,I['tdi'][name]),substeps)
  rows.append({'patient':name,'seed':seed,'variant':variant,'metrics':glucose_metrics(tr)})
 return dict(summarize(rows),rows=rows)
def atomic(name,data):
 path=OUT+'/'+name
 with open(path+'.tmp','w') as f: json.dump(data,f,indent=2)
 os.replace(path+'.tmp',path)
if __name__=='__main__':
 import sys
 stage=sys.argv[1] if len(sys.argv)>1 else 'initial'
 if stage=='initial':
  save_design(design())
  ex=Experiment(I)
  history=[]
  for a,e,n in [(.0004,150,8),(.00055,150,8),(.0007,150,8),(.0007,190,12),(.00085,190,12)]:
   d=design(a,e,n); r=evaluate(ex,d)
   history.append({'design':d,'metrics':r})
   print(a,e,n,{k:v for k,v in r.items() if k!='rows'},flush=True)
  atomic('history.json',history)
 if stage=='search':
  start=time.process_time()
  ex=Experiment(I,seeds=[6111002,381725,928341])
  rng=np.random.default_rng(1047)
  hist=[]; pool=[]; best=-1
  # Lower leak maximizes the available change in rate with glucose.
  fixed=[(.00050,130,4),(.00055,130,4),(.00060,130,4),(.00055,110,3),(.0006,120,6),(.0006,140,6),(.00055,150,8),(.00050,150,8),(.00060,100,2),(.00050,100,2),(.00065,140,4),(.00055,120,2)]
  k=0
  while time.process_time()-start<15.5:
   if k<len(fixed): a,e,n=fixed[k]
   elif k%4==0:
    a=rng.uniform(.0004,.0007);e=rng.uniform(85,170);n=rng.uniform(1.2,10)
   else:
    parent=pool[rng.integers(min(5,len(pool)))][1]
    a=parent[0]*np.exp(rng.normal(0,.055));e=parent[1]+rng.normal(0,9);n=parent[2]*np.exp(rng.normal(0,.20))
   a=float(np.clip(a,.0003,.0008));e=float(np.clip(e,65,200));n=float(np.clip(n,.6,16))
   d=design(a,e,n);r=evaluate(ex,d)
   # Enforce margin against unseen meals. Prefer no low-glucose minutes.
   score=r['mean_tir']-3*max(0,73-r['minimum_glucose'])-5*r['max_trajectory_tbr70']-20*r['max_trajectory_tbr54']
   pool.append((score,(a,e,n)));pool.sort(reverse=True);pool=pool[:12]
   hist.append({'design':d,'metrics':r,'score':score})
   if r['minimum_glucose']>=73 and r['max_trajectory_tbr70']==0 and r['mean_tir']>best:
    best=r['mean_tir'];save_design(d);atomic('best_metrics.json',r)
    print('BEST',k,a,e,n,round(best,3),round(r['minimum_glucose'],3),flush=True)
   k+=1
  atomic('search_history.json',hist)
  print('evaluations',k,'CPU',time.process_time()-start,'top',pool[:3],flush=True)
 if stage=='validate':
  d=json.load(open(OUT+'/design.json'))
  ex=Experiment(I,seeds=[10203,90901,718111,30517])
  records=[]
  for factor in [1.,.98,.96,.94,.92,.90]:
   candidate=json.loads(json.dumps(d));candidate['parameters']['theta_a']*=factor
   r=evaluate(ex,candidate,4)
   records.append({'factor':factor,'design':candidate,'metrics':r})
   print('VALIDATION',factor,{k:v for k,v in r.items() if k!='rows'},flush=True)
   if r['minimum_glucose']>=75 and r['max_trajectory_tbr70']==0:
    save_design(candidate);break
  else:
   save_design(records[-1]['design'])
  atomic('validation.json',records)
  selected=json.load(open(OUT+'/design.json'))
  text='''# Shared responsive formulation\n\nThe submitted formulation uses the same six coefficients for all three adolescent profiles. Amplitude and finite reservoir load scale only with the provided native TDI. The minimum permitted relative leak provides the strongest available glucose dependence. A short filter time avoids adding substantial delay to the existing physiological insulin delay. The maximum permitted reservoir load reduces premature exhaustion.\n\nSearch used the public physiology with RK4 at one-minute steps, then validation used the API default quarter-minute steps. A seeded stochastic search varied amplitude, EC50 and Hill exponent on three meal seeds, each with all three challenges. Its objective penalized low glucose and retained only candidates with no time below 70 and full-horizon minima at least 73 mg/dL. The search log records every candidate. Validation then used four additional meal seeds, all three challenges and all three patients, reducing amplitude if needed to seek a 75 mg/dL minimum margin.\n\nSelected design:\n```json\n'''+json.dumps(selected,indent=2)+'\n```\n\nAdditional-seed validation results:\n```json\n'+json.dumps({k:v for k,v in records[-1]['metrics'].items() if k!='rows'},indent=2)+'''\n```\n\nThese are simulation estimates from public RK4 physiology, not independent native-dopri5 verification. No claim is made that training or validation safety guarantees heldout safety. Additional meals can produce different outcomes, and any heldout threshold violation makes the benchmark score zero.\n\nReproduction: set PYTHONPATH=/opt and run `python /work/output/search.py initial`, then `search`, then `validate`. Search uses random seed 1047 and a 15.5 CPU-second stopping budget, so the exact final iteration count depends on hardware; stored histories preserve the actual evaluated designs and metrics.\n'''
  with open(OUT+'/rationale.md','w') as f:f.write(text)
 if stage=='native_check':
  from gri_bench.native import native_trace
  from gri_bench.physiology import patient_parameters,meal_schedule
  d=json.load(open(OUT+'/design.json'))
  rows=json.load(open(OUT+'/validation.json'))[-1]['metrics']['rows']
  row=min(rows,key=lambda r:r['metrics']['minimum'])
  p,_=patient_parameters(row['patient'])
  meals=meal_schedule(row['seed'],I['days'],row['variant'])*p.BW/I['reference_weight_kg']
  tr,minutes=native_trace(row['patient'],meals,individual_design(d,I['tdi'][row['patient']]),I['patient_seed'])
  result=dict(patient=row['patient'],seed=row['seed'],variant=row['variant'],metrics=glucose_metrics(tr,I['warmup_minutes'],minutes))
  atomic('native_check.json',result)
  print(json.dumps(result),flush=True)
  with open(OUT+'/rationale.md','a') as f:
   f.write('\nThe validation trajectory with the lowest minimum was also checked with the native dopri5 solver:\n```json\n'+json.dumps(result,indent=2)+'\n```\nThis is a single native cross-check; the other reported validation trajectories use RK4.\n')
