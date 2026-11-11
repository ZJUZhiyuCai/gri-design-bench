"""Reproducible search for the GRI static formulation (instance dev-06).

Strategy
--------
The design space is 6-dimensional and shared across the cohort, so a direct
random/coordinate search on the public fast integrator is used.  The objective
is the mean post-warmup TIR over the 3 known patients x 3 challenge variants,
with hard feasibility constraints (TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40)
enforced as large penalties with safety margin so the design generalises to
fresh meal seeds.  Extra unseen seeds are used for validation only.
"""
import json
import time
import numpy as np

from gri_bench.api import load_instance, Experiment, individual_design, glucose_metrics, summarize

PARAMETERS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')
BOUNDS = np.array([[0.0, 0.007],
                   [0.5124966150526034, 5.518918645844859],
                   [59.26305046791457, 816.1143093473472],
                   [0.5880395112623367, 4.0],
                   [2.0, 20.0],
                   [0.4, 4.0]])


def make_design(x):
    return {'mode': 'responsive',
            'parameters': {'theta_a': float(x[0]), 'relative_leak': float(x[1]),
                           'ec50_mg_dl': float(x[2]), 'hill_n': float(x[3]),
                           'tau_min': float(x[4]), 'theta_L': float(x[5])}}


class Evaluator:
    """Batched evaluator over an Experiment's job list."""

    def __init__(self, instance, seeds=None, variants=None):
        self.instance = instance
        self.exp = Experiment(instance, seeds=seeds, variants=variants)
        self.jobs = self.exp.jobs
        self.warmup = instance['warmup_minutes']
        self.tdi = instance['tdi']
        self.n = 0

    def evaluate(self, design):
        self.n += 1
        rows = []
        for name, seed, variant, p, initial, meals in self.jobs:
            trace = fast_trace(p, initial, meals,
                               individual_design(design, self.tdi[name]))
            rows.append({'patient': name, 'seed': seed, 'variant': variant,
                         'metrics': glucose_metrics(trace, self.warmup)})
        return summarize(rows)


def objective(summary, margin=0.7):
    """Safe TIR with margin-scaled feasibility penalties."""
    pen = 0.0
    pen += 300.0 * max(0.0, summary['max_trajectory_tbr70'] - 4.0 * margin)
    pen += 900.0 * max(0.0, summary['max_trajectory_tbr54'] - 1.0 * margin)
    pen += 30.0 * max(0.0, 40.0 + 5.0 - summary['minimum_glucose'])
    return summary['mean_tir'] - pen


def search(ev, iters=400, seed=0, x0=None, verbose=True):
    rng = np.random.default_rng(seed)
    x = np.array([0.0006, 1.5, 180.0, 2.0, 8.0, 2.5]) if x0 is None else x0.copy()
    x = np.clip(x, BOUNDS[:, 0], BOUNDS[:, 1])
    best = (objective(ev.evaluate(make_design(x))), x.copy())
    if verbose:
        print('start', best[0], best[1], flush=True)
    step = (BOUNDS[:, 1] - BOUNDS[:, 0]) * np.array([0.35, 0.5, 0.35, 0.3, 0.4, 0.25])
    for it in range(iters):
        cand = np.clip(best[1] + rng.normal(size=6) * step * (0.4 + 0.6 * rng.random()),
                       BOUNDS[:, 0], BOUNDS[:, 1])
        s = objective(ev.evaluate(make_design(cand)))
        if s > best[0]:
            best = (s, cand.copy())
        if it % 60 == 59:
            step *= 0.75
            if verbose:
                print(it, round(best[0], 3), np.round(best[1], 5), flush=True)
    return best


if __name__ == '__main__':
    t0 = time.time()
    inst = load_instance()
    ev = Evaluator(inst)
    print('jobs', len(ev.jobs), 'setup', round(time.time() - t0, 2), flush=True)
    score, x = search(ev, iters=int(__import__('os').environ.get('ITERS', 300)))
    print('BEST', score, x, 'evals', ev.n, 'cpu', round(time.time() - t0, 1))
    json.dump(make_design(x), open('/work/output/design.json', 'w'), indent=2)
