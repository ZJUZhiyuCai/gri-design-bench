"""Deterministic shared-cohort search and validation for the GRI benchmark.
Run stages in order: python search.py coarse; python search.py refine; python search.py validate.
The screening integrator uses one RK4 step/minute; validation uses four.
"""
import os, json, time, sys
import numpy as np
from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize, save_design, validate_design
from gri_bench.physiology import fast_trace
ROOT='/work/output/'
instance=load_instance()
def design(a,e,n=8.,leak=None,tau=.05):
    return {'mode':'responsive','parameters':dict(theta_a=float(a),relative_leak=float(instance['bounds']['relative_leak'][0] if leak is None else leak),ec50_mg_dl=float(e),hill_n=float(n),tau_min=float(tau),theta_L=4.)}
def evaluate(ex,d,steps=1):
    rows=[]
    for name,seed,variant,p,initial,meals in ex.jobs:
        trace=fast_trace(p,initial,meals,individual_design(d,instance['tdi'][name]),substeps=steps)
        rows.append(dict(patient=name,seed=seed,variant=variant,metrics=glucose_metrics(trace)))
    return dict(**summarize(rows),rows=rows)
def rank(m):
    # A safety buffer is required before optimizing TIR.
    penalty=10*max(0,m['max_trajectory_tbr70']-1.)+20*max(0,m['max_trajectory_tbr54'])+2*max(0,60-m['minimum_glucose'])
    return m['mean_tir']-penalty

def record(results,d,m):
    results.append(dict(design=d,metrics=m,score=rank(m)))
    results.sort(key=lambda r:r['score'],reverse=True)
    tmp=ROOT+'results.tmp'
    with open(tmp,'w') as f: json.dump(results,f,indent=2)
    os.replace(tmp,ROOT+'results.json')
    if results[0]['design']==d:
        save_design(d)
        print(json.dumps({'parameters':d['parameters'],**{k:v for k,v in m.items() if k!='rows'},'score':rank(m)}),flush=True)

if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else 'coarse'
    if stage=='coarse':
        ex=Experiment(instance)
        results=[]
        start=time.process_time()
        for a in [.0004,.0006,.0008,.0010,.0012]:
            for e in [110.,150.,200.,260.]:
                d=design(a,e)
                m=evaluate(ex,d)
                record(results,d,m)
                if time.process_time()-start>9: break
            if time.process_time()-start>9: break
        print('CPU',time.process_time()-start,'candidates',len(results),flush=True)
    elif stage=='refine':
        start=time.process_time()
        results=json.load(open(ROOT+'results.json'))
        ex=Experiment(instance)
        candidates=[design(a,e,n) for a,e,n in [
            (.0006,150,4),(.0006,150,12),(.0006,150,24),
            (.00065,160,12),(.00065,160,24),(.00065,150,24),
            (.0007,170,24),(.0007,160,24),(.0006,140,24),
            (.00065,155,16),(.0007,180,12),(.0006,160,16)]]
        for d in candidates:
            record(results,d,evaluate(ex,d))
            if time.process_time()-start>5.4:break
        # Fresh scenarios are separate from the training seed; retain both outcomes.
        fresh=Experiment(instance,seeds=[772031,924107])
        checked=[]
        for r in results[:3]:
            m=evaluate(fresh,r['design'])
            checked.append(dict(design=r['design'],metrics=m,training=r['metrics'],score=rank(m)))
            print('FRESH',json.dumps({k:v for k,v in checked[-1].items() if k not in ['metrics','training']}),json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
        checked.sort(key=lambda r:r['score'],reverse=True)
        with open(ROOT+'fresh_results.json','w') as f:json.dump(checked,f,indent=2)
        winner=checked[0]
        save_design(winner['design'])
        # Higher accuracy validation of the selected design on training + new seeds.
        validation=Experiment(instance,seeds=[6111001,772031,924107])
        m=evaluate(validation,winner['design'],steps=4)
        with open(ROOT+'validation.json','w') as f:json.dump(m,f,indent=2)
        if not m['feasible']:
            # A lower amplitude is the conservative fallback if refinement is unsafe.
            d=winner['design'];d['parameters']['theta_a']*=.95
            save_design(d)
            m=evaluate(validation,d,steps=4)
            with open(ROOT+'validation.json','w') as f:json.dump(m,f,indent=2)
        else:d=winner['design']
        validate_design(d,instance)
        text='''# Shared glucose-responsive formulation

The final design uses one common parameter set for adult#001–003, with amplitude and reservoir scaled only by native TDI. The reservoir is set to the maximum permitted 4×TDI to avoid premature exhaustion. The low permitted leak limits glucose-independent delivery, while the Hill response increases delivery at higher glucose. Filtering is set to its minimum permitted time because additional delay compounds subcutaneous insulin action delay.

Search used a deterministic amplitude/EC50 sweep followed by response-steepness refinement, screening with RK4 at one-minute steps. Candidate ranking penalized any TBR70 above 1%, any TBR54, and minimum glucose below 60 mg/dL. The three highest-ranked training designs were compared on two separate fresh meal seeds (772031 and 924107), including ordinary, missed-lunch, and large-dinner variants for every patient. Selection used the fresh-seed ranking. This small sample does not guarantee safety on the verifier's unseen seeds.

The selected candidate was then checked with the public reference fast integrator at four RK4 substeps per minute on all three seeds (27 trajectories). Reported TIR/TBR omit day one; minimum glucose covers all three days. The independent verifier uses native dopri5, so these are numerical validation estimates, not verifier results.

'''
        text+='Final parameters:\n```json\n'+json.dumps(d,indent=2)+'\n```\n\nValidation aggregate:\n```json\n'+json.dumps({k:v for k,v in m.items() if k!='rows'},indent=2)+'\n```\n\nFull per-trajectory evidence is in validation.json. Reproduce with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py coarse`, followed by `OPENBLAS_NUM_THREADS=1 python /work/output/search.py refine`. The additional JSON files are audit evidence; only design.json specifies the formulation. This is a simulation benchmark, not a clinical recommendation.\n'
        with open(ROOT+'rationale.tmp','w') as f:f.write(text)
        os.replace(ROOT+'rationale.tmp',ROOT+'rationale.md')
        print('FINAL',json.dumps(d),json.dumps({k:v for k,v in m.items() if k!='rows'}),'CPU',time.process_time()-start,flush=True)
    elif stage=='stress':
        with open(ROOT+'design.json') as f:d=json.load(f)
        seeds=[18,19,77,13579,24680,98765,202603,202611]
        ex=Experiment(instance,seeds=seeds)
        m=evaluate(ex,d,steps=4)
        with open(ROOT+'stress_validation.tmp','w') as f:json.dump(dict(seeds=seeds,design=d,**m),f,indent=2)
        os.replace(ROOT+'stress_validation.tmp',ROOT+'stress_validation.json')
        print('STRESS',json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
        # When stress testing finds a violation, reduce common amplitude and recheck.
        if not m['feasible']:
            d['parameters']['theta_a']*=.95
            m=evaluate(ex,d,steps=4)
            save_design(d)
            with open(ROOT+'stress_validation.json','w') as f:json.dump(dict(seeds=seeds,design=d,**m),f,indent=2)
        with open(ROOT+'rationale.md','a') as f:
            f.write('\nAdditional stress validation used eight further fresh meal seeds '+str(seeds)+' and all three variants and patients (72 trajectories), using four RK4 substeps per minute. Aggregate results:\n```json\n'+json.dumps({k:v for k,v in m.items() if k!='rows'},indent=2)+'\n```\nThese scenarios were checked after selection. They remain a finite sample and do not establish unseen-scenario or native-integrator safety. Reproduce this additional stage with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py stress`. Full rows are in stress_validation.json.\n')
        assert all(os.path.isfile(ROOT+file) and os.path.getsize(ROOT+file)>0 for file in ['design.json','search.py','rationale.md'])
        validate_design(d,instance)
    elif stage=='polish':
        seeds=[6111001,772031,924107,18,19,77,13579,24680,98765,202603,202611]
        ex=Experiment(instance,seeds=seeds)
        with open(ROOT+'design.json') as f:baseline=json.load(f)
        candidates=[baseline]+[design(a,e,n) for a,e,n in [(.00061,150,4),(.00062,150,4),(.00063,155,4),(.00064,160,4),(.00063,155,3),(.00064,160,6)]]
        checked=[]
        for d in candidates:
            m=evaluate(ex,d)
            # Reserve margin against unseen meals: no observed TBR and minimum >=68.
            score=m['mean_tir']-20*m['max_trajectory_tbr70']-10*max(0,68-m['minimum_glucose'])
            checked.append(dict(design=d,metrics=m,score=score))
            print('POLISH',json.dumps(d['parameters']),json.dumps({k:v for k,v in m.items() if k!='rows'}),'score',score,flush=True)
        checked.sort(key=lambda r:r['score'],reverse=True)
        d=checked[0]['design']
        m=evaluate(ex,d,steps=4)
        if m['feasible']:
            save_design(d)
            with open(ROOT+'final_validation.json','w') as f:json.dump(dict(seeds=seeds,design=d,**m),f,indent=2)
            with open(ROOT+'polish_results.json','w') as f:json.dump(checked,f,indent=2)
            # Keep rationale consistent with final design if the amplitude changed.
            with open(ROOT+'rationale.md') as f:text=f.read()
            begin=text.index('Final parameters:\n```json\n')+len('Final parameters:\n```json\n')
            end=text.index('\n```',begin)
            text=text[:begin]+json.dumps(d,indent=2)+text[end:]
            text+='\nA final local amplitude/shape refinement compared seven candidates over the combined 11 available seeds (99 trajectories). Selection maximized TIR with penalties for any observed TBR70 and minimum glucose below 68 mg/dL. These seeds now serve as optimization data, not an unbiased test set. The final selected design was reevaluated at four RK4 substeps per minute; final metrics supersede earlier candidate metrics above:\n```json\n'+json.dumps({k:v for k,v in m.items() if k!='rows'},indent=2)+'\n```\nReproduce with the additional `polish` stage. The final per-trajectory outcomes and exact seeds are in final_validation.json. Safety on new meals and native dopri5 is not guaranteed.\n'
            with open(ROOT+'rationale.tmp','w') as f:f.write(text)
            os.replace(ROOT+'rationale.tmp',ROOT+'rationale.md')
        print('SELECTED',json.dumps(d),json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
    elif stage=='holdout':
        seeds=[431127,806213,1209931,4427819,7311001,9142271,173891,293774]
        with open(ROOT+'design.json') as f:d=json.load(f)
        ex=Experiment(instance,seeds=seeds)
        m=evaluate(ex,d,steps=4)
        with open(ROOT+'holdout_validation.json','w') as f:json.dump(dict(seeds=seeds,design=d,**m),f,indent=2)
        with open(ROOT+'rationale.md','a') as f:
            f.write('\nAfter the final selection, a separate eight-seed check '+str(seeds)+' evaluated 72 additional trajectories with four RK4 substeps per minute. No candidate tuning used this check. Its outcomes were:\n```json\n'+json.dumps({k:v for k,v in m.items() if k!='rows'},indent=2)+'\n```\nReproduction stage order: `coarse`, `refine`, `stress`, `polish`, `holdout`. Run each as `OPENBLAS_NUM_THREADS=1 python /work/output/search.py STAGE`. This last check offers additional empirical evidence only; the final verifier uses unseen scenarios and native dopri5.\n')
        print('HOLDOUT',json.dumps({k:v for k,v in m.items() if k!='rows'}),flush=True)
        validate_design(d,instance)
        assert all(os.path.isfile(ROOT+file) and os.path.getsize(ROOT+file)>0 for file in ['design.json','search.py','rationale.md'])
