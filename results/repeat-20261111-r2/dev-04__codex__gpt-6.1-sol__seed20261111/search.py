"""Deterministic cohort-wide search. Uses public physiology only.
Run stages with: python /work/output/search.py initial|search|validate
Outputs are atomically checkpointed after each better feasible candidate.
"""
import os, json, sys, time
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, validate_design
from gri_bench.physiology import fast_trace
OUT=Path('/work/output')
def write(name,data):
    tmp=OUT/(name+'.tmp'); tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n'); tmp.replace(OUT/name)
def design(a,e,n=16.,leak=0.5124966150526034,tau=.05):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(leak),ec50_mg_dl=float(e),hill_n=float(n),tau_min=float(tau),theta_L=1.25)}
def evaluate(ex,d,substeps=2):
    rows=[]
    for name,seed,var,p,x,meals in ex.jobs:
        tr=fast_trace(p,x,meals,individual_design(d,ex.instance['tdi'][name]),substeps)
        rows.append(dict(patient=name,seed=seed,variant=var,metrics=glucose_metrics(tr)))
    return dict(summarize(rows),rows=rows)
def report(d,m):
    return {'design':d,'mean_tir':m['mean_tir'],'max_tbr70':m['max_trajectory_tbr70'],'max_tbr54':m['max_trajectory_tbr54'],'minimum':m['minimum_glucose'],'feasible':m['feasible']}
if __name__=='__main__':
    t=time.process_time(); inst=load_instance(); stage=sys.argv[1] if len(sys.argv)>1 else 'initial'
    if stage=='initial':
        ex=Experiment(inst)
        results=[]
        for a,e in [(0.0003,140),(0.0004,140),(0.0005,140),(0.0006,140),(0.0007,140)]:
            d=design(a,e); m=evaluate(ex,d); r=report(d,m); results.append(r); print(json.dumps(r),flush=True)
        write('initial_metrics.json',results)
    elif stage=='search':
        ex=Experiment(inst); results=[]; best=-1
        for a in [.00025,.000325,.0004,.000475,.00055,.000625]:
            for e in [180,220,260,300,360]:
                d=design(a,e,24); m=evaluate(ex,d); r=report(d,m); results.append(r)
                if m['feasible'] and m['minimum_glucose']>=65 and m['max_trajectory_tbr70']<=1 and m['mean_tir']>best:
                    best=m['mean_tir']; write('design.json',d); write('best_metrics.json',m)
                print(json.dumps(r),flush=True)
        write('search_metrics.json',results)
    elif stage=='refine':
        ex=Experiment(inst); results=[]; best=-1
        candidates=[design(a,e,n) for a in [.00040,.00045,.00050,.00055,.00060,.00065] for e in [65,90,115,140,165] for n in [3.,24.]]
        rng=np.random.default_rng(481)
        candidates += [design(rng.uniform(.00016,.00055),rng.uniform(65,190),rng.choice([2.,6.,12.,24.]),rng.uniform(.5125,2.5)) for i in range(80)]
        for d in candidates:
            m=evaluate(ex,d); r=report(d,m); results.append(r)
            if m['feasible'] and m['minimum_glucose']>=65 and m['max_trajectory_tbr70']<=1 and m['mean_tir']>best:
                best=m['mean_tir']; write('design.json',d); write('best_metrics.json',m)
        write('refine_metrics.json',results)
        for r in sorted(results,key=lambda r: r['mean_tir'] if r['feasible'] and r['minimum']>=60 else -1,reverse=True)[:16]: print(json.dumps(r),flush=True)
    elif stage=='validate':
        ex=Experiment(inst,seeds=[6111004,71231,89501,246813,971113])
        previous=json.loads((OUT/'refine_metrics.json').read_text())
        candidates=[r['design'] for r in sorted(previous,key=lambda r:r['mean_tir'] if r['feasible'] else -1,reverse=True)[:15]]
        candidates += [design(a,e,n) for a in [.00036,.00040,.00044,.00048,.00052] for e,n in [(59.26305046791457,.5880395112623367),(59.26305046791457,1.5),(65,3),(90,6),(110,12)]]
        candidates += [{'mode':'constant','parameters':{'theta_c':a,'theta_L':1.25}} for a in [.00048,.00052,.00056,.00060,.00064]]
        results=[]; best=-1
        for d in candidates:
            m=evaluate(ex,d); r=report(d,m); results.append(r)
            if m['feasible'] and m['minimum_glucose']>=62 and m['max_trajectory_tbr70']<=1 and m['mean_tir']>best:
                best=m['mean_tir']; write('design.json',d); write('validation_best_metrics.json',m)
        write('validation_metrics.json',results)
        for r in sorted(results,key=lambda r:r['mean_tir'] if r['feasible'] else -1,reverse=True)[:12]: print(json.dumps(r),flush=True)
    elif stage=='local':
        ex=Experiment(inst,seeds=[6111004,71231,89501,246813,971113]); results=[]
        current=json.loads((OUT/'design.json').read_text()); bm=evaluate(ex,current); best=bm['mean_tir']
        candidates=[design(a,e,n) for a in [.00038,.00039,.00040,.00041,.00042] for e in [59.26305046791457,65] for n in [2.,3.]]
        rng=np.random.default_rng(729)
        candidates += [design(rng.uniform(.00038,.00049),rng.uniform(59.26305046791457,100),rng.uniform(.5880395112623367,4.5)) for i in range(20)]
        for d in candidates:
            m=evaluate(ex,d); results.append(report(d,m))
            if m['feasible'] and m['minimum_glucose']>=70 and m['max_trajectory_tbr70']==0 and m['mean_tir']>best:
                best=m['mean_tir']; write('design.json',d); write('validation_best_metrics.json',m)
        write('local_metrics.json',results)
        for r in sorted(results,key=lambda r:r['mean_tir'] if r['feasible'] else -1,reverse=True)[:6]: print(json.dumps(r),flush=True)
    elif stage=='final':
        d=json.loads((OUT/'design.json').read_text()); validate_design(d,inst)
        seeds=[100003,100019,100043,100049,100057,100069,100103,100109,100129,100151,100153,100169,100183,100189,100193,100207,100213,100237,100267,100271]
        ex=Experiment(inst,seeds=seeds)
        m=evaluate(ex,d,substeps=4); write('final_fresh_metrics.json',m)
        training=evaluate(Experiment(inst),d,substeps=4); write('final_training_metrics.json',training)
        write('design.json',d)
        text=f"""# GRI static formulation for dev-04

## Submitted design
Responsive release with a single shared formulation for adult#004, adult#005 and adult#006. Parameters are theta_a={d['parameters']['theta_a']}, relative_leak={d['parameters']['relative_leak']}, EC50={d['parameters']['ec50_mg_dl']} mg/dL, Hill exponent={d['parameters']['hill_n']}, filter time={d['parameters']['tau_min']} minutes, and load=1.25 times native TDI. All parameters satisfy the supplied bounds. Release amplitude and reservoir are scaled only by the prescribed native TDI.

## Search and rationale
The finite three-day reservoir is an active constraint. Larger amplitudes exhausted the reservoir earlier and some caused hypoglycemia. Higher activation thresholds reduced TIR in the tested cohort. A low EC50 with a moderate Hill exponent gave the strongest observed balance of TIR and hypoglycemia margin. Minimum allowed relative leak and maximum reservoir load were selected; the shortest filter avoids additional delay. The formulation remains a fixed material response with no meal boluses or individual fitted coefficients.

Search used the public RK4 physiology at two substeps per minute, an amplitude/threshold sweep, a broader deterministic grid and random search, constant-rate comparators, five-seed scenario evaluation, and a local refinement. Candidates were checkpointed atomically. Selection required extra safety margin beyond the benchmark limits. All three meal variants and all three patients were included. This was a bounded heuristic search, without a claim of global optimality.

## Final checks
Final checks used four RK4 substeps per minute, the API default precision, with day one omitted from TIR/TBR but included in the glucose minimum.

* Training: 9 trajectories; mean TIR {training['mean_tir']:.6f}%; maximum trajectory TBR70 {training['max_trajectory_tbr70']:.6f}%; maximum TBR54 {training['max_trajectory_tbr54']:.6f}%; full-horizon minimum {training['minimum_glucose']:.6f} mg/dL.
* Additional seeds reserved until after parameter selection: {len(seeds)} seeds, {m['trajectories']} trajectories; mean TIR {m['mean_tir']:.6f}%; maximum trajectory TBR70 {m['max_trajectory_tbr70']:.6f}%; maximum TBR54 {m['max_trajectory_tbr54']:.6f}%; full-horizon minimum {m['minimum_glucose']:.6f} mg/dL.

The additional seed check passed the benchmark safety limits: {m['feasible']}. These observations do not guarantee safety on unseen seeds or agreement with the trusted native dopri5 verifier. Native dopri5 verification was not run within the compute budget. This submission is for the simulation benchmark, not a clinical recommendation.

## Reproduction
From an environment containing the public gri_bench package, run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py STAGE` for stages `initial`, `search`, `refine`, `validate`, `local`, then `final` in that order. The deterministic random seeds and all scenario seeds are embedded in search.py. Stage metrics are retained as JSON files, including per-trajectory final measurements. Only design.json determines the submitted formulation.
"""
        tmp=OUT/'rationale.md.tmp'; tmp.write_text(text); tmp.replace(OUT/'rationale.md')
        print(json.dumps({'design':d,'training':report(d,training),'fresh':report(d,m),'fresh_trajectories':m['trajectories']}),flush=True)
    print('CPU',time.process_time()-t,flush=True)
