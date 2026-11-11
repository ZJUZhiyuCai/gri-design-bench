"""Reproducible search for the GRI static formulation, instance dev-02.

Usage:  python search.py [cpu_seconds]     # default 14; rewrites design.json
Phase 1: coarse random search parametrised by base flux b = theta_a*relative_leak (log-uniform),
         theta_L fixed at its upper bound (reservoir only relaxes the depletion cap).
Phase 2: multiplicative coordinate refinement (log-normal, adaptive step) around the incumbent.
Objective: mean post-warmup TIR penalised for TBR70 > 1 %, TBR54 > 0.2 %, minimum < 60 mg/dL,
plus a graded margin term (identical intent to the official gate, stricter on the margins).
The submitted design.json is the best point found by this procedure.
"""
import json, sys, time
import numpy as np
from gri_bench.api import load_instance, Experiment

ORDER = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')
T0 = time.process_time()
inst = load_instance()
B = inst['bounds']
LO = np.array([B[k][0] for k in ORDER], float)
HI = np.array([B[k][1] for k in ORDER], float)
LO[0] = 1e-6                      # keep theta_a finite for the b/leak parametrisation
exp = Experiment(inst)


def make(x):
    return {'mode': 'responsive', 'parameters': {k: float(v) for k, v in zip(ORDER, x)}}


def evaluate(x):
    return exp.evaluate(make(np.clip(x, LO, HI)))


def score(m):
    pen = 300.0 * max(0.0, m['max_trajectory_tbr70'] - 1.0)
    pen += 200.0 * max(0.0, m['max_trajectory_tbr54'] - 0.2)
    pen += 3.0 * max(0.0, 75.0 - m['minimum_glucose'])
    if (m['max_trajectory_tbr70'] > 4 or m['max_trajectory_tbr54'] > 1
            or m['minimum_glucose'] < 40):
        pen += 500.0
    return m['mean_tir'] - pen


def search(budget=14.0, seed=20261111):
    rng = np.random.default_rng(seed)
    best = (-1e9, None, None)
    while time.process_time() - T0 < 0.6 * budget:          # phase 1
        base = 10 ** rng.uniform(-4.0, -2.35)               # U/min per U of TDI
        leak = 10 ** rng.uniform(np.log10(LO[1]), np.log10(HI[1]))
        x = np.array([base / leak, leak,
                      rng.uniform(LO[2], 160.0),
                      rng.uniform(LO[3], 3.0),
                      rng.uniform(LO[4], 4.0),
                      HI[5]])
        m = evaluate(x)
        s = score(m)
        if s > best[0]:
            best = (s, x, m)
    step = 0.25
    while time.process_time() - T0 < budget:                # phase 2
        cand = np.clip(best[1] * np.exp(rng.normal(0, step, len(ORDER))), LO, HI)
        cand[5] = HI[5]
        m = evaluate(cand)
        s = score(m)
        if s > best[0]:
            best, step = (s, cand, m), min(0.5, step * 1.25)
        else:
            step = max(0.03, step * 0.9)
    return best


if __name__ == '__main__':
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 14.0
    s, x, m = search(budget)
    print('design', make(x))
    print({k: v for k, v in m.items() if k != 'rows'})
    for r in m['rows']:
        print(r['patient'], r['variant'], {k: round(v, 2) for k, v in r['metrics'].items()})
    from gri_bench.api import save_design
    save_design(make(x))
