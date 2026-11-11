"""Reproducible search for the GRI static formulation design (instance dev-02).

Formulation family (coefficients shared across the cohort):
  responsive: rate = theta_a*TDI * (relative_leak + Hill(G_filt, ec50, hill_n))
              G_filt: exact first-order filter with tau_min; 3-min midpoint flux
              finite reservoir of theta_L*TDI units over the horizon
  constant  : rate = theta_c*TDI, same reservoir

Objective: maximize mean post-warmup TIR ([70,180] mg/dL) over 3 known patients x
3 training variants, subject to hard safety gates TBR70<=4%, TBR54<=1%, min>=40.
Safety enforced by a large additive penalty (feasible points always dominate).
"""
import json
import time
import numpy as np
from scipy.optimize import minimize
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

OUT = '/work/output'
LO = np.array([0.0, 0.5124966150526034, 59.26305046791457, 0.5880395112623367, 0.05, 0.4])
HI = np.array([0.007, 5.518918645844859, 816.1143093473472, 24.0, 20.0, 4.0])
NCPU = time.process_time


def make_design(mode, x):
    if mode == 'responsive':
        return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, x)))}
    return {'mode': 'constant', 'parameters': {'theta_c': float(x[0]), 'theta_L': float(x[1])}}


class Objective:
    def __init__(self, instance, mode='responsive', penalty=5000.0):
        self.exp = Experiment(instance)
        self.mode = mode
        self.penalty = penalty
        self.best = (-np.inf, None, None)
        self.n = 0

    def __call__(self, x):
        x = np.clip(np.asarray(x, float), LO, HI)
        m = self.exp.evaluate(make_design(self.mode, x))
        pen = 0.0
        if not m['feasible']:
            pen = self.penalty * (1.0
                + max(0.0, m['max_trajectory_tbr70'] - 4.0) / 4.0
                + 20.0 * max(0.0, m['max_trajectory_tbr54'] - 1.0)
                + 50.0 * max(0.0, 40.0 - m['minimum_glucose']))
        score = m['mean_tir'] - pen
        self.n += 1
        if score > self.best[0]:
            self.best = (score, x.copy(), m)
        return score


def random_start(rng):
    return np.array([
        10 ** rng.uniform(np.log10(2e-4), np.log10(6e-3)),   # theta_a
        10 ** rng.uniform(np.log10(0.55), np.log10(4.0)),   # relative_leak
        10 ** rng.uniform(np.log10(90.0), np.log10(700.0)),  # ec50
        10 ** rng.uniform(np.log10(0.8), np.log10(12.0)),   # hill_n
        10 ** rng.uniform(np.log10(0.2), np.log10(20.0)),   # tau_min
        10 ** rng.uniform(np.log10(0.5), np.log10(3.5)),    # theta_L
    ])


def main():
    t0 = time.time()
    instance = load_instance()
    obj = Objective(instance)
    rng = np.random.default_rng(20261111)
    cand = [np.array([3e-4, 0.8, 150., 4., 8., 1.8]),
            np.array([1e-3, 1.0, 200., 6., 6., 2.5]),
            np.array([3e-3, 2.0, 250., 8., 10., 3.0])]
    cand += [random_start(rng) for _ in range(14)]
    for x in cand:
        obj(x)
    best_x = obj.best[1].copy()
    print('stage1 evals', obj.n, 'best', round(obj.best[0], 2), 'cpu', round(NCPU() - t0, 2))
    # local refinement (Nelder-Mead on log-scales where appropriate)
    steps = np.array([0.35, 0.25, 0.3, 0.3, 0.3, 0.2])
    for it in range(4):
        def sh(x):
            return best_x * np.exp(np.clip(x, -3, 3))
        res = minimize(lambda z: -obj(sh(z)), np.zeros(6), method='Nelder-Mead',
                       options={'maxiter': 130, 'xatol': 1e-3, 'fatol': 1e-4,
                                'initial_simplex': np.vstack([np.zeros(6), np.eye(6) * steps])})
        best_x = np.clip(res.x * 0 + best_x, LO, HI)
        print('stage2', it, 'evals', obj.n, 'best', round(obj.best[0], 2), 'cpu', round(NCPU() - t0, 2))
    x = np.clip(obj.best[1], LO, HI)
    d = make_design('responsive', x)
    m = obj.exp.evaluate(d)
    print('FINAL', json.dumps(d))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'rows'})
    for r in m['rows']:
        print(' ', r['patient'], r['variant'], {k: round(v, 2) for k, v in r['metrics'].items()})
    save_design(d)
    json.dump({'design': d, 'metrics': {k: v for k, v in m.items() if k != 'rows'}, 'evaluations': obj.n},
              open(OUT + '/best.json', 'w'), indent=1)
    print('total cpu', round(NCPU() - t0, 2))


if __name__ == '__main__':
    main()
