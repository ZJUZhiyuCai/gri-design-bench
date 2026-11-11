"""Reproducible search for GRI design dev-02 (shared cohort coefficients).

Stage 1: coarse randomized sweep on the training seed.
Stage 2: pattern refinement of the top candidates, scored on training + fresh
validation seeds with strict hypo margins. Saves /work/output/design.json.
"""
import json, os, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, individual_design
from gri_bench.physiology import fast_trace, glucose_metrics

T0 = time.process_time()
BUDGET = float(os.environ.get('SEARCH_CPU', '18.0'))

def main():
    inst = load_instance()
    seeds = [inst['training_seeds'][0], 20261111, 777]
    groups = {}
    jobs_all = []
    for s in seeds:
        e = Experiment(inst, seeds=[s])
        groups[s] = list(range(len(jobs_all), len(jobs_all)+len(e.jobs)))
        jobs_all += e.jobs

    def run(design, idx):
        rows = []
        for i in idx:
            name, seed, variant, p, initial, meals = jobs_all[i]
            tr = fast_trace(p, initial, meals, individual_design(design, inst['tdi'][name]))
            rows.append(glucose_metrics(tr, inst['warmup_minutes']))
        return rows

    def score(design, idx):
        rows = run(design, idx)
        tir = np.mean([r['tir'] for r in rows])
        pen = 0.0
        for r in rows:
            pen += 400*max(0., r['tbr70']-1.0)**2 + 900*max(0., r['tbr54']-0.3)**2
            pen += 2.0*max(0., 45.0-r['minimum'])**2
        return tir - pen, rows

    rng = np.random.default_rng(0)
    lo = np.array([inst['bounds'][k][0] for k in ('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L')])
    hi = np.array([inst['bounds'][k][1] for k in ('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L')])
    span = np.array([1,0,1,1,1,0])  # log-scale flags
    def sample(n):
        u = rng.random((n,6))
        t = lo + u*(hi-lo)
        for j in range(6):
            if span[j]:
                t[:,j] = np.exp(np.log(lo[j]) + u[:,j]*(np.log(hi[j])-np.log(lo[j])))
        return t
    train = groups[seeds[0]]
    best = (-1e9, None)
    for t in sample(24):
        if time.process_time()-T0 > BUDGET: break
        d = {'mode':'responsive','parameters':dict(zip(('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L'), map(float,t)))}
        s,_ = score(d, train)
        if s > best[0]: best = (s, d)
    # Stage 2: pattern refinement on all seeds
    keys = ('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L')
    allidx = list(range(len(jobs_all)))
    cur = dict(best[1]['parameters']); curs,_ = score({'mode':'responsive','parameters':cur}, train)
    cursA,_ = score({'mode':'responsive','parameters':cur}, allidx)
    curall = cursA
    for it in range(40):
        if time.process_time()-T0 > BUDGET: break
        step = 0.5**it
        improved = False
        for k in keys:
            for mult in (1+0.6*step, 1/(1+0.6*step)):
                if time.process_time()-T0 > BUDGET: break
                trial = dict(cur); trial[k] = float(np.clip(trial[k]*mult, lo[keys.index(k)], hi[keys.index(k)]))
                st,_ = score({'mode':'responsive','parameters':trial}, allidx)
                if st > curall:
                    cur, curall = trial, st; improved = True; break
        if not improved and step < 0.05: break
    design = {'mode':'responsive','parameters':cur}
    save_design(design)
    res = score(design, allidx)[1]
    print(json.dumps({'design':design,'mean_tir':float(np.mean([r['tir'] for r in res])),
        'max_tbr70':max(r['tbr70'] for r in res),'max_tbr54':max(r['tbr54'] for r in res),
        'min_g':min(r['minimum'] for r in res)}))

if __name__ == '__main__':
    main()
