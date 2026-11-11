"""Deterministic static formulation search, using only public physiology.
Run phases in order: python search.py coarse; python search.py refine;
python search.py validate. Results and candidates are persisted between phases.
"""
import os, sys, json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, individual_design, glucose_metrics, summarize, save_design, validate_design
from gri_bench.physiology import fast_trace
ROOT='/work/output'
I=load_instance()

def design(a, ec=140., n=12., leak=None, tau=2., load=4.):
    return {'mode':'responsive','parameters':dict(zip(PARAMETERS,[a,I['bounds']['relative_leak'][0] if leak is None else leak,ec,n,tau,load]))}

def evaluate(e,d,steps=1):
    validate_design(d,I)
    rows=[]
    for name,seed,v,p,x,meals in e.jobs:
        t=fast_trace(p,x,meals,individual_design(d,I['tdi'][name]),steps)
        rows.append({'patient':name,'seed':seed,'variant':v,'metrics':glucose_metrics(t,I['warmup_minutes'])})
    return dict(summarize(rows),rows=rows)

def read_records():
    path=ROOT+'/trials.json'
    return json.load(open(path)) if os.path.exists(path) else []

def atomic(path,obj):
    with open(path+'.tmp','w') as f: json.dump(obj,f,indent=2)
    os.replace(path+'.tmp',path)

def score(m):
    return m['mean_tir'] - 10*max(0,m['max_trajectory_tbr70']-1) - 20*max(0,m['max_trajectory_tbr54']) - 2*max(0,55-m['minimum_glucose'])

def run(candidates,e,steps=1):
    records=read_records()
    for d in candidates:
        m=evaluate(e,d,steps)
        records.append({'design':d,'metrics':m,'substeps':steps})
        print(json.dumps({'p':d['parameters'],'m':{k:v for k,v in m.items() if k!='rows'},'score':score(m)}),flush=True)
        atomic(ROOT+'/trials.json',records)
        safe=[r for r in records if r['metrics']['feasible']]
        if safe: save_design(max(safe,key=lambda r:score(r['metrics']))['design'])
    return records

if __name__=='__main__':
    phase=sys.argv[1] if len(sys.argv)>1 else 'coarse'
    e=Experiment(I)
    if phase=='coarse':
        run([design(a) for a in [0.0003,0.0004,0.0005,0.0006,0.0007,0.0008]],e)
    elif phase=='shape':
        run([design(a,ec,n) for ec in [150.,180.,210.,240.] for n in [4.,12.,24.] for a in [.00042,.00050]],e)
    elif phase=='smooth':
        run([design(a,ec,n,tau=.05) for ec in [100.,140.,180.] for n in [1.,2.,4.] for a in [.00040,.00046,.00052]],e)
    elif phase=='inspect':
        rs=sorted(read_records(),key=lambda r:score(r['metrics']),reverse=True)
        print(json.dumps(rs[:6],indent=2))
    elif phase=='fresh':
        seeds=[6111017,6111031,6111049,6111073,6111091,6111127,6111151,6111193]
        e=Experiment(I,seeds=seeds)
        candidates=[design(.0004,100.,2.,tau=.05),design(.00039,100.,2.,tau=.05),design(.00044,140.,1.,tau=.05),design(.00042,140.,1.,tau=.05),design(.00049,180.,2.,tau=.05),design(.00050,180.,4.,tau=.05),design(.00042,150.,4.),design(.00038,100.,1.,tau=.05)]
        out=[]
        for d in candidates:
            m=evaluate(e,d)
            out.append({'design':d,'metrics':m})
            atomic(ROOT+'/fresh.json',out)
            print(json.dumps({'p':d['parameters'],'m':{k:v for k,v in m.items() if k!='rows'}}),flush=True)
        safe=[r for r in out if r['metrics']['feasible']]
        if safe: save_design(max(safe,key=lambda r:score(r['metrics']))['design'])
    elif phase=='local':
        e=Experiment(I,seeds=[6111003,6111017,6111031,6111049])
        candidates=[design(a,ec,n,tau=.05) for ec,n,amps in [(80.,2.,[.00036,.00037,.00038]),(100.,2.5,[.00038,.00039,.00040]),(120.,2.,[.00042,.00043,.00044]),(120.,3.,[.00042,.00043,.00044]),(100.,1.5,[.00040,.00041,.00042])] for a in amps]
        out=[]
        for d in candidates:
            m=evaluate(e,d)
            out.append({'design':d,'metrics':m})
            atomic(ROOT+'/local.json',out)
            print(json.dumps({'p':d['parameters'],'m':{k:v for k,v in m.items() if k!='rows'}}),flush=True)
    elif phase=='validate':
        # Separate larger seed set, not used in local curve search.
        d=design(.000395,100.,2.,tau=.05)
        save_design(d)
        seeds=[6120001+137*i for i in range(20)]
        m=evaluate(Experiment(I,seeds=seeds),d,1)
        fine=evaluate(e,d,4)
        atomic(ROOT+'/validation.json',{'design':d,'new_seed_screen':m,'training_fine':fine,'screen_substeps':1,'fine_substeps':4})
        print(json.dumps({'new_seed_screen':{k:v for k,v in m.items() if k!='rows'},'training_fine':{k:v for k,v in fine.items() if k!='rows'}}),flush=True)
    elif phase=='finalize':
        d=design(.000385,100.,2.,tau=.05)
        save_design(d)
        prior=json.load(open(ROOT+'/validation.json'))['new_seed_screen']['rows']
        worst=sorted(prior,key=lambda r:(-r['metrics']['tbr70'],r['metrics']['minimum']))[:9]
        seeds=sorted(set(r['seed'] for r in worst))
        selected={(r['patient'],r['seed'],r['variant']) for r in worst}
        check=Experiment(I,seeds=seeds)
        check.jobs=[j for j in check.jobs if j[:3] in selected]
        m=evaluate(check,d,4)
        train=evaluate(e,d,4)
        atomic(ROOT+'/final_validation.json',{'design':d,'vulnerable_scenarios_fine':m,'training_fine':train,'substeps':4,'selected_from_prior_rows':worst})
        print(json.dumps({'vulnerable':{k:v for k,v in m.items() if k!='rows'},'train':{k:v for k,v in train.items() if k!='rows'}}))
        text='''# Shared responsive formulation

The final design uses theta_a=0.000385, relative_leak=0.5124966150526034, EC50=100 mg/dL, Hill exponent 2, filtering time 0.05 minutes, and reservoir load 4 times native TDI. All coefficients are shared across child#001, child#002 and child#003 and satisfy the instance bounds. The reservoir remains finite. No meal boluses or individual fitted coefficients are used.

A smooth glucose response balanced meal control against delayed insulin action better than steep Hill curves in this cohort. Minimum permitted leak maximizes the available response ratio; the short filter avoids adding delay. The maximum permitted load avoids unnecessary depletion over three days.

The reproducible search in search.py includes coarse amplitude screening, curve screening, fresh-seed comparisons, local refinement, larger validation and final safety reduction. Run phases coarse, shape, smooth, fresh, local, validate, finalize in that order. Results are saved in trials.json, fresh.json, local.json, validation.json and final_validation.json. Screening used RK4 with one-minute steps; final reported checks used the API physiology with four substeps per minute. All simulations reset to the native initial state. TIR/TBR omit day one; minimum glucose includes it.

A candidate with amplitude 0.000395 passed training but failed the larger 20-seed, 180-trajectory screen with worst TBR70 5.1042%. The submitted amplitude is reduced to 0.000385. The final design was retested on the nine most vulnerable trajectories selected from that screen and all nine original training trajectories. These selected checks are not independent validation; the final reduced design was not run over all 180 trajectories. Fresh unseen meals and the native dopri5 verifier can differ; the observed checks do not guarantee held-out safety.

Final four-substep training metrics: mean TIR %.6f%%, maximum trajectory TBR70 %.6f%%, maximum trajectory TBR54 %.6f%%, full-horizon minimum %.6f mg/dL.

Final four-substep vulnerable-scenario metrics: mean TIR %.6f%%, maximum trajectory TBR70 %.6f%%, maximum trajectory TBR54 %.6f%%, full-horizon minimum %.6f mg/dL.

This is a simulation benchmark, not a clinical recommendation.
''' % (train['mean_tir'],train['max_trajectory_tbr70'],train['max_trajectory_tbr54'],train['minimum_glucose'],m['mean_tir'],m['max_trajectory_tbr70'],m['max_trajectory_tbr54'],m['minimum_glucose'])
        with open(ROOT+'/rationale.md.tmp','w') as f:f.write(text)
        os.replace(ROOT+'/rationale.md.tmp',ROOT+'/rationale.md')
