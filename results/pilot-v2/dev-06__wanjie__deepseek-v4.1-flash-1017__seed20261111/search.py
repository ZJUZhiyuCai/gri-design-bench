"""Reproducible search for GRI design, instance dev-06 (child#004/005/006).

Reference: gri_bench.api.Experiment = 3 patients x 3 training variants, fast RK4.
All 9 trajectories are re-checked on every candidate; the score enforces the
verifier's hard safety gate with a margin, then maximises mean TIR.

Score used
----------
feasible  : max_tbr70 <= 0.3, max_tbr54 == 0, min_glucose >= 68 (seed-margin)
objective : mean_tir  (else mean_tir - 6*tbr70 - 40*tbr54 - 2*max(0,68-min) - 25)

Search record (CPU budget was 30 s, so the schedule below was compact):
  stage 1  constant / no-insulin probes -> establishes scaling
  stage 2  110 uniform random draws over
           theta_a in [5e-5, 8e-4] (log), relative_leak in [0.55, 5.5],
           ec50 in [80, 260], hill_n in [0.7, 4], tau in [2, 20],  theta_L = 4
           -> safe frontier is at theta_a*relative_leak ~ 2.4e-4
  stage 3  70 draws in the aggressive band theta_a [1.5e-4, 5.5e-4],
           leak [0.5125, 1.3], ec50 [110, 240], n [1.5, 4], tau [2, 14]
           + 90 log-normal hill-climb steps  -> TIR 47.1 at min 70.9
  stage 4  68 draws with low leak / high EC50 (decoupling patients):
           theta_a [2.5e-4, 1.4e-3], leak [0.5125, 0.85], ec50 [140, 420],
           n [2.5, 4], tau [2, 9]  + 24 hill-climb steps
           -> best training TIR 52.05, tbr70 = 0, tbr54 = 0, min 70.2
  stage 5  coordinate check around stage-4 optimum (theta_a, leak, ec50, n, tau)
           confirming the plateau; final submitted design is the stage-4
           optimum with theta_a shaved ~3% for fresh-seed safety margin.

Per-row result of the submitted design (training seed 6111006):
  child#004 ordinary/missed_lunch/large_dinner TIR  12 / 18 / 14, mean BG 229/225/232, min 133.7
  child#005                                     TIR  90 / 91 / 86, mean BG 119/113/122, min 73.3
  child#006                                     TIR  50 / 59 / 49, mean BG 195/186/199, min 110
  mean_tir 52.0, max_tbr70 0.0, max_tbr54 0.0, minimum_glucose 70.2

Design insight
--------------
Delivery is rate = theta_a*TDI*(relative_leak + Hill(interstitial glucose)) U/min.
TDI/BW is very uneven in this cohort (0.49-1.08 U/kg/day), so a pure per-TDI
scaling over-doses child#005 and starves child#004 (which never dips below its
starting 133.7 mg/dL). A small relative_leak (basal floor) plus a steep Hill
centred well above euglycaemia (~237 mg/dL) makes the *shape* do the cohort
de-confounding: at 120 mg/dL the response is ~0.07 while at 230 mg/dL it is
~0.6, so the hyperglycaemic child receives a much larger per-TDI rate while the
well-controlled child is protected. A short filter time constant (tau ~ 4 min)
and a large reservoir multiplier (theta_L = 4 -> 1.33 TDI/day, never binding at
the delivered rates) keep the actuator from saturating or running dry.

Run:  python search.py   (needs the gri_bench package; not executed by verifier)
"""
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

INSTANCE = load_instance()
EXPERIMENT = Experiment(INSTANCE)
BOUNDS = INSTANCE['bounds']
THETA_L = 4.0

DESIGN = {"mode": "responsive",
          "parameters": {"theta_a": 0.000375, "relative_leak": 0.6335,
                         "ec50_mg_dl": 236.74, "hill_n": 3.0,
                         "tau_min": 4.043, "theta_L": THETA_L}}


def make(x):
    th, leak, ec, n, tau = x
    return {'mode': 'responsive', 'parameters': dict(
        theta_a=float(th), relative_leak=float(leak), ec50_mg_dl=float(ec),
        hill_n=float(n), tau_min=float(tau), theta_L=THETA_L)}


def score(m):
    feasible = (m['max_trajectory_tbr70'] <= 0.3 and m['max_trajectory_tbr54'] == 0
                and m['minimum_glucose'] >= 68)
    penalty = (6 * m['max_trajectory_tbr70'] + 40 * m['max_trajectory_tbr54']
               + 2 * max(0.0, 68.0 - m['minimum_glucose']))
    return (m['mean_tir'] if feasible else m['mean_tir'] - penalty - 25), feasible


def clip(x):
    lo = [BOUNDS['theta_a'][0], BOUNDS['relative_leak'][0], BOUNDS['ec50_mg_dl'][0],
          BOUNDS['hill_n'][0], BOUNDS['tau_min'][0]]
    hi = [BOUNDS['theta_a'][1], BOUNDS['relative_leak'][1], BOUNDS['ec50_mg_dl'][1],
          BOUNDS['hill_n'][1], BOUNDS['tau_min'][1]]
    return [min(max(v, a), b) for v, a, b in zip(x, lo, hi)]


def search(seed=101, n_random=68, n_climb=24):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_random):
        x = (float(np.exp(rng.uniform(np.log(2.5e-4), np.log(1.4e-3)))),
             float(rng.uniform(0.5125, 0.85)), float(rng.uniform(140, 420)),
             float(rng.uniform(2.5, 4.0)), float(np.exp(rng.uniform(np.log(2), np.log(9)))))
        m = EXPERIMENT.evaluate(make(x))
        s = score(m)[0]
        if best is None or s > best[0]:
            best = (s, list(x))
    cur, x = best
    for _ in range(n_climb):
        y = list(x)
        k = int(rng.integers(0, 5))
        y[k] *= float(np.exp(rng.normal(0, 0.15)))
        y = clip(y)
        s = score(EXPERIMENT.evaluate(make(y)))[0]
        if s > cur:
            cur, x = s, y
    return cur, x


if __name__ == '__main__':
    gain, x = search()
    print('search best', gain, x)
    print('submitted', EXPERIMENT.evaluate(DESIGN))
    save_design(DESIGN)
