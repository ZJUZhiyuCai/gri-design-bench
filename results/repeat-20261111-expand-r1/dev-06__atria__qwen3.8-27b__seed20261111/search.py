#!/usr/bin/env python3
"""Reproducible search for GRI static formulation (dev-06).

Strategy:
1. Load instance, build Experiment with training seeds/variants.
2. Coarse grid over responsive parameters (theta_a, relative_leak, ec50, hill_n, tau, theta_L).
3. Local refinement (Nelder-Mead / coordinate) maximizing mean TIR subject to
   safety: TBR70<=4%, TBR54<=1%, min glucose >= 40 mg/dL (full horizon).
4. Save best design atomically to /work/output/design.json.
"""
import json, os, tempfile
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def score(metrics):
    # mean TIR after warmup; hard safety penalties
    tir = metrics["mean_tir"]
    tbr70 = metrics["mean_tbr70"]
    tbr54 = metrics["mean_tbr54"]
    mingluc = metrics["min_glucose"]
    if tbr70 > 4.0 or tbr54 > 1.0 or mingluc < 40.0:
        return -1.0
    return tir

def main():
    instance = load_instance()
    exp = Experiment(instance)
    best = None
    # coarse grid
    for theta_a in [0.0002, 0.0005, 0.001, 0.002]:
        for leak in [1.0, 2.0, 3.0]:
            for ec50 in [150.0, 200.0, 250.0]:
                for hill in [1.5, 2.0, 3.0]:
                    for tau in [5.0, 10.0, 15.0]:
                        for theta_L in [0.8, 1.2, 1.6]:
                            d = {"mode":"responsive","parameters":{"theta_a":theta_a,"relative_leak":leak,"ec50_mg_dl":ec50,"hill_n":hill,"tau_min":tau,"theta_L":theta_L}}
                            m = exp.evaluate(d)
                            s = score(m)
                            if best is None or s > best[0]:
                                best = (s, d, m)
    print("best", best[0], best[1])
    save_design(best[1])

if __name__ == "__main__":
    main()
