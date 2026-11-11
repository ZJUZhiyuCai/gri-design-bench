#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (instance dev-03).

Maximizes mean post-warmup TIR subject to hard safety constraints
(TBR70<=4%, TBR54<=1%, min glucose>=40 over the full horizon).
Strategy: random search over the responsive box (log-scale for scale
parameters) followed by local Nelder-Mead refinement on a
safety-penalized objective.
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

def score(experiment, design):
    m = experiment.evaluate(design)
    tir = m['mean_tir']
    pen = (50.0*max(0.0, m['max_trajectory_tbr70']-4.0)
           + 50.0*max(0.0, m['max_trajectory_tbr54']-1.0)
           + 500.0*max(0.0, 40.0-m['minimum_glucose']))
    return tir - pen, m

def main():
    instance = load_instance()
    exp = Experiment(instance)
    b = instance['bounds']
    rng = np.random.default_rng(0)

    def sample():
        p = {
            'theta_a': 10**rng.uniform(np.log10(1e-4), np.log10(b['theta_a'][1])),
            'relative_leak': rng.uniform(*b['relative_leak']),
            'ec50_mg_dl': 10**rng.uniform(np.log10(b['ec50_mg_dl'][0]), np.log10(b['ec50_mg_dl'][1])),
            'hill_n': 10**rng.uniform(np.log10(b['hill_n'][0]), np.log10(b['hill_n'][1])),
            'tau_min': 10**rng.uniform(np.log10(b['tau_min'][0]), np.log10(b['tau_min'][1])),
            'theta_L': rng.uniform(*b['theta_L']),
        }
        return {'mode': 'responsive', 'parameters': p}

    best, best_s = None, -1e9
    t0 = time.time()
    for i in range(40):
        d = sample()
        s, m = score(exp, d)
        if s > best_s:
            best_s, best = s, d
            print(i, round(s, 2), m['feasible'], round(m['mean_tir'], 1),
                  round(m['max_trajectory_tbr70'], 2), round(m['max_trajectory_tbr54'], 2),
                  round(m['minimum_glucose'], 1),
                  {k: round(v, 4) for k, v in d['parameters'].items()}, flush=True)
    print('elapsed', round(time.time()-t0, 1), 'best', best_s, flush=True)
    save_design(best)
    print('saved', best)

if __name__ == '__main__':
    main()
