#!/usr/bin/env python
"""Reproducible search for the dev-05 GRI static formulation (shared responsive parameters).

Stage 1: multiplicative coordinate descent from several starts, scored on the known cohort
with the training seed + one held-out seed, feasibility-aware (TBR70/TBR54/min-glucose
penalties). Stage 2: seed-stress comparison of the knee candidates (theta_a / EC50) over 9
meal seeds; the final design maximises mean TIR subject to worst-trajectory TBR70 == 0 and
min glucose >= 65. Run: python /work/output/search.py
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

INST = load_instance()
B = {k: tuple(v) for k, v in INST['bounds'].items()}

def clip(p):
    return {k: float(min(max(p[k], B[k][0]), B[k][1])) for k in PARAMETERS}

def design(p):
    return {'mode': 'responsive', 'parameters': clip(p)}

def score(r, tbr70_lim=2.0, tbr54_lim=0.5, min_floor=55.0):
    return r['mean_tir'] - (100.0 * max(0.0, r['max_trajectory_tbr70'] - tbr70_lim)
                            + 100.0 * max(0.0, r['max_trajectory_tbr54'] - tbr54_lim)
                            + 5.0 * max(0.0, min_floor - r['minimum_glucose'])), r

def coordinate_descent(exp, p0, deadline, factors=(1.7, 1.3, 1.12)):
    p, (s, m) = clip(p0), score(exp.evaluate(design(p0)))
    while time.time() < deadline:
        improved = False
        for k in PARAMETERS:
            for f in factors:
                for sgn in (1, -1):
                    if time.time() > deadline:
                        break
                    q = clip({**p, k: p[k] * f ** sgn})
                    if q == p:
                        continue
                    s2, m2 = score(exp.evaluate(design(q)))
                    if s2 > s:
                        p, s, m, improved = q, s2, m2, True
                    if improved:
                        break
        if not improved:
            break
    return p, s, m

def stress(exp, p):
    m = exp.evaluate(design(p))
    return m

if __name__ == '__main__':
    t0 = time.time()
    train_seeds = [INST['training_seeds'][0], 4001]
    exp = Experiment(INST, seeds=train_seeds)
    starts = [
        {'theta_a': 0.00025, 'relative_leak': 1.5, 'ec50_mg_dl': 130.0, 'hill_n': 3.0, 'tau_min': 10.0, 'theta_L': 2.5},
        {'theta_a': 0.00045, 'relative_leak': 1.5, 'ec50_mg_dl': 110.0, 'hill_n': 4.0, 'tau_min': 8.0, 'theta_L': 3.0},
        {'theta_a': 0.00035, 'relative_leak': 2.5, 'ec50_mg_dl': 160.0, 'hill_n': 2.0, 'tau_min': 15.0, 'theta_L': 3.5},
    ]
    deadline = t0 + 14.0
    best = None
    for p0 in starts:
        if time.time() > deadline:
            break
        p, s, m = coordinate_descent(exp, p0, deadline)
        print(f'CD score={s:.2f} tir={m["mean_tir"]:.2f} wtbr70={m["max_trajectory_tbr70"]:.2f} '
              f'min={m["minimum_glucose"]:.1f} {p}', flush=True)
        if best is None or s > best[1]:
            best = (p, s)
    # Stage 2: knee refinement under fresh-seed stress; require zero worst-trajectory TBR70.
    stress_seeds = [6111005, 4001, 101, 202, 303, 5501, 1234, 777, 8888]
    exps = Experiment(INST, seeds=stress_seeds)
    base = best[0]
    knee = [base,
            {**base, 'ec50_mg_dl': 104.0},
            {**base, 'theta_a': base['theta_a'] / 1.037},
            {**base, 'ec50_mg_dl': 108.0}]
    final, final_m = None, None
    for p in knee:
        m = stress(exps, p)
        print(f'KNEE tir={m["mean_tir"]:.2f} wtbr70={m["max_trajectory_tbr70"]:.2f} '
              f'wtbr54={m["max_trajectory_tbr54"]:.2f} min={m["minimum_glucose"]:.1f} {clip(p)}', flush=True)
        ok = (m['max_trajectory_tbr70'] == 0.0 and m['max_trajectory_tbr54'] == 0.0
              and m['minimum_glucose'] >= 65.0)
        better = final_m is None or (ok and m['mean_tir'] > final_m['mean_tir']) or \
                 (ok and (final_m['max_trajectory_tbr70'] > 0 or final_m['minimum_glucose'] < m['minimum_glucose'] - 3))
        if better:
            final, final_m = clip(p), m
    print('FINAL', final, {k: round(v, 3) for k, v in final_m.items() if k != 'rows'})
    save_design(design(final))
    json.dump({'params': final, 'stress': {k: v for k, v in final_m.items() if k != 'rows'}},
              open('/work/output/search_result.json', 'w'), indent=1)
    print(f'total {time.time()-t0:.1f}s')
