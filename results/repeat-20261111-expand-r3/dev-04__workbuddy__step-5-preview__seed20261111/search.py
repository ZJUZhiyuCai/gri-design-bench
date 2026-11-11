#!/usr/bin/env python3
"""Reproducible random+local search for the GRI static formulation design (dev-04).

Objective: maximise mean TIR over the known cohort (adult#004/005/006) x the three
training variants, subject to the hard safety envelope
(max per-trajectory TBR70 <= 4%, TBR54 <= 1%, full-horizon minimum glucose >= 40).
Feasibility is enforced by a large penalty; among feasible candidates the best
mean TIR wins.  Final ranking uses the public cached experiment (fast RK4).
"""
import json
import sys
import numpy as np

from gri_bench.api import load_instance, Experiment, PARAMETERS

INSTANCE = load_instance()
EXPERIMENT = Experiment(INSTANCE)

LOW = np.array([INSTANCE['bounds'][k][0] for k in PARAMETERS])
HIGH = np.array([INSTANCE['bounds'][k][1] for k in PARAMETERS])


def to_design(v):
    return {'mode': 'responsive',
            'parameters': {k: float(x) for k, x in zip(PARAMETERS, v)}}


def score(v, penalty=1000.0):
    """Return (safe_tir, feasible, mean_tir, diagnostics)."""
    res = EXPERIMENT.evaluate(to_design(v))
    ok = res['feasible']
    safe = res['safe_tir']
    return (safe - penalty * (0.0 if ok else 1.0)), ok, res


def objective(v):
    return score(v)[0]


def sample(rng):
    """Log-uniform where scale spans orders of magnitude."""
    v = np.empty(6)
    v[0] = np.exp(rng.uniform(np.log(1e-4), np.log(7e-3)))          # theta_a
    v[1] = np.exp(rng.uniform(np.log(0.55), np.log(5.5)))           # relative_leak
    v[2] = np.exp(rng.uniform(np.log(60.0), np.log(820.0)))         # ec50
    v[3] = np.exp(rng.uniform(np.log(0.6), np.log(24.0)))           # hill_n
    v[4] = np.exp(rng.uniform(np.log(0.05), np.log(20.0)))          # tau_min
    v[5] = np.exp(rng.uniform(np.log(0.4), np.log(1.25)))           # theta_L
    return np.clip(v, LOW, HIGH)


def local_refine(v, rng, scale=0.25, iters=25):
    best_v, best_s = v.copy(), objective(v)
    for _ in range(iters):
        cand = best_v * np.exp(rng.normal(0, scale, 6))
        cand = np.clip(cand, LOW, HIGH)
        s = objective(cand)
        if s > best_s:
            best_v, best_s = cand, s
    return best_v, best_s


def main(n_random=40, n_seeds=3, iters=20, seed=0):
    rng = np.random.default_rng(seed)
    pool = [sample(rng) for _ in range(n_random)]
    scored = [(objective(v), v) for v in pool]
    scored.sort(key=lambda t: -t[0])
    best_s, best_v = scored[0]
    for _, v in scored[:n_seeds]:
        rv, rs = local_refine(v, rng, scale=0.3, iters=iters)
        if rs > best_s:
            best_s, best_v = rs, rv
    res = EXPERIMENT.evaluate(to_design(best_v))
    design = to_design(best_v)
    out = {'design': design, 'safe_tir': res['safe_tir'],
           'feasible': res['feasible'], 'mean_tir': res['mean_tir'],
           'summary': {k: res[k] for k in ('mean_tir', 'max_trajectory_tbr70',
                                            'max_trajectory_tbr54', 'minimum_glucose')}}
    print(json.dumps(out, indent=2))
    return design, res


if __name__ == '__main__':
    main()
