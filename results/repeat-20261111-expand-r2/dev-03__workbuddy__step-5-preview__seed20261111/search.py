#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (dev-03)."""
import json, sys, time
import numpy as np
sys.path.insert(0, '/opt/gri_bench')
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def make(theta_a, leak, ec50, n, tau, theta_L):
    return {"mode": "responsive",
            "parameters": {"theta_a": theta_a, "relative_leak": leak,
                           "ec50_mg_dl": ec50, "hill_n": n, "tau_min": tau,
                           "theta_L": theta_L}}

if __name__ == '__main__':
    t0 = time.time()
    inst = load_instance()
    exp = Experiment(inst)
    print('build', time.time()-t0)
    for tL in [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]:
        d = make(0.0, 1.0, 200.0, 2.0, 10.0, tL)
        m = exp.evaluate(d)
        print('theta_L=%.2f tir=%.2f tbr70=%.2f tbr54=%.3f min=%.1f evals=%d wall=%.1f'
              % (tL, m['mean_tir'], m['max_trajectory_tbr70'], m['max_trajectory_tbr54'],
                 m['minimum_glucose'], exp.evaluations, time.time()-t0))
