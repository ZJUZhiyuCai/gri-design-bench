"""Shared formulation search. Run with PYTHONPATH=/opt python search.py.
Candidate history and validation are persisted for audit. CPU-limited stages can
be rerun separately using the positional stage argument.
"""
import json, sys, time, os
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS
OUT='/work/output/'
I=load_instance()

def design(a, ec=150., n=12., tau=1., leak=None, load=4.):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[a,I['bounds']['relative_leak'][0] if leak is None else leak,ec,n,tau,load]))}

def record(d,m,tag):
    row={'design':d,'metrics':m,'stage':tag}
    with open(OUT+'history.jsonl','a') as f: f.write(json.dumps(row)+'\n')
    print(json.dumps({'parameters':d['parameters'], **{k:v for k,v in m.items() if k!='rows'}}),flush=True)

def evaluate(e,d,tag):
    m=e.evaluate(d); record(d,m,tag); return m

if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else 'amplitude'
    exp=Experiment(I)
    if stage=='amplitude':
        for a in [.0003,.0004,.0005,.0006,.0007,.0008,.0009]:
            d=design(a); m=evaluate(exp,d,stage)
            if m['feasible']:
                old=json.load(open(OUT+'best.json')) if os.path.exists(OUT+'best.json') else {'score':-1}
                if m['mean_tir']>old['score']:
                    save_design(d); json.dump({'score':m['mean_tir'],'design':d},open(OUT+'best.json','w'))
    elif stage=='shape':
        best=-1
        for ec in [100.,120.,140.,160.,180.]:
            for n in [3.,8.,24.]:
                for a in [.00045,.00055,.00065]:
                    d=design(a,ec,n,.05); m=exp.evaluate(d)
                    with open(OUT+'history.jsonl','a') as f:f.write(json.dumps({'design':d,'metrics':m,'stage':stage})+'\n')
                    if m['max_trajectory_tbr70']<=1 and m['minimum_glucose']>=60 and m['mean_tir']>best:
                        best=m['mean_tir']; save_design(d)
                        print(json.dumps({'design':d,'mean_tir':best,'tbr':m['max_trajectory_tbr70'],'minimum':m['minimum_glucose']}),flush=True)
    elif stage=='validation':
        exp=Experiment(I,seeds=[7123001,7123002,7123003,7123004,7123005,7123006])
        candidates=[design(a,ec,n,.05) for a in [.0004,.000425,.00045] for ec in [110.,130.] for n in [4.,12.]]
        candidates += [design(.0005,160.,3.,.05),design(.000525,160.,3.,.05),design(.00055,180.,3.,.05)]
        best=-1
        for d in candidates:
            m=evaluate(exp,d,stage)
            if m['max_trajectory_tbr70']<=2 and m['max_trajectory_tbr54']==0 and m['minimum_glucose']>=55 and m['mean_tir']>best:
                best=m['mean_tir'];save_design(d)
    elif stage=='refine':
        exp=Experiment(I,seeds=[6111002,7123005,7123006])
        candidates=[design(a,ec,n,.05) for a in [.00032,.00035,.00038] for ec in [80.,100.] for n in [4.,12.]]
        candidates += [design(.0004,120.,8.,.05), design(.00039,110.,8.,.05),design(.0004,110.,6.,.05),design(.00042,125.,6.,.05)]
        for d in candidates: evaluate(exp,d,stage)
    elif stage=='stress':
        exp=Experiment(I,seeds=list(range(8244001,8244016)))
        candidates=[design(.00034,80.,12.,.05),design(.00035,80.,12.,.05),design(.00038,100.,12.,.05),design(.0004,110.,4.,.05)]
        best=-1
        for d in candidates:
            m=evaluate(exp,d,stage)
            if m['max_trajectory_tbr70']<=1 and m['max_trajectory_tbr54']==0 and m['minimum_glucose']>=60 and m['mean_tir']>best:
                best=m['mean_tir'];save_design(d)
    elif stage=='final':
        import signal
        d=json.load(open(OUT+'design.json'))
        m=evaluate(Experiment(I,seeds=[6111002,7123001,7123002,7123003,7123004,7123005,7123006]),d,stage)
        json.dump(m,open(OUT+'final_fast_metrics.json','w'),indent=2)
        # Bound native spot-check CPU so all submission files remain complete.
        def expired(*args): raise TimeoutError('Native spot-check CPU limit')
        signal.signal(signal.SIGPROF,expired);signal.setitimer(signal.ITIMER_PROF,4.)
        try:
            from gri_bench.native import native_trace
            from gri_bench.api import individual_design, glucose_metrics
            rows=[json.loads(x) for x in open(OUT+'history.jsonl')]
            stress=next(x for x in rows if x['stage']=='stress' and x['design']==d)
            worst=min(stress['metrics']['rows'],key=lambda x:x['metrics']['minimum'])
            exp=Experiment(I,seeds=[worst['seed']],variants=[worst['variant']])
            job=next(j for j in exp.jobs if j[0]==worst['patient'])
            tr,mins=native_trace(job[0],job[5],individual_design(d,I['tdi'][job[0]]),I['patient_seed'])
            result={'patient':job[0],'seed':job[1],'variant':job[2],'metrics':glucose_metrics(tr,I['warmup_minutes'],mins)}
            json.dump(result,open(OUT+'native_check.json','w'),indent=2);print('NATIVE',json.dumps(result),flush=True)
        except TimeoutError as e: print(str(e),flush=True)
        finally:signal.setitimer(signal.ITIMER_PROF,0.)
    elif stage=='confirmation':
        d=json.load(open(OUT+'design.json'))
        m=evaluate(Experiment(I,seeds=list(range(9335001,9335021))),d,stage)
        json.dump(m,open(OUT+'confirmation_metrics.json','w'),indent=2)
