"""Reproducible search for GRI static formulation (dev-05).

Responsive mode: rate = theta_a*TDI * (relative_leak + Hill(filtered IG)),
finite reservoir theta_L*TDI.  All coefficients shared across the cohort.
"""
import json, itertools, math, time
from pathlib import Path
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS
from gri_bench.physiology import release_step, hill

INSTANCE = load_instance()
JOBS = None


def build_experiment():
    global JOBS
    e = Experiment(INSTANCE)
    JOBS = e.jobs
    return e


def evaluate(design):
    return Experiment(INSTANCE).evaluate(design)


def objective(design):
    """Mean TIR if feasible, else a penalty-scaled value."""
    m = evaluate(design)
    if m['feasible']:
        return m['mean_tir']
    # penalty: hard constraints dominate; report safe_tir (0) for infeasible
    return m['safe_tir']


def grid_search():
    b = INSTANCE['bounds']
    # Coarse safety-first sweep: low leak / modest amplitude region.
    thetas = {
        'theta_a': np.linspace(b['theta_a'][0], b['theta_a'][1], 12),
        'relative_leak': np.linspace(b['relative_leak'][0], b['relative_leak'][1], 10),
        'ec50_mg_dl': np.linspace(b['ec50_mg_dl'][0], b['ec50_mg_dl'][1], 10),
        'hill_n': np.linspace(b['hill_n'][0], b['hill_n'][1], 10),
        'tau_min': np.linspace(b['tau_min'][0], b['tau_min'][1], 10),
        'theta_L': np.linspace(b['theta_L'][0], b['theta_L'][1], 10),
    }
    best = None
    for vals in itertools.product(*[thetas[k] for k in PARAMETERS]):
        d = dict(zip(PARAMETERS, vals))
        design = {'mode': 'responsive', 'parameters': {k: float(v) for k, v in d.items()}}
        sc = objective(design)
        if best is None or sc > best[0]:
            best = (sc, design)
    return best


def local_refine(design, step=0.05, iters=6):
    p = dict(design['parameters'])
    b = INSTANCE['bounds']
    best = objective(design)
    for _ in range(iters):
        improved = False
        for k in PARAMETERS:
            lo, hi = b[k]
            for mul in (1.0 + step, 1.0 - step):
                q = dict(p)
                q[k] = float(np.clip(p[k] * mul, lo, hi))
                if q[k] == p[k]:
                    continue
                sc = objective({'mode': 'responsive', 'parameters': q})
                if sc > best:
                    best, p, improved = sc, q, True
        if not improved:
            step *= 0.5
    return {'mode': 'responsive', 'parameters': p}


def main():
    t0 = time.time()
    build_experiment()
    best_design, best_sc = None, -1.0
    log = []

    # 1) Constant-mode baseline (always feasible at theta_c=0, TIR ~0).
    cb = INSTANCE['constant_theta_c_bounds']
    for tc in np.linspace(cb[0], cb[1], 8):
        for tL in np.linspace(INSTANCE['bounds']['theta_L'][0], INSTANCE['bounds']['theta_L'][1], 5):
            d = {'mode': 'constant', 'parameters': {'theta_c': float(tc), 'theta_L': float(tL)}}
            sc = objective(d)
            log.append((sc, d))
            if sc > best_sc:
                best_sc, best_design = sc, d

    # 2) Coarse responsive grid.
    sc, d = grid_search()
    log.append((sc, d))
    if sc > best_sc:
        best_sc, best_design = sc, d

    # 3) Local refinement around the best responsive candidate.
    sc = objective(best_design)
    for step in (0.15, 0.06, 0.02):
        d = local_refine(best_design, step=step, iters=4)
        sc = objective(d)
        log.append((sc, d))
        if sc > best_sc:
            best_sc, best_design = sc, d

    save_design(best_design)
    Path('/work/output/search_log.json').write_text(json.dumps(
        [{'score': float(s), 'design': d} for s, d in log], indent=2))
    print(f'elapsed={time.time()-t0:.1f}s best={best_sc:.3f}')
    print(json.dumps(best_design, indent=2))


if __name__ == '__main__':
    main()
