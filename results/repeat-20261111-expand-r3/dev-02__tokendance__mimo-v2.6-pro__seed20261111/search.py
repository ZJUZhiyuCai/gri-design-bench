#!/usr/bin/env python3
"""Reproducible search for GRI static formulation (dev-02).

Strategy: coordinate refinement around a safe seed, maximizing mean TIR70-180
subject to hard safety constraints (TBR70<=4%, TBR54<=1%, min glucose >= 40).
Uses gri_bench.api Experiment with the instance's training seed/variants.
"""
import json, math, random
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

SEED = 12345

def clip(v, lo, hi):
    return max(lo, min(hi, v))

def make_design(x):
    return {"mode": "responsive",
            "parameters": {k: float(v) for k, v in zip(PARAMETERS, x)}}

def feasible(m):
    return (m["max_tbr70"] <= 4.0 + 1e-9 and m["max_tbr54"] <= 1.0 + 1e-9
            and m["min_glucose"] >= 40.0 - 1e-9)

def score(m):
    if not feasible(m):
        return -1e6 + 1000.0 * max(0.0, m["max_tbr70"] - 4.0) \
               + 1000.0 * max(0.0, m["max_tbr54"] - 1.0) \
               + 1000.0 * max(0.0, 40.0 - m["min_glucose"])
    return m["mean_tir"]

def main():
    instance = load_instance()
    b = instance["bounds"]
    lo = [b[p][0] for p in PARAMETERS]
    hi = [b[p][1] for p in PARAMETERS]
    exp = Experiment(instance)
    rng = random.Random(SEED)

    x = [0.002, 2.0, 180.0, 2.0, 10.0, 2.0]
    best = score(exp.evaluate(make_design(x)))
    print("seed", best, flush=True)
    # coordinate refinement
    step = [0.5 * (h - l) for l, h in zip(lo, hi)]
    for it in range(6):
        improved = False
        for i in range(len(x)):
            for sgn in (1.0, -1.0):
                cand = list(x)
                cand[i] = clip(x[i] + sgn * step[i], lo[i], hi[i])
                sc = score(exp.evaluate(make_design(cand)))
                if sc > best:
                    best, x, improved = sc, cand, True
        if not improved:
            step = [s * 0.5 for s in step]
    d = make_design(x)
    print(json.dumps(d), best, flush=True)
    save_design(d)

if __name__ == "__main__":
    main()
