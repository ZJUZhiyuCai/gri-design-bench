"""Reproducible search for the GRI static formulation (instance dev-06).

Staged deterministic coordinate search over the responsive shape parameters,
using the public fast-RK4 Experiment as surrogate. Safety-first objective:
feasible designs ranked by mean TIR; infeasible designs ranked by violation.
The best candidate is checkpointed atomically to /work/output/design.json.
A CPU-time guard keeps total container activity within budget.
"""
import json, os, time
import numpy as np
from gri_bench.api import Experiment, load_instance, save_design

T0 = time.process_time()
CPU_LIMIT = float(os.environ.get('GRI_CPU_LIMIT', '20'))
OUT = '/work/output/design.json'

def used():
    return time.process_time() - T0

def key(res):
    if res['feasible']:
        return (1, res['mean_tir'], res['minimum_glucose'])
    return (0, -(4 - res['max_trajectory_tbr70']) ** 2
               -(1 - res['max_trajectory_tbr54']) ** 2
               - max(0.0, 40 - res['minimum_glucose']) ** 2)

def search():
    instance = load_instance()
    experiment = Experiment(instance)
    lo = {k: v[0] for k, v in instance['bounds'].items()}
    hi = {k: v[1] for k, v in instance['bounds'].items()}

    def design(p):
        return {'mode': 'responsive', 'parameters': dict(p)}

    best = None
    log = []

    def trial(p):
        nonlocal best
        try:
            res = experiment.evaluate(design(p))
        except Exception as exc:
            log.append((p, 'error', str(exc))); return
        k = key(res)
        log.append((dict(p), k, res['mean_tir'], res['max_trajectory_tbr70'],
                    res['max_trajectory_tbr54'], res['minimum_glucose']))
        if best is None or k > best[0]:
            best = (k, dict(p))
            save_design(design(p), OUT)          # atomic checkpoint

    start = {'theta_a': 0.00035, 'relative_leak': 1.0, 'ec50_mg_dl': 200.0,
             'hill_n': 2.0, 'tau_min': 10.0, 'theta_L': 3.0}
    trial(start)
    if used() > CPU_LIMIT:
        return best, log

    # stage 1: amplitude / leak sweeps (dominates basal fraction and total dose)
    for ta in [0.0002, 0.00028, 0.00044, 0.00055, 0.0007]:
        for lk in [0.7, 1.5, 2.5]:
            if used() > CPU_LIMIT: break
            p = dict(start, theta_a=ta, relative_leak=lk); trial(p)

    # stage 2: coordinate refinement of the current best
    grid = {'theta_a': [0.75, 1.3], 'relative_leak': [0.8, 1.25],
            'ec50_mg_dl': [0.7, 1.4], 'hill_n': [0.8, 1.3],
            'tau_min': [0.7, 1.4], 'theta_L': [0.85, 1.15]}
    for _ in range(2):
        if used() > CPU_LIMIT: break
        improved = False
        for k, mults in grid.items():
            for m in mults:
                if used() > CPU_LIMIT: break
                p = dict(best[1]); p[k] = float(np.clip(p[k] * m, lo[k], hi[k]))
                if p[k] != best[1][k]:
                    q = dict(p); trial(q)
                    if best[1][k] == p[k]: improved = True
        if not improved: break
    return best, log

if __name__ == '__main__':
    best, log = search()
    print('evaluations:', len(log), 'cpu_used:', round(used(), 2))
    for row in log:
        print(row)
    if best:
        print('BEST', best[1]); print('KEY', best[0])
