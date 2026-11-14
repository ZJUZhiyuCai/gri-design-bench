"""Local prescreen runner: immutable plan -> designs -> fast screen -> native audit.

No model API calls, no publication, and no writes to earlier experiment files.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from multiprocessing import get_context
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import time
import numpy as np
from gri_bench.api import Experiment, summarize, glucose_metrics, individual_design
from gri_bench.physiology import patient_parameters, fast_trace, meal_schedule
from gri_bench.native import native_trace
from gri_bench.runner import ROOT
from .search import candidate_search,shortlist,validate_fixed,race,transfer_design,loss,key,compact

EXP=ROOT/'experiments/search-validation-prescreen-2026-11-13'
OUT=ROOT/'private/search-validation-prescreen-2026-11-13'
CASES=[f'dev-{i:02}' for i in range(1,7)]
METHODS=['de_search','de_fixed','de_racing','sobol_fixed','constant_search','constant_fixed','de_no_margin','de_early']

def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def digest_json(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()
def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def check_plan():
    p=read(EXP/'plan.json');lock=read(EXP/'implementation-lock.json')
    if sha(EXP/'plan.json')!=lock['plan_sha256']:raise ValueError('Plan changed')
    for name,digest in lock['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen input/code changed: '+name)
    return p

def prepare():
    if EXP.exists():raise FileExistsError(EXP)
    EXP.mkdir(parents=True)
    instances={c:read(ROOT/f'instances/dev/{c}.json') for c in CASES}
    oldpanels=read(ROOT/'instances/v0.2/development-evaluation.json')['cases']
    panels={}
    for i,c in enumerate(CASES):
        train=instances[c]['training_seeds'];train=train+[int((train[0]+1_000_000_007)%2**32)] if len(train)==1 else train
        rng=np.random.default_rng(2026111320+i)
        validation=rng.choice(np.arange(960_000_000+i*100_000,960_100_000+i*100_000),44,replace=False).tolist()
        evaluation=rng.choice(np.arange(970_000_000+i*100_000,970_100_000+i*100_000),32,replace=False).tolist()
        assert not(set(train)&set(validation) or set(validation)&set(evaluation) or set(evaluation)&set(oldpanels[c]))
        panels[c]={'training':train,'validation':validation,'evaluation':evaluation}
    patients=[p for x in instances.values() for p in x['patients']]
    assert len(set(patients))==18
    plan={'id':EXP.name,'created_utc':now(),'scope':'Exploratory no-model prescreen on six previously seen development cohorts; new meal panels. Not new-patient validation.',
          'cases':CASES,'repetitions':5,'search_seeds':[2026111341+i for i in range(5)],'methods':METHODS+['fixed_transfer'],
          'instances':instances,'panels':panels,'query_unit':'One design x one seed x all 3 patients x all 3 variants (9 trajectories).',
          'query_budget':256,'search_candidates_full':128,'search_candidates_split':64,'shortlist':8,
          'fixed_validation_seeds':16,'racing_blocks':[4,8,32],'racing_survivors':[4,2,1],
          'racing_zero':'Zero-release candidate reserved at each non-final elimination.',
          'margin':{'tbr70':3,'tbr54':.5,'minimum':45},'no_margin':'Selection-only ablation on exactly the same fixed-validation observations.',
          'early':'Training incumbent after 64 candidates / 128 queries; intentionally half budget, not cost matched.',
          'fixed_transfer':'Leave-target-case-out raw-parameter median of five historical robust-reference designs, clipped to target bounds; zero online queries; historical offline cost not zero.',
          'optimizer':'Sequential DE/rand/1/bin population16, F Uniform(.45,1), CR .85, Sobol initialization; declared old-prompt anchor and zero control; no polishing.',
          'evaluation':'First 16 fresh seeds primary; all 32 sensitivity. Existing v0.2 safety/TIR windows and thresholds unchanged.',
          'primary_estimator':'Case means over all 5 optimizer seeds; paired case differences, six disjoint patient groups. No trial/trajectory pseudoreplication.',
          'native_audit':'All trajectories on first evaluation seed per unique design plus every fast trajectory within 0.5pp TBR70 of4, 0.25pp TBR54 of1, or5mg/dL minimum of40. Native original RHS check on six deterministic anchors. Any safety-classification mismatch blocks unqualified continuation.',
          'gates':{'validation':'de_fixed - de_search >=5pp case-mean score, positive in >=4/6 cases, safety passes no more than1/30 worse; point-estimate screening only, not significance.',
                   'adaptive':'de_racing - de_fixed >=3pp, positive in>=4/6 cases, no lower safety-pass count.',
                   'transfer':'Transfer within5pp of best responsive online mean AND safe on>=5/6 cases suggests limited need for per-case search; not an equivalence test.',
                   'native_confirmation':'If validation gate passes with zero audited safety-classification mismatches, natively rescore ALL 16-seed trajectories for de_search and de_fixed, all30 runs each. Other methods remain audited fast-screen evidence.',
                   'outcome':'Continue method study only when main effect survives native confirmation; adaptive claim requires its separate gate. If gates fail, retain negative findings and do not launch new Agent runs.'},
          'disclosure':'Primary screen is RK4; selective native audit does not make un-audited scores native-verified. Hash freeze is local, not public preregistration.',
          'workers':3,'host':platform.platform(),'python':platform.python_version()}
    write_new(EXP/'plan.json',plan)
    # Existing tracked files are protected, including old numerical results.
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    protected={name:sha(ROOT/name) for name in tracked if name and (ROOT/name).is_file()}
    write_new(EXP/'preservation.json',protected)
    source=list((ROOT/'src/gri_bench').glob('*.py'))+list((ROOT/'src/gri_bench/prescreen_v03').glob('*.py'))
    source +=[ROOT/'src/gri_bench/v02/search.py',ROOT/'results/v0.2/calibration/robust-reference.json']
    source +=list((ROOT/'instances/dev').glob('dev-??.json'))+[ROOT/'tests/test_prescreen_v03.py']
    write_new(EXP/'implementation-lock.json',{'created_utc':now(),'plan_sha256':sha(EXP/'plan.json'),'files':{str(p.relative_to(ROOT)):sha(p) for p in source}})
    print('FROZEN',EXP,sha(EXP/'plan.json'),flush=True)

def warmup(instance):
    p,x=patient_parameters(instance['patients'][0]);fast_trace(p,x,np.zeros(6),np.array([0.,-1.,150.,2.,10.,100.]))

def search_job(args):
    case,rep=args;p=check_plan();instance=p['instances'][case];seeds=p['panels'][case];rng_seed=p['search_seeds'][rep-1]
    out=OUT/'search'/f'{case}-r{rep}.json'
    if out.exists():
        old=read(out);assert old['plan_sha256']==sha(EXP/'plan.json');return str(out)
    warmup(instance);start=time.process_time();results={};details={}
    def record(name,d,q,cpu,origin):results[name]={'design':d,'query_units':q,'trajectories':q*9,'cpu_seconds':cpu,'origin':origin}
    for mode,optimizer,label,count in [('responsive','de','de',128),('responsive','sobol','sobol',64),('constant','de','constant',128)]:
        archive,panel=candidate_search(instance,seeds['training'],rng_seed,count,mode,optimizer)
        first=archive[:64];chosen=shortlist(first);details[label]={'archive':archive,'training_events':panel.events}
        fixed,fp=validate_fixed(instance,chosen,seeds['validation'][:16])
        details[label]['fixed_validation']={'candidates':fixed,'events':fp.events}
        record(label+'_fixed',fixed[0]['design'],256,first[-1]['cpu_seconds']+fp.cpu,'first64 + fixed16 per8')
        if label in ('de','constant'):
            best=min(archive,key=lambda r:(r['loss'],r['index']))
            record(label+'_search',best['design'],256,archive[-1]['cpu_seconds'],'128 candidate training search')
        if label=='de':
            early=min(first,key=lambda r:(r['loss'],r['index']))
            record('de_early',early['design'],128,first[-1]['cpu_seconds'],'first64 training incumbent')
            nomargin=min(fixed,key=lambda r:(loss(r['validation'],False),r['candidate_index']))
            record('de_no_margin',nomargin['design'],256,first[-1]['cpu_seconds']+fp.cpu,'same fixed observations; official rather than stricter selection thresholds')
            selected,stages,rp=race(instance,chosen,seeds['validation'])
            record('de_racing',selected['design'],256,first[-1]['cpu_seconds']+rp.cpu,'first64 + reserved-zero successive halving')
            details['racing']={'stages':stages,'events':rp.events}
    write_new(out,{'case':case,'repetition':rep,'search_seed':rng_seed,'plan_sha256':sha(EXP/'plan.json'),
                   'finished_utc':now(),'actual_job_cpu_seconds':time.process_time()-start,'methods':results,'details':details})
    print('SEARCH',case,rep,round(time.process_time()-start,2),flush=True)
    return str(out)

def design_records(p):
    rows=[]
    for case in p['cases']:
        for rep in range(1,p['repetitions']+1):
            x=read(OUT/'search'/f'{case}-r{rep}.json')
            if x['plan_sha256']!=sha(EXP/'plan.json'):raise ValueError('Search plan mismatch')
            for method in METHODS:rows.append({'case':case,'repetition':rep,'method':method,**x['methods'][method]})
        d,donors=transfer_design(p['instances'][case],read(ROOT/'results/v0.2/calibration/robust-reference.json')['cases'])
        rows.append({'case':case,'repetition':0,'method':'fixed_transfer','design':d,'donors':donors,'query_units':0,'cpu_seconds':0.})
    for r in rows:r['design_id']=digest_json({'case':r['case'],'design':r['design']})[:24]
    return rows

def screen_job(arg):
    case,design_id,design=arg;p=check_plan();out=OUT/'screen'/f'{design_id}.json'
    if out.exists():return read(out)
    instance=p['instances'][case];warmup(instance)
    seeds=p['panels'][case]['evaluation'];m=Experiment(instance,seeds=seeds).evaluate(design)
    rows=m['rows'];primary=[r for r in rows if r['seed'] in seeds[:16]]
    def summary(rs):
        s=summarize(rs);failed=sum(not summarize([r])['feasible'] for r in rs)
        return {**s,'failed_trajectories':failed,'violation_fraction':failed/len(rs)}
    result={'case':case,'design_id':design_id,'design':design,'primary':summary(primary),'expanded':summary(rows),'rows':rows,'plan_sha256':sha(EXP/'plan.json')}
    write_new(out,result);return result

def audit_indices(record,p):
    first=p['panels'][record['case']]['evaluation'][0];idx=[]
    for i,r in enumerate(record['rows']):
        m=r['metrics']
        if r['seed']==first or abs(m['tbr70']-4.)<=.5 or abs(m['tbr54']-1.)<=.25 or abs(m['minimum']-40.)<=5.:
            idx.append(i)
    return idx

@lru_cache(maxsize=512)
def native_input(case,index):
    p=check_plan();instance=p['instances'][case];seeds=p['panels'][case]['evaluation'];variants=instance['variants']
    per_patient=len(seeds)*len(variants)
    name=instance['patients'][index//per_patient]
    seed=seeds[(index%per_patient)//len(variants)];variant=variants[index%len(variants)]
    params,_=patient_parameters(name)
    meals=meal_schedule(seed,instance['days'],variant)*params.BW/instance['reference_weight_kg']
    return name,seed,variant,meals

def native_job(arg):
    case,design_id,design,index,original=arg;p=check_plan();suffix='-original' if original else ''
    out=OUT/'native'/design_id/f'{index:03}{suffix}.json'
    if out.exists():return read(out)
    instance=p['instances'][case];warmup(instance)
    # The same seed/patient/variant ordering as the fast screen.
    name,seed,variant,meals=native_input(case,index)
    trace,minute=native_trace(name,meals,individual_design(design,instance['tdi'][name]),instance['patient_seed'],original_rhs=original)
    metrics=glucose_metrics(trace,instance['warmup_minutes'],minute)
    out.parent.mkdir(parents=True,exist_ok=True)
    npz=out.with_suffix('.npz')
    if npz.exists():raise FileExistsError('Unfinished native artifact: '+str(npz))
    np.savez_compressed(npz,trace=trace,minute=minute)
    result={'case':case,'design_id':design_id,'index':index,'patient':name,'seed':seed,'variant':variant,'metrics':metrics,
            'native_integrator':'simglucose-dopri5','original_rhs':original,'trace_sha256':sha(npz),'plan_sha256':sha(EXP/'plan.json')}
    write_new(out,result);return result

def pool_run(fn,jobs,workers):
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(fn,j):j for j in jobs}
        n=0
        for f in as_completed(futures):
            f.result();n+=1
            if n%20==0 or n==len(jobs):print(fn.__name__,n,'/',len(jobs),now(),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','search','screen','audit','confirm','preserve']);parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    if args.stage=='prepare':prepare();return
    p=check_plan();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='search':pool_run(search_job,[(c,r) for c in p['cases'] for r in range(1,p['repetitions']+1)],args.workers)
    elif args.stage in ('screen','audit','confirm'):
        rows=design_records(p);unique={r['design_id']:r for r in rows}
        if args.stage=='screen':
            pool_run(screen_job,[(r['case'],d,r['design']) for d,r in unique.items()],args.workers)
            if not (OUT/'designs.json').exists():write_new(OUT/'designs.json',rows)
        else:
            jobs=[]
            if args.stage=='confirm':
                decision=read(OUT/'screen-decision.json')
                if not decision['validation_gate'] or decision['audit_safety_mismatches']!=0:raise ValueError('Native confirmation gate not satisfied')
                unique={r['design_id']:r for r in rows if r['method'] in ('de_search','de_fixed')}
            for d,r in unique.items():
                rec=read(OUT/'screen'/f'{d}.json')
                idx=audit_indices(rec,p) if args.stage=='audit' else [i for i,x in enumerate(rec['rows']) if x['seed'] in p['panels'][r['case']]['evaluation'][:16]]
                jobs.extend((r['case'],d,r['design'],i,False) for i in idx if not (OUT/'native'/d/f'{i:03}.json').exists())
            print('NATIVE_JOBS',len(jobs),flush=True);pool_run(native_job,jobs,args.workers)
            if args.stage=='audit':
                anchors=[next(r for r in rows if r['case']==c and r['method']=='fixed_transfer') for c in p['cases']]
                pool_run(native_job,[(r['case'],r['design_id'],r['design'],0,True) for r in anchors],args.workers)
    else:
        protected=read(EXP/'preservation.json');changed=[name for name,d in protected.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=d]
        print('PROTECTED',len(protected),'CHANGED',changed)
        if changed:raise ValueError('Protected file changes')

if __name__=='__main__':main()
