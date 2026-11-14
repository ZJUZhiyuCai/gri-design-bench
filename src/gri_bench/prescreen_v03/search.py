"""Deterministic query-budgeted search and validation controls.

A query is one design on one meal seed, for all cohort members and variants.
CPU is measured separately; this experiment does not claim equal wall/LLM cost.
"""
import copy
import time
import numpy as np
from scipy.stats import qmc
from gri_bench.api import PARAMETERS, Experiment, summarize, validate_design
from gri_bench.v02.search import robust_loss, zero_design


def loss(metrics, margin=True):
    if margin:
        return robust_loss(metrics)
    violation = (max(0., metrics['max_trajectory_tbr70']-4.)
                 + 4*max(0., metrics['max_trajectory_tbr54']-1.)
                 + max(0., 40.-metrics['minimum_glucose'])/5.)
    return (1000.+100.*violation if violation else 0.)-metrics['mean_tir']


def key(design):
    return (design['mode'], tuple(sorted(design['parameters'].items())))


def compact(metrics):
    return {k:v for k,v in metrics.items() if k!='rows'}


class Panel:
    """Cache scenario construction, not design outcomes. Every call is charged."""
    def __init__(self, instance, cap):
        self.instance=instance
        self.cap=cap
        self.queries=0
        self.trajectories=0
        self.events=[]
        self.panels={}
        self.cpu=0.

    def evaluate(self, design, seeds):
        seeds=tuple(seeds)
        if not seeds or len(set(seeds))!=len(seeds):
            raise ValueError('A panel must have distinct seeds')
        if self.queries+len(seeds)>self.cap:
            raise ValueError('Query budget exceeded')
        validate_design(design,self.instance)
        started=time.process_time()
        if seeds not in self.panels:
            self.panels[seeds]=Experiment(self.instance,seeds=list(seeds))
        metrics=self.panels[seeds].evaluate(design)
        self.queries+=len(seeds)
        self.trajectories+=len(metrics['rows'])
        self.cpu+=time.process_time()-started
        self.events.append({'query_end':self.queries,'seeds':list(seeds),
                            'design':copy.deepcopy(design),'metrics':compact(metrics)})
        return metrics


def coordinate_system(instance, mode):
    names=PARAMETERS if mode=='responsive' else ('theta_c','theta_L')
    b=[instance['constant_theta_c_bounds'] if k=='theta_c' else instance['bounds'][k] for k in names]
    low,high=np.array(b,dtype=float).T
    loglo=np.log(np.maximum(low,1e-7)); width=np.log(high)-loglo
    def decode(x):
        vals=np.clip(np.exp(loglo+np.asarray(x)*width),low,high)
        return {'mode':mode,'parameters':dict(zip(names,map(float,vals)))}
    def encode(d):
        return np.clip((np.log(np.maximum([d['parameters'][k] for k in names],1e-7))-loglo)/width,0.,1.)
    return names,decode,encode


def candidate_search(instance, seeds, rng_seed, count, mode='responsive', optimizer='de', panel=None):
    """DE/rand/1/bin, population 16, plus zero and a declared prompt anchor.

    Sequential updates and no polishing. The first 64 candidates are exactly
    identical whether the requested run stops at 64 or continues to 128.
    """
    if count<17 or optimizer not in ('de','sobol'):
        raise ValueError('Need >=17 candidates and a supported optimizer')
    panel=panel or Panel(instance,count*len(seeds))
    names,decode,encode=coordinate_system(instance,mode)
    rng=np.random.default_rng(rng_seed)
    points=qmc.Sobol(len(names),scramble=True,seed=rng_seed).random_base2(8)
    anchor=({'mode':'responsive','parameters':dict(zip(PARAMETERS,(.0002,1.5,200.,2.,10.,1.)))}
            if mode=='responsive' else {'mode':'constant','parameters':{'theta_c':.0002,'theta_L':1.}})
    points[0]=encode(anchor)
    pop=points[:16].copy(); costs=np.full(16,np.inf)
    records=[]
    started=time.process_time()
    def evaluate(d):
        m=panel.evaluate(d,seeds)
        records.append({'index':len(records),'design':copy.deepcopy(d),'training':compact(m),
                        'loss':loss(m),'queries':panel.queries,'cpu_seconds':time.process_time()-started})
        return loss(m)
    evaluate(zero_design(instance,mode))
    for i in range(16): costs[i]=evaluate(decode(pop[i]))
    for n in range(17,count):
        i=(n-17)%16
        if optimizer=='sobol':
            unit=points[n-1]
        else:
            choices=np.array([j for j in range(16) if j!=i])
            a,b,c=rng.choice(choices,size=3,replace=False)
            mutant=np.clip(pop[a]+rng.uniform(.45,1.)*(pop[b]-pop[c]),0.,1.)
            cross=rng.random(len(names))<.85;cross[rng.integers(len(names))]=True
            unit=np.where(cross,mutant,pop[i])
        value=evaluate(decode(unit))
        if optimizer=='de' and value<=costs[i]:pop[i]=unit;costs[i]=value
    return records,panel


def shortlist(records,k=8):
    unique={}
    for record in sorted(records,key=lambda r:(r['loss'],r['index'])):
        unique.setdefault(key(record['design']),record)
    ordered=list(unique.values())
    zero=next(r for r in records if all(v==0 for n,v in r['design']['parameters'].items() if n in ('theta_a','theta_c')))
    chosen=[r for r in ordered if key(r['design'])!=key(zero['design'])][:k-1]+[zero]
    if len(chosen)!=k:raise ValueError('Insufficient unique candidates')
    return chosen


def validate_fixed(instance, finalists, seeds, margin=True, panel=None):
    panel=panel or Panel(instance,len(finalists)*len(seeds))
    tested=[]
    for record in finalists:
        m=panel.evaluate(record['design'],seeds)
        tested.append({'candidate_index':record['index'],'design':record['design'],
                       'validation':compact(m),'loss':loss(m,margin)})
    tested.sort(key=lambda r:(r['loss'],r['candidate_index']))
    return tested,panel


def race(instance, finalists, seeds, panel=None):
    """Eight -> four -> two candidates; 4, 8, 32 ADDITIONAL seed blocks.

    8*4+4*8+2*32=128 queries, matching fixed 8*16. The final two have
    both seen 44 identical validation seeds. Discarded candidates never return.
    """
    if len(finalists)!=8 or len(seeds)!=44:raise ValueError('Racing needs 8 candidates and 44 seeds')
    panel=panel or Panel(instance,128)
    active=[{'candidate_index':r['index'],'design':r['design'],'rows':[]} for r in finalists]
    stages=[];offset=0
    for size,keep in ((4,4),(8,2),(32,1)):
        for r in active:
            m=panel.evaluate(r['design'],seeds[offset:offset+size]);r['rows'].extend(m['rows'])
            r['validation']=compact(summarize(r['rows']));r['loss']=loss(r['validation'])
        active.sort(key=lambda r:(r['loss'],r['candidate_index']))
        stages.append({'additional_seeds':size,'total_seeds':offset+size,'keep':keep,
                       'candidates':[{k:v for k,v in r.items() if k!='rows'} for r in active]})
        if keep>1:
            zero=next((r for r in active if all(v==0 for k,v in r['design']['parameters'].items() if k in ('theta_a','theta_c'))),None)
            active=([r for r in active if r is not zero][:keep-1]+[zero]) if zero is not None else active[:keep]
        else:
            active=active[:keep]
        offset+=size
    return {k:v for k,v in active[0].items() if k!='rows'},stages,panel


def transfer_design(instance, source_records):
    """LOO coordinate-wise raw-parameter median, clipped to target bounds.

    No target score or target design enters the median. Historical donor search
    cost is not charged as online compute and is explicitly reported separately.
    """
    donors=[r for r in source_records if r['case']!=instance['id']]
    if not donors:raise ValueError('No out-of-case donors')
    values={k:float(np.clip(np.median([r['design']['parameters'][k] for r in donors]),*instance['bounds'][k])) for k in PARAMETERS}
    d={'mode':'responsive','parameters':values};validate_design(d,instance)
    return d,[r['case'] for r in donors]
