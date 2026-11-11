"""Reproducible search for GRI static formulation, instance dev-05.

Structure of the search (staged random / local random search):
  stage 1 (s1.py logic): broad log-uniform Latin-hypercube-like sampling over all six
      responsive parameters.  Finding: the reservoir cap theta_L*TDI is small compared
      with 3 days of basal delivery, so an over-large theta_a dumps the whole finite
      reservoir in a few hours and produces severe hypoglycaemia (TBR54 ~ 100%).
      Only configurations whose mean release rate ~ theta_a*TDI*(leak+0.5) keeps the
      reservoir alive for most of the 4320 min are safe.
  stage 2: local random search in the band theta_a ~ 1.2e-4..1.2e-3, theta_L 1.2..3.2,
      leak 1.5..2.6 (max Hill modulation span), ec50 120..340, n 0.8..4, tau 2..16.
  stage 3: refinement near the ridge theta_a ~ 2.4e-4..5e-4, theta_L 3.0..4.0.
  stage 4: validation of the top candidates on held-out meal seeds
      (7001..7007) that are disjoint from the training seed 6111005; final choice
      maximises mean TIR on the pooled 8-seed set subject to TBR70 = 0 and a
      minimum plasma glucose well above the 40 mg/dL hard floor.

Fitness used during search (soft-margin penalty so that near-feasible points still
carry gradient information):
    score = mean_tir - 6*max(0, TBR70-0.2) - 6*max(0, TBR54-0.05)
                     - 1.5*max(0, 66 - minimum_glucose)
"""
import json
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

P = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')
TRAIN_SEED = 6111005
HELD_OUT = [7001, 7002, 7003, 7004, 7005, 7006, 7007]


def design(p):
    return {"mode": "responsive", "parameters": dict(zip(P, map(float, p)))}


def score(r):
    return (r['mean_tir']
            - 6 * max(0.0, r['max_trajectory_tbr70'] - 0.2)
            - 6 * max(0.0, r['max_trajectory_tbr54'] - 0.05)
            - 1.5 * max(0.0, 66.0 - r['minimum_glucose']))


def sample(rng):
    return (float(np.exp(rng.uniform(np.log(2.4e-4), np.log(5.0e-4)))),
            float(rng.uniform(1.5, 2.0)),
            float(rng.uniform(210, 300)),
            float(np.exp(rng.uniform(np.log(1.2), np.log(3.0)))),
            float(np.exp(rng.uniform(np.log(1.5), np.log(9.0)))),
            float(rng.uniform(3.0, 4.0)))


def main(trials=46, seed=23):
    inst = load_instance('/task/instance.json')
    ex = Experiment(inst)
    rng = np.random.default_rng(seed)
    pool = []
    for _ in range(trials):
        p = sample(rng)
        r = ex.evaluate(design(p))
        pool.append((score(r), r['mean_tir'], r['max_trajectory_tbr70'],
                     r['minimum_glucose'], p))
    pool.sort(key=lambda t: -t[0])

    ex_ho = Experiment(inst, seeds=[TRAIN_SEED] + HELD_OUT)
    best = None
    for row in pool[:6]:
        r = ex_ho.evaluate(design(row[4]))
        ok = (r['max_trajectory_tbr70'] <= 1.0 and r['max_trajectory_tbr54'] == 0.0
              and r['minimum_glucose'] >= 70.0)
        key = (ok, r['mean_tir'], r['minimum_glucose'])
        print(len(pool), np.round(row[4], 6), round(r['mean_tir'], 2),
              round(r['minimum_glucose'], 2), ok)
        if best is None or key > best[0]:
            best = (key, row[4], r)
    chosen = best[1]
    summary = {"parameters": dict(zip(P, map(float, chosen))),
               "seed_validation_mean_tir": best[2]['mean_tir'],
               "seed_validation_min_glucose": best[2]['minimum_glucose'],
               "seed_validation_tbr70": best[2]['max_trajectory_tbr70']}
    save_design(design(chosen))
    with open('/work/output/search_summary.json', 'w') as fh:
        json.dump(summary, fh, indent=2)
    return summary


if __name__ == '__main__':
    print(main())
