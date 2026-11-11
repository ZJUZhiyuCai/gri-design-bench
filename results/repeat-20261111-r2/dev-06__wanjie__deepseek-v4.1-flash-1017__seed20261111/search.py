"""Reproducible search for the shared-cohort GRI design (dev-06).

Formulation searched: responsive mode
    rate(t) = theta_a*TDI * (relative_leak + Hill(filtered interstitial glucose))
    Hill uses ec50_mg_dl, hill_n and the exact first-order filter tau_min;
    the finite reservoir is theta_L*TDI per 3-day run.

Scoring = mean TIR (post-warmup plasma 70-180) with soft penalties for
approaching the hard safety gates (TBR70<=4%, TBR54<=1%, min minute plasma>=40)
so the selected design keeps margin for fresh meal seeds.
"""
import json, math, time
import numpy as np
from pathlib import Path
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

RNG = np.random.default_rng(20261111)
OUT = Path('/work/output')


def score(m):
    tir = m['mean_tir']
    t70, t54, mn = m['max_trajectory_tbr70'], m['max_trajectory_tbr54'], m['minimum_glucose']
    pen = 0.0
    pen += 8.0 * max(0.0, t70 - 0.0)          # any hypo on training set is a red flag
    pen += 25.0 * max(0.0, t54 - 0.0)
    pen += 2.0 * max(0.0, 55.0 - mn)          # keep glucose floor well above 40
    return tir - pen


def design(v, mode='responsive'):
    if mode == 'constant':
        return {'mode': 'constant', 'parameters': {'theta_c': v[0], 'theta_L': v[1]}}
    return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, v)))}


def sample(b):
    """Bounded random sample with log spacing on the positive scale parameters."""
    a = 10 ** RNG.uniform(math.log10(2e-4), math.log10(1.2e-3))
    leak = RNG.uniform(b['relative_leak'][0], 1.2)
    ec50 = 10 ** RNG.uniform(math.log10(110.0), math.log10(600.0))
    n = RNG.uniform(0.8, b['hill_n'][1])
    tau = RNG.uniform(b['tau_min'][0], b['tau_min'][1])
    L = RNG.choice([2.0, 3.0, 4.0])
    return np.array([a, leak, ec50, n, tau, L])


def gen_boundary(b, v):
    out = v.copy()
    for i, k in enumerate(PARAMETERS):
        lo, hi = b[k]
        out[i] = min(hi, max(lo, out[i]))
    return out


def main(budget_a=56, budget_b=44):
    inst = load_instance(); b = inst['bounds']
    exp = Experiment(inst)
    t0 = time.process_time()
    cache = {}

    def ev(v):
        key = tuple(np.round(v, 12))
        if key not in cache:
            m = exp.evaluate(design(v))
            cache[key] = (score(m), m)
        return cache[key]

    results = []
    for _ in range(budget_a):
        v = gen_boundary(b, sample(b))
        s, m = ev(v)
        results.append((s, v, m))
    results.sort(key=lambda r: -r[0])
    print('stage A best:', [(round(r[0], 2), np.round(r[1], 5).tolist()) for r in results[:5]])

    step = np.array([2e-4, 0.25, 40.0, 0.4, 3.0, 1.0])
    for k in range(budget_b):
        base = results[k % 3][1]
        v = base * (1 + RNG.normal(0, 0.12, size=6)) + RNG.normal(0, 1, 6) * step * 0.15
        v = gen_boundary(b, v)
        s, m = ev(v)
        results.append((s, v, m))
        results.sort(key=lambda r: -r[0])
        results = results[:20]

    results.sort(key=lambda r: -r[0])
    best_s, best_v, best_m = results[0]
    print('total evals', len(cache), 'cpu', round(time.process_time() - t0, 2))
    for s, v, m in results[:8]:
        print(round(s, 2), np.round(v, 6).tolist(),
              {k: round(m[k], 2) for k in ('mean_tir', 'max_trajectory_tbr70', 'max_trajectory_tbr54', 'minimum_glucose')})
    d = design(best_v)
    save_design(d, OUT / 'design.json')
    (OUT / 'search_log.json').write_text(json.dumps(
        {'best': d, 'score': best_s, 'metrics': {k: best_m[k] for k in ('mean_tir', 'max_trajectory_tbr70', 'max_trajectory_tbr54', 'minimum_glucose')},
         'top': [{'params': np.round(v, 8).tolist(), 'score': s} for s, v, _ in results[:10]]}, indent=2))
    return d


if __name__ == '__main__':
    print(main())
