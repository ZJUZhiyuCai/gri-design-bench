#!/usr/bin/env python3
"""Reproducible search for GRI static formulation (dev-02).

Strategy:
1. Load instance; build Experiment with training seeds/variants.
2. Coarse random + local refinement over the responsive parameter space
   (log-spaced for scale parameters), maximizing mean TIR subject to
   safety: TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40 mg/dL.
3. Save best design atomically to /work/output/design.json.
"""
import json, os, random, tempfile
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def score(m):
    # hard safety -> -inf
    if m["tbr70"] > 4.0 or m["tbr54"] > 1.0 or m["min_glucose"] < 40.0:
        return -1.0
    return m["mean_tir"]

def main():
    instance = load_instance()
    exp = Experiment(instance)
    rng = random.Random(0)
    b = instance["bounds"]
    def sample():
        return {
            "theta_a": 10 ** rng.uniform(np.log10(1e-4), np.log10(b["theta_a"][1])),
            "relative_leak": rng.uniform(b["relative_leak"][0], b["relative_leak"][1]),
            "ec50_mg_dl": 10 ** rng.uniform(np.log10(b["ec50_mg_dl"][0]), np.log10(b["ec50_mg_dl"][1])),
            "hill_n": rng.uniform(b["hill_n"][0], b["hill_n"][1]),
            "tau_min": 10 ** rng.uniform(np.log10(b["tau_min"][0]), np.log10(b["tau_min"][1])),
            "theta_L": rng.uniform(b["theta_L"][0], b["theta_L"][1]),
        }
    best, best_s = None, -1.0
    for i in range(60):
        p = sample()
        d = {"mode": "responsive", "parameters": p}
        m = exp.evaluate(d)
        s = score(m)
        if s > best_s:
            best_s, best = s, d
            print(i, s, p, flush=True)
    save_design(best)
    print("BEST", best_s, best)

if __name__ == "__main__":
    main()
