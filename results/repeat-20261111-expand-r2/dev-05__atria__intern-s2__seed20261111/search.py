"""Reproducible search for the dev-05 GRI static formulation.

Only /work/output/design.json is used by the verifier. This script is retained for audit.
"""
import json
import itertools
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance = load_instance()
exp = Experiment(instance)

def design_from(mode, values):
    return {"mode": mode, "parameters": dict(values)}

def evaluate(design):
    return exp.evaluate(design)

# --- coarse scan -----------------------------------------------------------
candidates = []
theta_a_grid = [0.0002, 0.00035, 0.0005, 0.0007, 0.001]
leak_grid = [1.5, 2.0, 2.5]
ec50_grid = [90.0, 110.0, 130.0, 150.0]
n_grid = [1.0, 2.0, 3.0]
tau_grid = [3.0, 5.0, 10.0]
L_grid = [1.0, 1.5, 2.0, 2.5]

for ta, lk, ec, n, tau, L in itertools.product(theta_a_grid, leak_grid, ec50_grid,
                                               n_grid, tau_grid, L_grid):
    d = design_from("responsive", dict(zip(PARAMETERS, [ta, lk, ec, n, tau, L])))
    m = evaluate(d)
    candidates.append((m, d))
    if m["feasible"]:
        print("FEASIBLE", m["mean_tir"], d["parameters"])

feasible = [(m, d) for m, d in candidates if m["feasible"]]
if feasible:
    best_m, best_d = max(feasible, key=lambda x: x[0]["mean_tir"])
else:
    best_m, best_d = candidates[0]

print("BEST", best_m["mean_tir"], best_m, best_d["parameters"])
save_design(best_d)
print("saved", best_d)
