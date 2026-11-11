"""Reproducible search for the GRI static-formulation design (dev-03).

Ranking metric: mean post-warmup TIR, zeroed if any trajectory violates
TBR70 > 4%, TBR54 > 1%, or any full-horizon minute < 40 mg/dL.
"""
import json, os, sys, time
import numpy as np
from pathlib import Path

sys.path.insert(0, '/opt')
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS, individual_design
from gri_bench.physiology import fast_trace

INSTANCE_PATH = '/task/instance.json'
OUT_DIR = Path('/work/output')


def load_instance_local(path=INSTANCE_PATH):
    return json.loads(Path(path).read_text())


def score(instance, design, jobs=None):
    """Fast-RK4 score; returns (safe_tir, tir, tbr70, tbr54, min_glucose, rows)."""
    if jobs is None:
        jobs = Experiment(instance).jobs
    rows = []
    for name, seed, variant, p, initial, meals in jobs:
        trace = fast_trace(p, initial, meals, individual_design(design, instance['tdi'][name]))
        from gri_bench.api import glucose_metrics
        rows.append({'patient': name, 'seed': seed, 'variant': variant,
                     'metrics': glucose_metrics(trace, instance['warmup_minutes'])})
    from gri_bench.api import summarize
    s = summarize(rows)
    return s['safe_tir'], s['mean_tir'], s['max_trajectory_tbr70'], s['max_trajectory_tbr54'], \
        s['minimum_glucose'], rows


def make(theta_a, relative_leak, ec50, hill_n, tau, theta_L):
    return {'mode': 'responsive', 'parameters': dict(
        theta_a=theta_a, relative_leak=relative_leak, ec50_mg_dl=ec50,
        hill_n=hill_n, tau_min=tau, theta_L=theta_L)}


def main():
    instance = load_instance_local()
    b = instance['bounds']
    exp = Experiment(instance)
    jobs = exp.jobs

    rng = np.random.default_rng(2026111101)

    # ---- coarse grid -------------------------------------------------------
    grid = {
        'theta_a': [0.0005, 0.001, 0.0015, 0.002, 0.003],
        'relative_leak': [0.8, 1.0, 1.3, 1.7, 2.2],
        'ec50_mg_dl': [100, 120, 140, 160, 190],
        'hill_n': [1.5, 2.5, 4.0, 6.0],
        'tau_min': [2.0, 4.0, 6.0, 9.0],
        'theta_L': [1.2, 1.6, 2.0, 2.6, 3.2],
    }
    keys = list(grid.keys())
    best = None
    t0 = time.time()

    def vecs():
        return [np.array(grid[k]) for k in keys]

    import itertools
    for combo in itertools.product(*vecs()):
        d = make(*combo)
        st, tir, t70, t54, mg, _ = score(instance, d, jobs)
        if best is None or st > best[0]:
            best = (st, tir, t70, t54, mg, d)
        if time.time() - t0 > 14:
            break

    # ---- local random refinement ------------------------------------------
    cur = best[5]
    scales = {'theta_a': 0.001, 'relative_leak': 0.3, 'ec50_mg_dl': 15.0,
              'hill_n': 0.8, 'tau_min': 1.5, 'theta_L': 0.3}
    for it in range(400):
        cand = {}
        for k in keys:
            cand[k] = float(np.clip(cur['parameters'][k] + rng.normal(0, scales[k]),
                                    b[k][0], b[k][1]))
        d = make(**cand)
        st, tir, t70, t54, mg, _ = score(instance, d, jobs)
        if st > best[0]:
            best = (st, tir, t70, t54, mg, d)
            cur = d

    design = best[5]
    save_design(design)
    print(json.dumps({'score': best[0], 'mean_tir': best[1], 'max_tbr70': best[2],
                      'max_tbr54': best[3], 'min_glucose': best[4], 'design': design}, indent=2))


if __name__ == '__main__':
    main()
