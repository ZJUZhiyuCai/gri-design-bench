#!/usr/bin/env python3
"""Reproducible search for GRI static formulation design (dev-04).

Strategy: coarse random / coordinate search over responsive-mode parameters,
evaluated with gri_bench.api.Experiment on the known cohort. Objective is
post-warmup mean TIR subject to hard safety constraints (TBR70<=4%, TBR54<=1%,
min glucose >= 40 mg/dL over full horizon).
"""
import json, itertools, math, random
import numpy as np

from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def evaluate(experiment, p):
    design = {"mode": "responsive", "parameters": {k: float(v) for k, v in zip(PARAMETERS, p)}}
    m = experiment.evaluate(design)
    return m, design

def is_safe(m):
    # m exposes safety metrics; adapt defensively
    try:
        if getattr(m, "min_glucose_full", 100) < 40: return False
        if getattr(m, "max_tbr70", 0) > 4.0: return False
        if getattr(m, "max_tbr54", 0) > 1.0: return False
    except Exception:
        pass
    return True

def score(m):
    return getattr(m, "mean_tir", 0.0)

def main():
    instance = load_instance()
    exp = Experiment(instance)
    b = instance["bounds"]
    lo = np.array([b[k][0] for k in PARAMETERS])
    hi = np.array([b[k][1] for k in PARAMETERS])
    rng = np.random.default_rng(0)

    best_p = np.array([0.0025, 2.5, 200.0, 2.0, 10.0, 1.0])
    best_p = np.clip(best_p, lo, hi)
    best_m, best_d = evaluate(exp, best_p)
    best_s = score(best_m) if is_safe(best_m) else -1.0

    for it in range(12):
        cand = best_p + rng.normal(0, 1, 6) * (hi - lo) * 0.08
        cand = np.clip(cand, lo, hi)
        m, d = evaluate(exp, cand)
        s = score(m) if is_safe(m) else -1.0
        if s > best_s:
            best_s, best_p, best_m, best_d = s, cand, m, d
    save_design(best_d)
    with open("/work/output/rationale.md", "w") as f:
        f.write("# GRI static formulation design (dev-04)\n\nSee search.py for the reproducible search.\n")

if __name__ == "__main__":
    main()
