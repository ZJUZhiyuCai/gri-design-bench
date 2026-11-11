"""Reproducible search for the GRI static responsive design (instance dev-05).

Pipeline
1. broad randomized scan (log/linear mix) scored on the instance training seed;
2. coordinate pattern refinement of the best candidates;
3. robustness selection on extra fresh meal seeds (manufactured seeds, never the
   held-out ones), maximising mean TIR subject to worst-case safety margins;
4. atomic save of the chosen design via gri_bench.api.save_design.

Rate model: rate = theta_a*TDI*[relative_leak + 1/(1+(ec50/mid)^n)], finite
reservoir theta_L*TDI, so the search keeps the leak term near basal and spends
the reservoir on post-meal hyperglycaemia only when it stays safe.
"""
import json, time
import numpy as np
from pathlib import Path
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

INST = load_instance()
KEYS = PARAMETERS
B = INST['bounds']
LO = np.array([B[k][0] for k in KEYS]); HI = np.array([B[k][1] for k in KEYS])
OUT = Path('/work/output')
RNG = np.random.default_rng(20261111)
FRESH = [11, 101, 909]


def design(v):
    return {'mode': 'responsive', 'parameters': {k: float(x) for k, x in zip(KEYS, v)}}


def aggregate(ms):
    """Safety-first aggregate over trajectory summaries."""
    tbr70 = max(m['max_trajectory_tbr70'] for m in ms)
    tbr54 = max(m['max_trajectory_tbr54'] for m in ms)
    mn = min(m['minimum_glucose'] for m in ms)
    tir = float(np.mean([m['mean_tir'] for m in ms]))
    feasible = tbr70 <= 4 and tbr54 <= 1 and mn >= 40
    pen = (max(0., tbr70 - 2)/2 + max(0., tbr54 - 0.25)/0.25
           + max(0., 55. - mn)/55)
    return tir - 80*pen, tir, feasible, mn, tbr70, tbr54


class Scorer:
    def __init__(self, experiment):
        self.exp = experiment; self.cache = {}

    def __call__(self, v):
        key = tuple(np.round(v, 10))
        if key in self.cache:
            return self.cache[key]
        m = self.exp.evaluate(design(v))
        res = aggregate([m])
        self.cache[key] = res
        return res


def random_point():
    return np.array([10**RNG.uniform(np.log10(2e-5), np.log10(8e-4)),
                     RNG.uniform(1.5, 5.5), RNG.uniform(70, 350),
                     10**RNG.uniform(np.log10(0.6), np.log10(20)),
                     RNG.uniform(0.05, 20), RNG.uniform(0.4, 4)])


def pattern_search(f, v0, budget_s, steps=None):
    v = np.clip(np.asarray(v0, float), LO, HI)
    best = f(v)[0]
    if steps is None:
        steps = np.array([3e-5, .4, 25., 1.5, 3., .4])
    t0 = time.time()
    while time.time() - t0 < budget_s and steps[0] > 2e-6:
        improved = False
        for i in range(len(v)):
            for sign in (1., -1.):
                cand = v.copy()
                cand[i] = np.clip(cand[i] + sign*steps[i], LO[i], HI[i])
                s = f(cand)[0]
                if s > best + 1e-9:
                    v, best, improved = cand, s, True
        if not improved:
            steps = steps * 0.5
    return v, best


def main(broad_seconds=6.0, refine_seconds=5.0, validate_seconds=4.0):
    exp = Experiment(INST)
    f = Scorer(exp)
    t0 = time.time(); pool = []
    while time.time() - t0 < broad_seconds:
        v = random_point(); pool.append((f(v)[0], v))
    pool.sort(key=lambda x: -x[0])
    cands = []
    for s, v in pool[:3]:
        print('broad', round(s, 2), np.round(v, 5).tolist(), flush=True)
        cands.append(pattern_search(f, v, refine_seconds / 3.0))
    cands.sort(key=lambda x: -x[1])
    # robustness on fresh manufactured seeds
    fexp = Experiment(INST, seeds=FRESH)
    g = Scorer(fexp)
    t0 = time.time(); checked = []
    for v, s in cands + [(v, s) for s, v in pool[:12]]:
        if time.time() - t0 > validate_seconds * 0.6:
            break
        checked.append((g(v), v))
    checked.sort(key=lambda x: -x[0][0])
    for r, v in checked[:6]:
        print('valid', np.round(r, 2).tolist(), np.round(v, 5).tolist(), flush=True)
    # final refinement against both seed sets, safety first
    def both(v):
        a = f(v); b = g(v)
        return (min(a[0], b[0]),) + tuple(a[1:]) if a[0] < b[0] else (min(a[0], b[0]),) + tuple(b[1:])
    best_v, best_s = pattern_search(both, checked[0][1], validate_seconds * 0.35)
    print('final', round(best_s, 2), np.round(best_v, 5).tolist())
    final = design(best_v)
    print('training', {k: v for k, v in exp.evaluate(final).items() if k != 'rows'})
    print('fresh', {k: v for k, v in fexp.evaluate(final).items() if k != 'rows'})
    save_design(final)
    (OUT / 'search_result.json').write_text(json.dumps(
        {'design': final, 'fresh_seeds': FRESH, 'score': best_s}, indent=2) + '\n')
    return final


if __name__ == '__main__':
    main()
