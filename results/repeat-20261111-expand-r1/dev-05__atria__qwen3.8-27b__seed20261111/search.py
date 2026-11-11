"""Reproducible search for the GRI static formulation (dev-05).

Runs a coarse-to-fine search over the responsive parameter space using the
public fast RK4 API, then saves the best feasible design atomically.
"""
import json, itertools, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

def score(exp, design):
    m = exp.evaluate(design)
    # safe_tir is 0 when any safety constraint is violated
    return m['safe_tir'], m

def main():
    inst = load_instance()
    exp = Experiment(inst)
    t0 = time.time()
    best = None; best_val = -1.0
    grid = {
        'theta_a': [0.0003, 0.00046, 0.0007, 0.001],
        'relative_leak': [1.5, 2.0, 3.0],
        'ec50_mg_dl': [120.0, 160.0, 200.0],
        'hill_n': [1.5, 3.0, 6.0],
        'tau_min': [8.0, 12.0],
        'theta_L': [4.0],
    }
    keys = list(grid)
    for combo in itertools.product(*[grid[k] for k in keys]):
        design = {'mode': 'responsive', 'parameters': dict(zip(keys, combo))}
        val, m = score(exp, design)
        if val > best_val:
            best_val, best = val, design
            print(f"t={time.time()-t0:5.1f} val={val:6.2f} {dict(zip(keys,combo))} "
                  f"tbr70={m['max_trajectory_tbr70']:.2f} tbr54={m['max_trajectory_tbr54']:.2f} "
                  f"min={m['minimum_glucose']:.1f}", flush=True)
    print("BEST", best_val, best, flush=True)
    save_design(best)

if __name__ == '__main__':
    main()
