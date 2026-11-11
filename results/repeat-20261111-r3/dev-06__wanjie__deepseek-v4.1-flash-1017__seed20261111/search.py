"""Reproducible search for GRI responsive-rate design (instance dev-06).

Mechanism notes from probing physiology:
 * rate = theta_a * TDI * (relative_leak + sigmoid(n*ln(G_filt/EC50))), reservoir theta_L*TDI U.
 * Fasting insulin need is nearly identical in ABSOLUTE units (~11-14 U/day) for child#004/005/006
   although TDI is 19.8 / 40.9 / 20.2, so the TDI scaling is ~2x generous for child#005 and the
   glucose feedback has to correct it. That favours leak at its lower bound plus a high-EC50 and
   steep Hill term, so only clearly hyperglycaemic excursions earn extra insulin.
 * Saturation ceiling / floor ratio is fixed by TDI ratios, so amplitude is tuned just below the
   point where child#005's floor dose exceeds its basal need (hypo risk).
Objective: mean TIR with safety penalties and an explicit minimum-glucose margin for new seeds.
"""
import time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

BOUNDS = {'theta_a': (0.0, 0.007), 'relative_leak': (0.5124966150526034, 5.518918645844859),
          'ec50_mg_dl': (59.26305046791457, 816.1143093473472), 'hill_n': (0.5880395112623367, 4.0),
          'tau_min': (2.0, 20.0), 'theta_L': (0.4, 4.0)}
LO = np.array([BOUNDS[k][0] for k in PARAMETERS]); HI = np.array([BOUNDS[k][1] for k in PARAMETERS])
INSTANCE = load_instance()
EXPERIMENT = Experiment(INSTANCE)
SAFETY_MIN = 82.0


def design(x):
    return {'mode': 'responsive', 'parameters': {k: float(np.clip(v, LO[i], HI[i])) for i, (k, v) in enumerate(zip(PARAMETERS, x))}}


def score(m):
    p = 4.0 * m['max_trajectory_tbr70'] + 20.0 * m['max_trajectory_tbr54']
    p += 0.6 * max(0.0, SAFETY_MIN - m['minimum_glucose'])
    return m['mean_tir'] - p


def main(budget_s=12.0):
    t0 = time.time(); rng = np.random.default_rng(20261111)
    lo = np.array([1.2e-4, 0.512, 90.0, 0.7, 2.0, 2.2])
    hi = np.array([8.0e-4, 2.0, 816.0, 4.0, 20.0, 4.0])
    cache = {}

    def ev(x):
        x = np.clip(x, LO, HI); key = tuple(np.round(x, 9))
        if key not in cache:
            m = EXPERIMENT.evaluate(design(x)); cache[key] = (score(m), x, m)
        return cache[key]

    for _ in range(150):
        if time.time() - t0 > budget_s * 0.65: break
        x = lo + (hi - lo) * rng.random(6)
        x[0] = np.exp(rng.uniform(np.log(lo[0]), np.log(hi[0])))
        x[2] = np.exp(rng.uniform(np.log(lo[2]), np.log(hi[2])))
        x[4] = np.exp(rng.uniform(np.log(lo[4]), np.log(hi[4])))
        ev(x)
    ranked = sorted(cache.values(), key=lambda r: -r[0])[:4]
    scales = np.array([2e-4, 0.35, 90.0, 0.7, 4.0, 0.6])
    tick = 0
    while time.time() - t0 < budget_s and tick < 400:
        tick += 1
        base = ranked[tick % len(ranked)][1]
        shrink = 0.5 ** (1 + tick // 120)
        x = base + rng.normal(0, 1, 6) * scales * shrink
        r = ev(x)
        if r[0] > ranked[-1][0]:
            ranked = sorted(ranked + [r], key=lambda z: -z[0])[:4]
    best = ranked[0]
    save_design(design(best[1]))
    m = best[2]
    print('score', round(best[0], 2), design(best[1])['parameters'])
    print('mean_tir', round(m['mean_tir'], 2), 'tbr70', round(m['max_trajectory_tbr70'], 2),
          'tbr54', round(m['max_trajectory_tbr54'], 2), 'min_g', round(m['minimum_glucose'], 1),
          'evals', EXPERIMENT.evaluations)
    for r in m['rows']:
        print(r['patient'], r['variant'], {k: round(v, 1) for k, v in r['metrics'].items()})


if __name__ == '__main__':
    main()
