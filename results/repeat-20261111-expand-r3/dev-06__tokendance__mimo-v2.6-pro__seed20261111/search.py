"""Reproducible search for the GRI static formulation (instance dev-06).

Run: python3 /work/output/search.py
Deterministic (fixed seeds, fixed evaluation order); uses only the public
training API in /opt/gri_bench. Writes /work/output/design.json atomically.

Strategy
--------
The shared law is rate = theta_a*TDI*(relative_leak + Hill(G_sc_filtered)),
Hill = 1/(1+exp(n*(log(EC50)-log(G)))).  Cohort basal needs are nearly equal
in U/min while TDI differs ~2x, so per-TDI need spans ~2x.  We therefore use
the widest feedback dynamic range: relative_leak near its lower bound, with
the Hill term providing the patient-specific, glucose-negative-feedback part.
The floor must be <= the most TDI-over-scaled patient's basal (child#005),
the ceiling must cover meals for the least-scaled ones.  Reservoir theta_L
caps 3-day delivery against stacking.  Search: seeded random coarse sample,
then coordinate pattern search on training scenarios; finalists are checked
on fresh meal seeds for robustness before selection.
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

SEED = 2026111101
RNG_SEED = 6111
COARSE_EVALS = 90
REFINE_EVALS = 70
VAL_SEEDS = (7331, 9152)          # fresh meal seeds, selection-only robustness check

BOUNDS = {
    'theta_a': (0.0, 0.007),
    'relative_leak': (0.5124966150526034, 5.518918645844859),
    'ec50_mg_dl': (59.26305046791457, 816.1143093473472),
    'hill_n': (0.5880395112623367, 4.0),
    'tau_min': (2.0, 20.0),
    'theta_L': (0.4, 4.0),
}
SCALES = {'theta_a': 8e-5, 'relative_leak': 0.25, 'ec50_mg_dl': 35.0,
          'hill_n': 0.6, 'tau_min': 1.5, 'theta_L': 0.4}


def clip(v):
    return {k: float(min(max(v[k], BOUNDS[k][0]), BOUNDS[k][1])) for k in PARAMETERS}


def score(m):
    """Robustness-first scalar: hard safety, then safety margin, then mean TIR."""
    if m['minimum_glucose'] < 40 or m['max_trajectory_tbr70'] > 4 or m['max_trajectory_tbr54'] > 1:
        pen = (2.0 * max(0.0, m['max_trajectory_tbr70'] - 4.0)
               + 20.0 * max(0.0, m['max_trajectory_tbr54'] - 1.0)
               + 1.0 * max(0.0, 40.0 - m['minimum_glucose']))
        return -1000.0 - pen
    margin = (min(3.0, m['minimum_glucose'] - 50.0)
              + min(3.0, 2.0 - 0.5 * m['max_trajectory_tbr70'])
              + min(3.0, 1.0 - 2.0 * m['max_trajectory_tbr54']))
    return m['mean_tir'] + margin


def main():
    instance = load_instance()
    train = Experiment(instance)
    valid = Experiment(instance, seeds=list(VAL_SEEDS))
    rng = np.random.default_rng(RNG_SEED)
    seen = {}

    def evaluate(v):
        v = clip(v)
        key = tuple(round(v[k], 9) for k in PARAMETERS)
        if key in seen:
            return seen[key]
        m = train.evaluate({'mode': 'responsive', 'parameters': v})
        seen[key] = (m, score(m))
        return seen[key]

    # ---- coarse seeded random sample inside a physiologically-informed box ----
    best_v, best_m, best_s = None, None, -np.inf
    for _ in range(COARSE_EVALS):
        v = {
            'theta_a': rng.uniform(0.00018, 0.00060),
            'relative_leak': rng.uniform(0.5125, 1.4),
            'ec50_mg_dl': rng.uniform(110.0, 240.0),
            'hill_n': rng.uniform(1.0, 3.2),
            'tau_min': rng.uniform(2.0, 9.0),
            'theta_L': rng.uniform(2.2, 3.8),
        }
        m, s = evaluate(v)
        if s > best_s:
            best_v, best_m, best_s = dict(v), m, s

    # ---- coordinate pattern search with step halving ----
    steps = dict(SCALES)
    stall = 0
    while stall < 3:
        improved = False
        for k in list(rng.permutation(np.array(PARAMETERS, dtype=object))):
            for direction in (1.0, -1.0):
                cand = dict(best_v)
                cand[k] = best_v[k] + direction * steps[k]
                if abs(clip(cand)[k] - best_v[k]) < 1e-12:
                    continue
                m, s = evaluate(cand)
                if s > best_s + 1e-9:
                    best_v, best_m, best_s = clip(cand), m, s
                    improved = True
        if improved:
            stall = 0
        else:
            stall += 1
            for k in steps:
                steps[k] *= 0.5

    # ---- robustness check on fresh meal seeds; fall back to best margins ----
    finalists = sorted(seen.items(), key=lambda kv: -kv[1][1])[:6]
    chosen_v, chosen_key, chosen_row = best_v, None, None
    best_val = -np.inf
    for key, (m, s) in finalists:
        v = dict(zip(PARAMETERS, key))
        mv = valid.evaluate({'mode': 'responsive', 'parameters': v})
        vs = score(mv)
        print(json.dumps({'candidate': v, 'val_mean_tir': round(mv['mean_tir'], 2),
                          'val_max_tbr70': round(mv['max_trajectory_tbr70'], 2),
                          'val_max_tbr54': round(mv['max_trajectory_tbr54'], 2),
                          'val_min': round(mv['minimum_glucose'], 1)}))
        if vs > best_val:
            best_val, chosen_v, chosen_key, chosen_row = v, v, key, (m, mv)

    design = {'mode': 'responsive', 'parameters': {k: float(chosen_v[k]) for k in PARAMETERS}}
    save_design(design)
    m, mv = chosen_row
    print(json.dumps({'chosen': design['parameters'],
                      'train_mean_tir': round(m['mean_tir'], 2),
                      'train_max_tbr70': round(m['max_trajectory_tbr70'], 2),
                      'train_max_tbr54': round(m['max_trajectory_tbr54'], 2),
                      'train_min': round(m['minimum_glucose'], 1),
                      'val_mean_tir': round(mv['mean_tir'], 2),
                      'val_max_tbr70': round(mv['max_trajectory_tbr70'], 2),
                      'val_max_tbr54': round(mv['max_trajectory_tbr54'], 2),
                      'val_min': round(mv['minimum_glucose'], 1),
                      'train_evals': train.evaluations}, indent=2))


if __name__ == '__main__':
    main()
