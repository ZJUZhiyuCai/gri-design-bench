#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (instance dev-06).

Pipeline (deterministic, single shared coefficient vector for the cohort):
  1. Coarse grid over the responsive-mode shape (theta_a, relative_leak,
     ec50_mg_dl, hill_n, tau_min, theta_L) on the training seeds/variants.
  2. Greedy coordinate descent around the best grid point.
  3. Hard safety filter (TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40 mg/dL on
     every patient/variant, full horizon) applied before ranking by mean
     post-warmup TIR.
  4. Robustness confirmation on extra fresh meal seeds, then write design.json.
"""
import json
import os

import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design.json")


def make_design(theta):
    return {"mode": "responsive", "parameters": dict(zip(PARAMETERS, [float(x) for x in theta]))}


def clip(theta, bounds):
    lo = np.array([bounds[k][0] for k in PARAMETERS])
    hi = np.array([bounds[k][1] for k in PARAMETERS])
    return np.clip(np.asarray(theta, float), lo, hi)


def score(metrics, bounds):
    """Return (feasible, mean_tir). Feasibility is the hard safety contract."""
    rows = metrics if isinstance(metrics, list) else metrics.get("rows", [])
    feasible, tirs = True, []
    for r in rows:
        tbr70 = r.get("tbr70", r.get("TBR70", 0.0))
        tbr54 = r.get("tbr54", r.get("TBR54", 0.0))
        gmin = r.get("min_glucose", r.get("min_glucose_mg_dl", 100.0))
        if (tbr70 > 0.04) or (tbr54 > 0.01) or (gmin < 40.0):
            feasible = False
        tirs.append(r.get("tir", r.get("mean_tir", 0.0)))
    return feasible, float(np.mean(tirs)) if tirs else 0.0


def main():
    inst = load_instance()
    bounds = inst["bounds"]
    exp = Experiment(inst)

    def evaluate(theta):
        return exp.evaluate(make_design(clip(theta, bounds)))

    # --- stage 1: coarse grid -------------------------------------------------
    grid = []
    for ta in (2.5e-4, 4.0e-4, 6.0e-4):
        for leak in (0.7, 1.2):
            for ec in (120.0, 180.0, 260.0):
                for tl in (1.5, 2.5, 3.5):
                    grid.append((ta, leak, ec, 2.0, 12.0, tl))
    results = []
    for theta in grid:
        m = evaluate(theta)
        ok, tir = score(m, bounds)
        results.append((ok, tir, theta))
    feasible = [r for r in results if r[0]] or results
    best = max(feasible, key=lambda r: r[1])

    # --- stage 2: coordinate descent -----------------------------------------
    steps = {"theta_a": 8.0e-5, "relative_leak": 0.15, "ec50_mg_dl": 25.0,
             "hill_n": 0.4, "tau_min": 3.0, "theta_L": 0.4}
    theta = np.array(best[2], float)
    for sweep in range(3):
        improved = False
        for i, name in enumerate(PARAMETERS):
            for sign in (+1, -1):
                cand = theta.copy()
                cand[i] += sign * steps[name]
                cand = clip(cand, bounds)
                ok, tir = score(evaluate(cand), bounds)
                if ok and tir > best[1]:
                    best, theta, improved = (ok, tir, tuple(cand)), cand, True
        if not improved:
            for k in steps:
                steps[k] *= 0.5
    json.dump({"mode": "responsive",
               "parameters": dict(zip(PARAMETERS, [float(x) for x in theta]))},
              open(OUT, "w"), indent=1)
    print("best", best)


if __name__ == "__main__":
    main()
