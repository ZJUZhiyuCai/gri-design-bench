#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (dev-01).
Coordinate search over responsive-mode parameters using gri_bench fast RK4 eval."""
import json, time, os, sys
import numpy as np
from gri_bench.api import load_instance, Experiment

OUT = os.path.dirname(os.path.abspath(__file__))
T_START = time.time()
TIME_BUDGET_S = float(os.environ.get("GRI_TIME_BUDGET", "600"))

def penalty(m):
    """score = mean_tir - penalties for unsafe trajectories."""
    rows = m.get("per_trajectory", m.get("rows", []))
    tir = float(m.get("mean_tir", 0.0))
    pen = 0.0
    for r in rows:
        tbr70 = float(r.get("tbr70", r.get("tbr_70", 0.0)))
        tbr54 = float(r.get("tbr54", r.get("tbr_54", 0.0)))
        mn = float(r.get("min_glucose", r.get("min_g", 1e9)))
        if tbr70 > 0.04: pen += 10*(tbr70-0.04) + 1
        if tbr54 > 0.01: pen += 20*(tbr54-0.01) + 1
        if mn < 40.0: pen += 5*(40.0-mn)/40.0 + 1
    return tir - pen, tir, pen

def eval_design(experiment, params):
    d = {"mode": "responsive", "parameters": {k: float(v) for k, v in zip(
        ["theta_a","relative_leak","ec50_mg_dl","hill_n","tau_min","theta_L"], params)}}
    m = experiment.evaluate(d)
    s, tir, pen = penalty(m)
    return s, tir, pen, d, m

def main():
    instance = load_instance()
    experiment = Experiment(instance)
    names = ["theta_a","relative_leak","ec50_mg_dl","hill_n","tau_min","theta_L"]
    best_p = [0.0002, 1.5, 200.0, 2.0, 10.0, 3.0]
    best = eval_design(experiment, best_p)
    print("seed:", best[1], best[2], flush=True)
    steps = {"theta_a":[0.5,0.7,1.0,1.4,2.0],
             "relative_leak":[0.7,0.85,1.0,1.15,1.4],
             "ec50_mg_dl":[0.6,0.8,1.0,1.25,1.6],
             "hill_n":[0.6,0.8,1.0,1.3,1.7],
             "tau_min":[0.5,0.7,1.0,1.4,2.0],
             "theta_L":[0.85,0.95,1.0]}
    improved = True
    rnd = 0
    while improved and time.time()-T_START < TIME_BUDGET_S:
        improved = False; rnd += 1
        for i, nm in enumerate(names):
            for f in steps[nm]:
                if time.time()-T_START > TIME_BUDGET_S: break
                q = list(best_p); q[i] = float(np.clip(q[i]*f, *BOUNDS[nm]))
                r = eval_design(experiment, q)
                if r[0] > best[0] + 1e-9:
                    best, best_p = r, q; improved = True
                    print(f"rnd{rnd} {nm} x{f} -> tir={r[1]:.4f} pen={r[2]:.3f}", flush=True)
                    break
    print("BEST", best_p, best[1], best[2], flush=True)
    with open(os.path.join(OUT,"design.json"),"w") as f:
        json.dump(best[3], f, indent=1)

BOUNDS = {"theta_a":(0.0,0.007), "relative_leak":(0.5124966150526034,5.518918645844859),
          "ec50_mg_dl":(59.26305046791457,816.1143093473472), "hill_n":(0.5880395112623367,24.0),
          "tau_min":(0.05,20.0), "theta_L":(0.4,4.0)}

if __name__ == "__main__":
    main()
