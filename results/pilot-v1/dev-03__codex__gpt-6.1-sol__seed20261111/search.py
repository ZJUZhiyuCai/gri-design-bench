import os, json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, individual_design, glucose_metrics, summarize
from gri_bench.physiology import fast_trace
I=load_instance()
start=time.process_time()
E=Experiment(I)
def design(a,ec,n=12,tau=.05,leak=None):
 return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=I['bounds']['relative_leak'][0] if leak is None else float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=4.)}
def evaluate(d,ex=E,steps=1):
 rows=[]
 for name,seed,var,p,x,meals in ex.jobs:
  t=fast_trace(p,x,meals,individual_design(d,I['tdi'][name]),steps)
  rows.append(dict(patient=name,seed=seed,variant=var,metrics=glucose_metrics(t,I['warmup_minutes'])))
 return dict(**summarize(rows),rows=rows)
if __name__=='__main__':
 for a in [.0004,.00055,.0007,.00085]:
  d=design(a,150)
  r=evaluate(d)
  print(a,{k:v for k,v in r.items() if k!='rows'},'CPU',time.process_time()-start,flush=True)
 # Search fixed random sequence, retaining margins below the benchmark limits.
 rng=np.random.default_rng(309)
 candidates=[]
 best=-1
 for j in range(430):
  if j<350:
   d=design(rng.uniform(.00032,.00085),rng.uniform(95,255),rng.choice([2.,3.,4.,6.,8.,12.,18.,24.]),rng.choice([.05,2.,10.]))
  else:
   base=candidates[rng.integers(min(15,len(candidates)))][1]['parameters']
   d=design(np.clip(base['theta_a']*np.exp(rng.normal(0,.07)),.0002,.001),np.clip(base['ec50_mg_dl']+rng.normal(0,10),60,350),np.clip(base['hill_n']*np.exp(rng.normal(0,.2)),.6,24),.05)
  r=evaluate(d)
  if r['minimum_glucose']>=57 and r['max_trajectory_tbr70']<=1.5 and r['max_trajectory_tbr54']==0:
   candidates.append((r['mean_tir'],d,r));candidates.sort(key=lambda z:-z[0])
   if r['mean_tir']>best:
    best=r['mean_tir'];save_design(d)
 print('TRAIN BEST',json.dumps(candidates[:3]),'CPU',time.process_time()-start,flush=True)
 V=Experiment(I,seeds=[15437,234980,87241,394002,61672,900003])
 survivors=[]
 for score,d,r in candidates[:22]:
  vr=evaluate(d,V)
  # Require a heldout margin, including no severe low glucose.
  if vr['minimum_glucose']>=55 and vr['max_trajectory_tbr70']<=2 and vr['max_trajectory_tbr54']==0:
   survivors.append((vr['mean_tir'],d,vr,r))
 survivors.sort(key=lambda z:-z[0])
 print('VALID BEST',json.dumps([(s,d,{k:v for k,v in vr.items() if k!='rows'}) for s,d,vr,r in survivors[:5]]),'CPU',time.process_time()-start,flush=True)
 if survivors:
  score,d,vr,tr=survivors[0]
 else:
  d=design(.0004,150);tr=evaluate(d);vr=evaluate(d,V)
 save_design(d)
 # Full-resolution RK4 confirmation and a separate set of unseen seeds.
 W=Experiment(I,seeds=[104729,73019,424243,819001])
 wr=evaluate(d,W,4)
 full=evaluate(d,E,4)
 val=evaluate(d,V,4)
 report={'design':d,'training_full_resolution':full,'validation_full_resolution':val,'additional_validation':wr,'search_candidates':430,'cpu_seconds':time.process_time()-start}
 with open('/work/output/results.json','w') as f:json.dump(report,f,indent=2)
 print('FINAL',json.dumps({key:({k:v for k,v in value.items() if k!='rows'} if isinstance(value,dict) else value) for key,value in report.items()}),flush=True)
 with open('/work/output/rationale.md.tmp','w') as f:
  f.write('# Shared responsive formulation\n\nThe design uses the minimum permitted leak, with a Hill response to filtered interstitial glucose. All coefficients are shared across the three children. The reservoir load is four times native TDI.\n\nSearch used 430 reproducible random and local candidates on the supplied meal seed, screening for minimum glucose at least 57 mg/dL and TBR70 at most 1.5%. The 22 leading candidates were screened on six additional meal seeds with all three variants, requiring minimum glucose at least 55 mg/dL, TBR70 at most 2%, and zero TBR54. Selection maximized mean TIR among these candidates.\n\n')
  for label,m in [('Training',full),('Six-seed validation',val),('Four further seeds',wr)]:
   f.write(f"{label}, RK4 at 0.25-minute steps: {m['trajectories']} trajectories; mean TIR {m['mean_tir']:.3f}%; maximum trajectory TBR70 {m['max_trajectory_tbr70']:.3f}%; TBR54 {m['max_trajectory_tbr54']:.3f}%; full-horizon minimum {m['minimum_glucose']:.3f} mg/dL.\n\n")
  f.write('First-day glucose contributes to the minimum but not TIR/TBR. Validation uses fresh public meal seeds and both challenges; this does not establish safety for every unseen scenario. The trusted native dopri5 verifier may differ numerically from these RK4 checks. No individual coefficients, external insulin, boluses, or custom controller are used. search.py reproduces search and reports, and checkpoints design.json atomically.\n')
 os.replace('/work/output/rationale.md.tmp','/work/output/rationale.md')

def refine():
 rng=np.random.default_rng(88371)
 current=json.load(open('/work/output/design.json'))
 base=current['parameters']
 local=Experiment(I,seeds=[6111003,15437,234980,87241,394002,61672,900003])
 pool=[]
 for j in range(60):
  if j==0:d=current
  else:
   d=design(base['theta_a']*np.exp(rng.normal(.02,.055)),np.clip(base['ec50_mg_dl']+rng.normal(0,10),60,150),np.clip(base['hill_n']*np.exp(rng.normal(0,.35)),.6,24),.05)
  r=evaluate(d,local)
  if r['minimum_glucose']>=65 and r['max_trajectory_tbr70']<=1 and r['max_trajectory_tbr54']==0:
   pool.append((r['mean_tir'],d,r))
 pool.sort(key=lambda z:-z[0])
 stress=Experiment(I,seeds=[19331,563111,96721,77389,273841,664831,14791,581901,72019,871021,36931,473021])
 accepted=[]
 # Keep independent challenge margins and rank by combined mean TIR.
 for score,d,r in pool[:4]+[(0,current,evaluate(current,local))]:
  sr=evaluate(d,stress)
  print('REFINE',json.dumps(d),{k:v for k,v in sr.items() if k!='rows'},flush=True)
  if sr['minimum_glucose']>=60 and sr['max_trajectory_tbr70']<=1.5 and sr['max_trajectory_tbr54']==0:
   accepted.append(((r['mean_tir']*7+sr['mean_tir']*12)/19,d,r,sr))
 if accepted:
  _,d,lr,sr=max(accepted,key=lambda z:z[0]);save_design(d)
  # Recheck full resolution on all nineteen search/validation seeds.
  lr=evaluate(d,local,4);sr=evaluate(d,stress,4)
  record={'design':d,'local':lr,'stress':sr}
  with open('/work/output/refinement.json','w') as f:json.dump(record,f,indent=2)
  text='# Final shared formulation\n\nThe submitted responsive formulation is shared across child#001, child#002 and child#003. It uses the minimum permitted relative leak, a near-immediate filter, a smooth Hill response, and the maximum allowed finite reservoir (four times native TDI). All bounds are respected. No patient-specific coefficients or external insulin are used.\n\n'
  text+='Search: 430 random/local candidates on the training seed, validation of the leading 22 candidates on six additional seeds, then 60 nearby candidates screened jointly on those seven seeds. The local screen required minimum glucose >=65 mg/dL, TBR70 <=1%, and zero TBR54. Four leading candidates and the prior design were checked on twelve further seeds, requiring minimum >=60 mg/dL, TBR70 <=1.5%, and zero TBR54; selection maximized combined mean TIR. All three meal variants and all three patients were included. Fixed RNG seeds in search.py reproduce the process.\n\n'
  for label,r in [('Seven search/validation seeds',lr),('Twelve further seeds',sr)]:
   text+=f"{label}: {r['trajectories']} trajectories, mean TIR {r['mean_tir']:.3f}%, worst TBR70 {r['max_trajectory_tbr70']:.3f}%, worst TBR54 {r['max_trajectory_tbr54']:.3f}%, full-horizon minimum {r['minimum_glucose']:.3f} mg/dL.\n\n"
  text+='Final results use RK4 with 0.25-minute steps. Day one is omitted from TIR/TBR but included in the minimum. The final native dopri5 verifier was not run within the compute budget. Sampled scenario safety does not guarantee heldout safety. Details of final checks are in refinement.json. The three required submission files are design.json, search.py and rationale.md.\n'
  with open('/work/output/rationale.md.tmp','w') as f:f.write(text)
  os.replace('/work/output/rationale.md.tmp','/work/output/rationale.md')
  print(text,flush=True)
if __name__=='__main__':refine()
