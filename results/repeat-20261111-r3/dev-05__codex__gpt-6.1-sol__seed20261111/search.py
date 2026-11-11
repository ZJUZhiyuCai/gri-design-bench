"""Deterministic cohort formulation search. Run stages with `python search.py probe|search|validate`.
Search uses one-minute RK4, validation uses the public quarter-minute RK4.
All safety checks include full-horizon minima; tuning uses only public meals.
"""
import json, sys, time
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, save_design, validate_design
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')
I=load_instance()
def design(a, ec=140., n=24., tau=.05, leak=1.5, load=4.):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(ec),hill_n=float(n),tau_min=float(tau),theta_L=float(load))}
def evaluate(ex,d,steps=1):
    validate_design(d,I)
    rows=[]
    for name,seed,var,p,x,meals in ex.jobs:
        tr=fast_trace(p,x,meals,individual_design(d,I['tdi'][name]),substeps=steps)
        rows.append(dict(patient=name,seed=seed,variant=var,metrics=glucose_metrics(tr,I['warmup_minutes'])))
    return dict(summarize(rows),rows=rows)
def log(d,m):
    with (OUT/'trials.jsonl').open('a') as f:f.write(json.dumps(dict(design=d,metrics=m))+'\n')
    print(json.dumps(dict(design=d,**{k:v for k,v in m.items() if k!='rows'})),flush=True)
def run_probe():
    ex=Experiment(I)
    start=time.process_time()
    for a in [.0002,.0003,.0004,.0005,.0006]:
        d=design(a); m=evaluate(ex,d);log(d,m)
    print('evaluation_cpu',time.process_time()-start,flush=True)
if __name__=='__main__':
    if sys.argv[-1]=='probe':run_probe()

def run_search():
    ex=Experiment(I)
    best=-1
    for ec in [95.,110.,125.,140.,160.,180.,210.]:
        for a in [.00024,.00026,.00028,.00030,.00032,.00034]:
            d=design(a,ec);m=evaluate(ex,d);log(d,m)
            if m['feasible'] and m['mean_tir']>best:
                best=m['mean_tir'];save_design(d)
    trials=[json.loads(s) for s in (OUT/'trials.jsonl').read_text().splitlines()]
    feasible=[r for r in trials if r['metrics']['feasible']]
    feasible.sort(key=lambda r:r['metrics']['mean_tir'],reverse=True)
    (OUT/'shortlist.json').write_text(json.dumps(feasible[:15],indent=2))
if __name__=='__main__' and sys.argv[-1]=='search':run_search()

VALIDATION_SEEDS=[6111005]+list(range(734120,734132))
def run_validate():
    ex=Experiment(I,seeds=VALIDATION_SEEDS)
    candidates=[(.000245,80.),(.00025,95.),(.00026,95.),(.00027,95.),(.00026,110.),(.00027,110.),(.00028,125.),(.00028,140.),(.00029,140.),(.00030,160.)]
    results=[]
    for a,ec in candidates:
        d=design(a,ec);m=evaluate(ex,d);log(d,m);results.append(dict(design=d,metrics=m))
    (OUT/'validation.json').write_text(json.dumps(results,indent=2))
    safe=[r for r in results if r['metrics']['feasible']]
    if safe:
        best=max(safe,key=lambda r:r['metrics']['mean_tir']);save_design(best['design'])
if __name__=='__main__' and sys.argv[-1]=='validate':run_validate()

def run_refine():
    ex=Experiment(I)
    results=[]
    for ec in [65.,75.,85.,95.]:
        for n in [4.,8.,16.,24.]:
            for a in [.00024,.00025,.00026,.00027]:
                d=design(a,ec,n);m=evaluate(ex,d)
                results.append(dict(design=d,metrics=m))
    with (OUT/'trials.jsonl').open('a') as f:
        for r in results:f.write(json.dumps(r)+'\n')
    safe=sorted([r for r in results if r['metrics']['feasible'] and r['metrics']['max_trajectory_tbr70']<2],key=lambda r:r['metrics']['mean_tir'],reverse=True)
    print('Training leaders',json.dumps([dict(design=r['design'],mean_tir=r['metrics']['mean_tir'],minimum=r['metrics']['minimum_glucose']) for r in safe[:15]]),flush=True)
    exv=Experiment(I,seeds=VALIDATION_SEEDS)
    shortlist=[]
    # Include the best of each slope and EC50, avoiding near-identical leaders.
    for n in [4.,8.,16.,24.]:
        group=[r for r in safe if r['design']['parameters']['hill_n']==n]
        if group:shortlist.append(group[0]['design'])
    for ec in [65.,75.,85.,95.]:
        group=[r for r in safe if r['design']['parameters']['ec50_mg_dl']==ec]
        if group and group[0]['design'] not in shortlist:shortlist.append(group[0]['design'])
    validated=[]
    for d in shortlist:
        m=evaluate(exv,d);log(d,m);validated.append(dict(design=d,metrics=m))
    (OUT/'refinement.json').write_text(json.dumps(validated,indent=2))
    previous=json.loads((OUT/'validation.json').read_text())
    safe=[r for r in validated+previous if r['metrics']['feasible']]
    best=max(safe,key=lambda r:r['metrics']['mean_tir']);save_design(best['design'])
if __name__=='__main__' and sys.argv[-1]=='refine':run_refine()

def run_stress():
    ex=Experiment(I)
    shaped=[]
    for n in [.5880395112623367,1.,2.,3.]:
        for ec in [59.26305046791457,80.,100.,125.]:
            for a in [.00026,.00028,.00030,.00032]:
                d=design(a,ec,n);m=evaluate(ex,d)
                shaped.append(dict(design=d,metrics=m))
    with (OUT/'trials.jsonl').open('a') as f:
        for r in shaped:f.write(json.dumps(r)+'\n')
    safe=sorted([r for r in shaped if r['metrics']['feasible'] and r['metrics']['max_trajectory_tbr70']<1],key=lambda r:r['metrics']['mean_tir'],reverse=True)
    candidates=[design(.00025,65.,8.),design(.000245,65.,8.),design(.00026,85.,24.)]
    for n in [.5880395112623367,1.,2.,3.]:
        group=[r for r in safe if r['design']['parameters']['hill_n']==n]
        if group:candidates.append(group[0]['design'])
    # Fresh scenario set, disjoint from every seed used for initial tuning.
    seeds=list(range(918200,918280))
    exv=Experiment(I,seeds=seeds)
    validated=[]
    for d in candidates:
        m=evaluate(exv,d);log(d,m);validated.append(dict(design=d,metrics=m))
    (OUT/'stress.json').write_text(json.dumps(validated,indent=2))
    safe=[r for r in validated if r['metrics']['feasible']]
    best=max(safe,key=lambda r:r['metrics']['mean_tir']);save_design(best['design'])
    worst=sorted(best['metrics']['rows'],key=lambda r:r['metrics']['minimum'])[:12]
    print('worst',json.dumps(worst),flush=True)
if __name__=='__main__' and sys.argv[-1]=='stress':run_stress()

def run_final_tune():
    # Tune near the best robust shape on public training plus the 12 development seeds.
    ex=Experiment(I,seeds=VALIDATION_SEEDS)
    results=[]
    for ec,n in [(59.26305046791457,8.),(65.,8.),(70.,8.),(75.,8.),(65.,12.)]:
        for a in [.000252,.000255,.000258]:
            d=design(a,ec,n);m=evaluate(ex,d);results.append(dict(design=d,metrics=m))
    with (OUT/'trials.jsonl').open('a') as f:
        for r in results:f.write(json.dumps(r)+'\n')
    safe=sorted([r for r in results if r['metrics']['feasible'] and r['metrics']['max_trajectory_tbr70']<=2.],key=lambda r:r['metrics']['mean_tir'],reverse=True)
    candidates=[r['design'] for r in safe[:3]]
    exv=Experiment(I,seeds=list(range(918200,918280)))
    validated=[]
    for d in candidates:
        m=evaluate(exv,d);log(d,m);validated.append(dict(design=d,metrics=m))
    (OUT/'final_tuning.json').write_text(json.dumps(validated,indent=2))
    prior=json.loads((OUT/'stress.json').read_text())
    safe=[r for r in validated+prior if r['metrics']['feasible'] and r['metrics']['max_trajectory_tbr70']<=2.]
    best=max(safe,key=lambda r:r['metrics']['mean_tir']);save_design(best['design'])
if __name__=='__main__' and sys.argv[-1]=='final_tune':run_final_tune()

def run_finish():
    d=json.loads((OUT/'design.json').read_text())
    # Quarter-minute RK4 checks the original tuning seeds and difficult fresh seeds.
    seeds=VALIDATION_SEEDS+[918208,918225,918230,918268,918274]
    ex=Experiment(I,seeds=seeds)
    m=evaluate(ex,d,steps=4)
    (OUT/'final_validation.json').write_text(json.dumps(dict(design=d,metrics=m,seeds=seeds,substeps=4),indent=2))
    print(json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
    save_design(d)
    p=d['parameters']
    text=f'''# Submitted formulation

Responsive release with shared coefficients: theta_a={p['theta_a']}, relative_leak={p['relative_leak']}, EC50={p['ec50_mg_dl']} mg/dL, Hill exponent={p['hill_n']}, filter time constant={p['tau_min']} min, reservoir multiplier={p['theta_L']}. Every coefficient satisfies the instance bounds. Amplitude and finite reservoir scale only by the provided native TDI; no patient-specific fitting or boluses are used.

## Design choice

The minimum allowed leak gives the strongest permitted modulation relative to basal release. A low EC50 and moderate Hill exponent preserve release through the usual glucose range while reducing release as glucose approaches the hypoglycemic range. The small filter time constant avoids extra response delay on top of the interstitial and subcutaneous physiological delays. The reservoir is deliberately ample: the maximum normalized flux is 0.000625 per minute, so even continuous maximum release for 4320 minutes would consume only 2.7 TDI, below the 4 TDI load.

## Search and evidence

The search varied amplitude, EC50, and Hill slope over the known cohort, always resetting native physiological initial states. Broad scans used one-minute RK4 for speed; the final check uses the public default quarter-minute RK4. All minima include warmup; TIR and TBR omit the first day. Candidate selection required each trajectory to pass the benchmark safety limits, with an additional 2% maximum TBR70 selection margin during the last comparison.

The selected design achieved 89.75434% mean TIR across 80 fresh seeds (918200 through 918279), all three challenge variants and all three patients: 720 trajectories. Maximum TBR70 and TBR54 were both 0%; full-horizon minimum glucose was 70.83123 mg/dL. An independent earlier 13-seed set (training seed plus 734120 through 734131) gave 89.79968% mean TIR, 0% TBR70, 0% TBR54, and minimum 70.87066 mg/dL. These fresh sets were subsequently used for selection and are not held-out guarantees.

Increasing amplitude from 0.000250 to 0.000252 raised the 80-seed mean TIR only to 89.95501%, but increased worst-trajectory TBR70 to 2.60417%. The lower amplitude was retained to preserve a useful safety margin against new meals and integrator differences.

Final quarter-minute RK4 check, covering {m['trajectories']} trajectories on the 13 earlier seeds and five difficult fresh seeds: mean TIR {m['mean_tir']:.6f}%; maximum TBR70 {m['max_trajectory_tbr70']:.6f}%; maximum TBR54 {m['max_trajectory_tbr54']:.6f}%; full-horizon minimum {m['minimum_glucose']:.6f} mg/dL. See final_validation.json for per-trajectory evidence.

Native dopri5 verification was not run within the compute budget. Training and fresh-seed observations cannot guarantee safety on the verifier's unseen meals. This is a simulation benchmark formulation, not a clinical recommendation.

## Reproduction

Run stages in order with OPENBLAS_NUM_THREADS=1: `python /work/output/search.py probe`, then `search`, `validate`, `refine`, `stress`, `final_tune`, and `finish`. The final selection uses the largest mean TIR among formulations passing the final 2% maximum-TBR70 selection margin on the 80-seed set. Atomic saves protect design checkpoints. Full results are retained in trials.jsonl, validation.json, refinement.json, stress.json, final_tuning.json, and final_validation.json.
'''
    temp=OUT/'rationale.tmp';temp.write_text(text);temp.replace(OUT/'rationale.md')
if __name__=='__main__' and sys.argv[-1]=='finish':run_finish()
