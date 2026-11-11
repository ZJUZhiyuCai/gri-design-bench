"""Deterministic shared-formulation search; run with PYTHONPATH=/opt.
Uses one-minute RK4 for screening, quarter-minute RK4 for final validation.
All candidates respect instance bounds. No simulator files are modified.
"""
import json, os, time
from pathlib import Path
import numpy as np
from gri_bench.api import (load_instance, Experiment, PARAMETERS, individual_design,
                           glucose_metrics, summarize, validate_design, save_design)
from gri_bench.physiology import fast_trace
OUT = Path('/work/output')
I = load_instance()
LEAK = I['bounds']['relative_leak'][0]

def design(a, ec, n=4., leak=LEAK, tau=2.):
    return {'mode':'responsive', 'parameters':dict(zip(PARAMETERS,[float(a),float(leak),float(ec),float(n),float(tau),4.]))}

def evaluate(e,d,substeps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in e.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,I['tdi'][name]),substeps=substeps)
        rows.append({'patient':name,'seed':int(seed),'variant':variant,'metrics':glucose_metrics(trace,I['warmup_minutes'])})
    return {**summarize(rows),'rows':rows}

def margin(m):
    return m['max_trajectory_tbr70'] <= 1.5 and m['max_trajectory_tbr54'] == 0. and m['minimum_glucose'] >= 58.

def record(name,obj):
    temp=OUT/(name+'.tmp'); temp.write_text(json.dumps(obj,indent=2)+'\n'); temp.replace(OUT/name)

def main():
    start=time.process_time()
    train=Experiment(I)
    candidates=[]
    for n in [4.]:
        for ec in np.linspace(80.,260.,10):
            for a in np.linspace(.00028,.00048,11):
                d=design(a,ec,n)
                m=evaluate(train,d)
                if margin(m):
                    candidates.append((m['mean_tir'],d,m))
    candidates.sort(key=lambda x:x[0],reverse=True)
    record('screen.json', [{'tir':s,'design':d,'metrics':{k:v for k,v in m.items() if k!='rows'}} for s,d,m in candidates[:100]])
    print('SCREEN',len(candidates), 'cpu',time.process_time()-start,flush=True)
    # Enforce diversity in shape to avoid testing adjacent amplitude grid points only.
    selected=[]; used=set()
    for s,d,m in candidates:
        p=d['parameters']; key=(p['hill_n'],p['ec50_mg_dl'])
        if key not in used:
            selected.append((s,d)); used.add(key)
        if len(selected)>=5: break
    robust=Experiment(I,seeds=[6111006,81001,81002,81003,81004,81005])
    results=[]
    for _,d in selected:
        # Reduce amplitude if necessary to retain a practical safety margin.
        for factor in [1.,.94,.88]:
            trial=json.loads(json.dumps(d)); trial['parameters']['theta_a']*=factor
            m=evaluate(robust,trial)
            if margin(m):
                results.append((m['mean_tir'],trial,m)); break
    results.sort(key=lambda x:x[0],reverse=True)
    record('robust.json',[{'design':d,'metrics':m} for _,d,m in results])
    if results:
        _,d,m=results[0]; save_design(d); record('selected_metrics.json',m)
        final=evaluate(robust,d,substeps=4)
        record('validation.json',final)
        print('FINAL',d,{k:v for k,v in final.items() if k!='rows'},flush=True)
        (OUT/'rationale.md').write_text('# Shared glucose-responsive formulation\n\nThe release curve uses the minimum permitted leak, Hill coefficient 4, and a two-minute filter. All coefficients are shared across the three known children; only native TDI scales amplitude and reservoir. The four-TDI reservoir avoids premature exhaustion.\n\nA deterministic grid screened 110 candidates on the provided meal seed. Five distinct curve shapes were then tested, with amplitude reductions when needed, on the training seed and five additional meal seeds, each with all three meal variants. Screening required worst-trajectory TBR70 at most 1.5%, no TBR54, and full-horizon glucose at least 58 mg/dL. These margins are stricter than benchmark limits. Selection maximized mean TIR among candidates meeting these margins.\n\nThe selected design was checked again with quarter-minute RK4 on these 54 trajectories. Results: '+json.dumps({k:v for k,v in final.items() if k!='rows'})+'\n\nThese are numerical simulation results. New meal seeds and the native dopri5 verifier can differ; finite validation does not establish heldout safety. This is not a clinical recommendation. Reproduce with OPENBLAS_NUM_THREADS=1 PYTHONPATH=/opt python /work/output/search.py.\n')
    print('ROBUST',[(round(s,3),d['parameters']) for s,d,m in results[:8]],'cpu',time.process_time()-start,flush=True)

if __name__=='__main__':main()
