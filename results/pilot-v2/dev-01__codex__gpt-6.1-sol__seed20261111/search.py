"""Reproduce the deterministic search and final verification.
Usage: python search.py [all|validate] (default: validate).
'all' repeats every optimization stage, requiring more CPU than validation.
Requires the public gri_bench API and scipy. Design parameters are cohort-shared.
"""
import json
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import (load_instance, Experiment, individual_design,
                           glucose_metrics, summarize, save_design, validate_design)
from gri_bench.physiology import fast_trace
OUT = Path(__file__).resolve().parent
I = load_instance()
SEARCH_SEEDS = [6111001, 82731, 492017, 951321, 160021]
VALIDATION_SEEDS = list(range(700001, 700021))

def design(a, ec=140., n=6., tau=5.):
    return {'mode': 'responsive', 'parameters': {
        'theta_a': float(a), 'relative_leak': I['bounds']['relative_leak'][0],
        'ec50_mg_dl': float(ec), 'hill_n': float(n),
        'tau_min': float(tau), 'theta_L': 4.}}

def evaluate(ex, d, steps=1):
    validate_design(d, I)
    rows = []
    for name, seed, variant, p, x, meals in ex.jobs:
        trace = fast_trace(p, x, meals, individual_design(d, I['tdi'][name]), substeps=steps)
        rows.append(dict(patient=name, seed=seed, variant=variant,
                         metrics=glucose_metrics(trace, I['warmup_minutes'])))
    return dict(summarize(rows), rows=rows)

def record(d, m, stage):
    with (OUT/'history.jsonl').open('a') as f:
        f.write(json.dumps(dict(stage=stage, design=d, metrics=m))+'\n')

def optimize(ex, bounds, x0, seed, iterations, stage, tbr_margin, min_margin,
             low_penalty, severe_penalty):
    best = -float('inf')
    def objective(x):
        nonlocal best
        d = design(*x)
        m = evaluate(ex, d)
        record(d, m, stage)
        score = (m['mean_tir'] - low_penalty*max(0., m['max_trajectory_tbr70']-tbr_margin)
                 - severe_penalty*m['max_trajectory_tbr54']
                 - max(0., min_margin-m['minimum_glucose']))
        if score > best:
            best = score
            if m['feasible']:
                save_design(d, OUT/'design.json')
        return -score
    return differential_evolution(objective, bounds, popsize=5, maxiter=iterations,
                                  seed=seed, polish=False, x0=x0, tol=.001)

def search():
    ex = Experiment(I)
    for a in [.00035, .00045, .00055, .00065, .00075, .00085]:
        d = design(a)
        record(d, evaluate(ex, d), 'screen')
    optimize(ex, [(.00048,.0011),(130,240),(3,24),(.05,12)],
             [.00055,140,6,5], 145, 3, 'refine', .7, 65., 6., 10.)
    ex = Experiment(I, seeds=SEARCH_SEEDS)
    d = json.loads((OUT/'design.json').read_text())
    record(d, evaluate(ex,d), 'fresh-initial')
    optimize(ex, [(.00048,.00078),(105,190),(1.5,24),(.05,20)],
             [.00055,140,6,5], 214, 4, 'robust', .3, 65., 8., 15.)
    d = json.loads((OUT/'design.json').read_text())
    x0 = [d['parameters'][k] for k in ['theta_a','ec50_mg_dl','hill_n','tau_min']]
    optimize(ex, [(.00046,.00057),(75,120),(5,24),(.05,20)],
             x0, 914, 2, 'local', .3, 66., 10., 15.)
    d = json.loads((OUT/'design.json').read_text())
    m = evaluate(Experiment(I,seeds=VALIDATION_SEEDS),d)
    record(d,m,'independent20')
    (OUT/'validation_coarse.json').write_text(json.dumps(m,indent=2)+'\n')

def validate():
    d = json.loads((OUT/'design.json').read_text())
    result = {}
    for label, seeds in [('search',SEARCH_SEEDS),('independent',VALIDATION_SEEDS)]:
        m = evaluate(Experiment(I,seeds=seeds),d,steps=4)
        result[label] = m
        print(label, {k:v for k,v in m.items() if k!='rows'}, flush=True)
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='all':
        search()
    validate()
