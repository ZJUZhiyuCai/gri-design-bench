"""Reproducible search for the GRI static formulation (dev-04).

Designs a single shared open-loop / glucose-responsive insulin release profile.
No patient-specific coefficients, no online controller, no meal boluses.
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance = load_instance()
BOUNDS = {k: np.array(instance['bounds'][k], dtype=float) for k in PARAMETERS}


def design_from_vector(v, mode='responsive'):
    if mode == 'constant':
        return {'mode': 'constant',
                'parameters': {'theta_c': float(v[0]), 'theta_L': float(v[1])}}
    return {'mode': 'responsive',
            'parameters': {k: float(v[i]) for i, k in enumerate(PARAMETERS)}}


def clip_vector(v, mode='responsive'):
    keys = ('theta_c', 'theta_L') if mode == 'constant' else PARAMETERS
    return np.clip(v, [BOUNDS[k][0] if k in BOUNDS else instance['constant_theta_c_bounds'][0]
                       for k in keys],
                   [BOUNDS[k][1] if k in BOUNDS else instance['constant_theta_c_bounds'][1]
                    for k in keys])


def score(design, experiment=None):
    if experiment is None:
        experiment = Experiment(instance)
    return experiment.evaluate(design)


def main():
    rng = np.random.default_rng(2026111101)
    experiment = Experiment(instance)
    lo = np.array([BOUNDS[k][0] for k in PARAMETERS])
    hi = np.array([BOUNDS[k][1] for k in PARAMETERS])

    # ---- Stage 1: coarse Latin-ish random scan -----------------------------
    best = None
    n_stage = 400
    for i in range(n_stage):
        v = lo + rng.random(len(lo)) * (hi - lo)
        d = design_from_vector(v)
        m = score(d, experiment)
        if m['feasible'] and (best is None or m['mean_tir'] > best[0]):
            best = (m['mean_tir'], d, m)
        elif best is None and m['mean_tir'] > (best[0] if best else -1):
            pass

    # ---- Stage 2: local refinement around the best feasible point ----------
    if best is None:
        # fall back to the least-violating feasible-ish candidate
        v = np.array([0.001, 1.0, 150.0, 2.0, 5.0, 0.8])
        best = (score(design_from_vector(v), experiment)['mean_tir'],
                design_from_vector(v), None)

    sigma = np.array([0.0005, 0.3, 30.0, 0.5, 1.0, 0.05])
    for scale in [0.6, 0.3, 0.12, 0.05, 0.02]:
        for _ in range(120):
            v = np.array([best[1]['parameters'][k] for k in PARAMETERS])
            v = v + scale * sigma * rng.normal()
            v = clip_vector(v)
            d = design_from_vector(v)
            m = score(d, experiment)
            if m['feasible'] and m['mean_tir'] > best[0]:
                best = (m['mean_tir'], d, m)

    # ---- Stage 3: constant-mode sanity check -------------------------------
    for tc in np.linspace(0.0, instance['constant_theta_c_bounds'][1], 25):
        for tL in np.linspace(0.4, 1.25, 10):
            d = {'mode': 'constant', 'parameters': {'theta_c': float(tc), 'theta_L': float(tL)}}
            m = score(d, experiment)
            if m['feasible'] and m['mean_tir'] > best[0]:
                best = (m['mean_tir'], d, m)

    save_design(best[1])
    print(json.dumps({'mean_tir': best[0],
                      'feasible': best[2]['feasible'] if best[2] else None,
                      'max_tbr70': best[2]['max_trajectory_tbr70'] if best[2] else None,
                      'max_tbr54': best[2]['max_trajectory_tbr54'] if best[2] else None,
                      'min_glucose': best[2]['minimum_glucose'] if best[2] else None,
                      'design': best[1]}, indent=2))


if __name__ == '__main__':
    main()
