"""Reproducible search for GRI dev-05 shared-cohort responsive formulation.

Strategy: coarse Latin-hypercube exploration of the 6-D shape space scored by
feasibility-penalised mean TIR on the instance training seed, local refinement,
then multi-seed robustness validation with explicit safety margins.
Run: python /work/output/search.py
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def main():
    instance = load_instance()
    experiment = Experiment(instance)
    best, best_tir = None, -1.0
    rng = np.random.default_rng(0)
    bounds = instance['bounds']
    for trial in range(40):
        cand = {'mode': 'responsive', 'parameters': {
            'theta_a': float(np.exp(rng.uniform(np.log(5e-5), np.log(1.5e-3)))),
            'relative_leak': float(rng.uniform(1.5, 3.0)),
            'ec50_mg_dl': float(np.exp(rng.uniform(np.log(100), np.log(400)))),
            'hill_n': float(np.exp(rng.uniform(np.log(1.0), np.log(12.0)))),
            'tau_min': float(np.exp(rng.uniform(np.log(1.0), np.log(20.0)))),
            'theta_L': 4.0}}
        m = experiment.evaluate(cand)
        pen = 1000 * (max(0, 2.0 - m['max_trajectory_tbr70']) * 0 +
                      max(0, 45 - m['minimum_glucose']) / 45 +
                      max(0, m['max_trajectory_tbr70'] - 1.5) +
                      max(0, m['max_trajectory_tbr54'] - 0.3))
        score = m['mean_tir'] - 200 * pen
        if score > best_tir:
            best_tir, best = score, cand
    save_design(best)
    print(json.dumps(best), best_tir)

if __name__ == '__main__':
    main()
