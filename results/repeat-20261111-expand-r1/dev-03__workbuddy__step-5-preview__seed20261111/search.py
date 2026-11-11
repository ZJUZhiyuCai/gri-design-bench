"""Static GRI formulation search -- instance dev-03 (children #001-#003).

Objective: maximize mean TIR (plasma glucose in [70,180] mg/dL over post-warmup
days 2-3) across the known cohort, subject to the safety contract
(max trajectory TBR70 <= 4%, TBR54 <= 1%, minimum minute glucose >= 40 mg/dL
over the full 3-day horizon).

Design space: the shared responsive 6-tuple
    (theta_a, relative_leak, ec50_mg_dl, hill_n, tau_min, theta_L)
with rate = theta_a*TDI*[leak + Hill(filtered G)] and a finite load
theta_L*TDI, all within the instance bounds.  No per-patient coefficients.

Search: (1) Sobol/random exploration of the box, (2) local pattern search with
shrinking steps on a safety-margined objective, (3) robustness re-ranking of the
best candidates on extra meal seeds so the choice is not tuned to one seed.
"""
import json
import time

import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

KEYS = list(PARAMETERS)
LO = np.array([load_instance()['bounds'][k][0] for k in KEYS])
HI = np.array([load_instance()['bounds'][k][1] for k in KEYS])
SPAN = HI - LO

WALL_LIMIT = 55.0          # seconds of wall time for the whole search
START = time.time()


def design_of(x):
    x = np.clip(np.asarray(x, float), LO, HI)
    return {"mode": "responsive",
            "parameters": {k: float(v) for k, v in zip(KEYS, x)}}


def objective(m):
    """Safety-margined score; infeasible designs get a large negative penalty."""
    pen = 0.0
    pen += 600.0 * max(0.0, m['max_trajectory_tbr70'] - 4.0)
    pen += 600.0 * max(0.0, m['max_trajectory_tbr54'] - 1.0)
    pen += 600.0 * max(0.0, 40.5 - m['minimum_glucose'])
    return m['mean_tir'] - pen


def run_search():
    instance = load_instance()
    exp = Experiment(instance)
    rng = np.random.default_rng(12345)

    # ---------- stage 1: random / structured exploration ----------
    best_x, best_s = None, -1e9
    n_random = 260
    for i in range(n_random):
        x = LO + rng.random(6) * SPAN
        # bias the physically meaningful directions: moderate amplitude, small
        # leak, EC50 near the middle of the target band, moderate steepness.
        if i % 3 == 0:
            x[0] = rng.uniform(0.0002, 0.0012)
        if i % 3 == 1:
            x[1] = rng.uniform(0.5125, 1.6)
            x[2] = rng.uniform(90.0, 200.0)
            x[3] = rng.uniform(2.0, 10.0)
            x[4] = rng.uniform(2.0, 20.0)
        if i % 5 == 0:
            x[5] = rng.uniform(2.0, 4.0)
        s = objective(exp.evaluate(design_of(x)))
        if s > best_s:
            best_s, best_x = s, x.copy()
    print("[random] best score %.3f  x=%s" % (best_s, np.round(best_x, 5)), flush=True)

    # ---------- stage 2: local pattern search ----------
    steps = SPAN * np.array([0.25, 0.25, 0.25, 0.25, 0.25, 0.25])
    x, s = best_x.copy(), best_s
    while time.time() - START < WALL_LIMIT * 0.55 and steps.max() > 1e-7:
        improved = False
        for j in range(6):
            for sgn in (1.0, -1.0):
                if time.time() - START > WALL_LIMIT * 0.6:
                    break
                y = x.copy()
                y[j] = np.clip(y[j] + sgn * steps[j], LO[j], HI[j])
                sy = objective(exp.evaluate(design_of(y)))
                if sy > s + 1e-9:
                    x, s, improved = y, sy, True
                    break
        if not improved:
            steps *= 0.5
    print("[local]  best score %.3f  x=%s" % (s, np.round(x, 5)), flush=True)
    return x, s, exp, instance


def robustness(x, instance, seeds):
    """Evaluate on fresh meal seeds (same 3 challenge variants)."""
    exp2 = Experiment(instance, seeds=seeds)
    return exp2.evaluate(design_of(x))


def main():
    x, s, exp, instance = run_search()

    # ---------- stage 3: robustness re-ranking over extra seeds ----------
    extra = [777001, 777002, 777003]
    cands = []
    # the search optimum plus small perturbations, to pick a robust one
    rng = np.random.default_rng(7)
    cands.append(x.copy())
    for k in range(10):
        y = x.copy()
        for j in range(6):
            y[j] = np.clip(y[j] + rng.normal(0, 0.02 * SPAN[j]), LO[j], HI[j])
        cands.append(y)
    scored = []
    for y in cands:
        m = exp.evaluate(design_of(y))
        r = robustness(y, instance, extra)
        # robust score: worst-case over seeds of (tir - penalty)
        worst = objective(r)
        scored.append((worst, objective(m), y, r))
        print("[robust] cand worst=%8.3f train=%8.3f seedTIR=%6.2f feas=%s" %
              (worst, objective(m), r['mean_tir'], r['feasible']), flush=True)
    scored.sort(key=lambda t: -t[0])
    worst, train_s, bx, r = scored[0]

    m = exp.evaluate(design_of(bx))
    print("[final train]", {k: m[k] for k in
                            ('mean_tir', 'max_trajectory_tbr70',
                             'max_trajectory_tbr54', 'minimum_glucose', 'feasible')})
    print("[final extra]", {k: r[k] for k in
                            ('mean_tir', 'max_trajectory_tbr70',
                             'max_trajectory_tbr54', 'minimum_glucose', 'feasible')})
    save_design(design_of(bx))
    print("elapsed", time.time() - START)
    print(json.dumps(design_of(bx)))


if __name__ == '__main__':
    main()
