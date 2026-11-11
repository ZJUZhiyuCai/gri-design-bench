#!/usr/bin/env python3
"""Reproducible two-stage search used for dev-01 (one CPU).

The objective is deliberately more conservative than the benchmark limits:
training and one fresh-seed experiment are both used during refinement, and
candidates are finally compared on three additional meal seeds.  The last
step is a native dopri5 check of the selected design on the training seed.
"""
import json
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance, Experiment, save_design
from gri_bench.native import verify_design

KEYS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')

def design(z):
    values = [np.exp(z[0]), z[1], np.exp(z[2]), np.exp(z[3]), np.exp(z[4]), z[5]]
    return {'mode': 'responsive', 'parameters': dict(zip(KEYS, map(float, values)))}

def conservative_score(metrics_list):
    tir = np.mean([m['mean_tir'] for m in metrics_list])
    tbr70 = max(m['max_trajectory_tbr70'] for m in metrics_list)
    tbr54 = max(m['max_trajectory_tbr54'] for m in metrics_list)
    minimum = min(m['minimum_glucose'] for m in metrics_list)
    return (tir - 50*max(0, tbr70-.5) - 100*max(0, tbr54-.1)
            - 2*max(0, 60-minimum))

def main():
    instance = load_instance()
    train = Experiment(instance)
    bounds = [(np.log(.00012), np.log(.0012)), (.5124966150526034, 2.5),
              (np.log(75), np.log(350)), (np.log(.7), np.log(12)),
              (np.log(.05), np.log(20)), (.45, 2.5)]
    stage1 = differential_evolution(lambda z: -conservative_score([train.evaluate(design(z))]),
        bounds, popsize=5, maxiter=5, tol=.005, polish=False, seed=31415,
        updating='immediate')
    validation1 = Experiment(instance, seeds=[8111001])
    def objective(z):
        return -conservative_score([train.evaluate(design(z)), validation1.evaluate(design(z))])
    local = [(np.log(.00027), np.log(.00043)), (.8, 1.5),
             (np.log(80), np.log(160)), (np.log(2), np.log(8)),
             (np.log(.05), np.log(3)), (1.6, 3.)]
    stage2 = differential_evolution(objective, local, popsize=4, maxiter=3,
        polish=False, seed=2718, x0=stage1.x, updating='immediate')
    candidates = [stage2.x, stage1.x]
    for factor in (.95, 1.025):
        z = stage2.x.copy(); z[0] += np.log(factor); candidates.append(z)
    validation2 = Experiment(instance, seeds=[8111002, 8111003, 8111004])
    selected = max(candidates, key=lambda z: conservative_score([validation2.evaluate(design(z))]))
    result = design(selected)
    save_design(result)
    print(json.dumps(result, indent=2))
    print(verify_design(instance, result, [6111001]))

if __name__ == '__main__':
    main()
