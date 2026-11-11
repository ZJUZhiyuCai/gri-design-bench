"""Reproducible search for the GRI static formulation, instance dev-05.

Design family (fixed by the benchmark): responsive Hill release
    rate(t) = theta_a * TDI * [relative_leak + 1/(1 + (ec50 / G_filt)^n)]
with exact first-order interstitial filtering (tau_min), 3-min midpoint flux and
a finite reservoir theta_L * TDI (U).  Coefficients are shared cohort-wide.

Search pipeline (3 stages, all evaluated with gri_bench.api.Experiment)
  S1  random search, 96 samples, mixed log/linear parameterisation, over
      (theta_a, relative_leak, ec50, hill_n, tau); theta_L pinned at its upper
      bound 4.0 (the reservoir is only a cap, so a large load never binds while
      tiny loads risk mid-horizon starvation).
  S2  coordinate hill-climb (9 rounds, shrink-on-stall) from the 3 best S1
      points, 5-D, log steps for theta_a / ec50 / tau.
  S3  safety scaling: the TIR optimum sits exactly on the 70 mg/dL fasting
      plateau, which is a knife edge (the hard gate is TBR70 > 4 % -> 0).  The
      amplitude is therefore rescaled on a grid a * theta_a and validated on
      held-out meal seeds (6111013..6111016, unused by S1/S2) to buy a fasting
      margin.  Selection rule: highest mean TIR with worst-case minimum glucose
      >= 74.5 mg/dL, worst TBR70 <= 0.2 %, worst TBR54 <= 0.05 %.

Objective for S1/S2 (safety-margin-penalised TIR, keeps the search strictly
inside the feasible region instead of hugging the gate):
    score = TIR - 60*max(0, TBR70-2) - 300*max(0, TBR54-0.2)
                - 4*max(0, 60 - min_glucose) - 1000*[min_glucose < 45]

Observed (findings that shaped the final design)
  * The optimum is a near-constant infusion: large relative_leak (5.34) with a
    saturated Hill term (ec50 at its lower bound, 59.3; n 4.3).  Feedback
    authority is intrinsically small because relative_leak >= 1.5 caps the
    high/low rate ratio at 2.5/1.5 = 1.67x, and the model prefers that tiny
    modulation plus a leak-dominated baseline.
  * Fasting plateau glucose moves ~1.45 mg/dL per 1 % change in theta_a, so the
    hard gate is reached at only +6 % amplitude (TBR70 = 14.6 % at a = 1.01).
    This is why stage S3 exists and why the submitted amplitude is ~5 % below
    the TIR optimum.
"""
import json
import math
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

INST = load_instance()
B = INST['bounds']
THETA_L = B['theta_L'][1]
RNG = np.random.default_rng(7)
SHAPE = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min')


def to_design(v, amp=1.0):
    p = dict(zip(SHAPE, v))
    p['theta_a'] = p['theta_a'] * amp
    p['theta_L'] = THETA_L
    return {'mode': 'responsive', 'parameters': p}


def score(m):
    return (m['mean_tir']
            - 60.0 * max(0.0, m['max_trajectory_tbr70'] - 2.0)
            - 300.0 * max(0.0, m['max_trajectory_tbr54'] - 0.2)
            - 4.0 * max(0.0, 60.0 - m['minimum_glucose'])
            - (1000.0 if m['minimum_glucose'] < 45 else 0.0))


def clip(v):
    return [min(max(v[0], B['theta_a'][0]), B['theta_a'][1]),
            min(max(v[1], B['relative_leak'][0]), B['relative_leak'][1]),
            min(max(v[2], B['ec50_mg_dl'][0]), B['ec50_mg_dl'][1]),
            min(max(v[3], B['hill_n'][0]), B['hill_n'][1]),
            min(max(v[4], B['tau_min'][0]), B['tau_min'][1])]


def main():
    exp = Experiment(INST)                      # training seed 6111005, 3 variants
    cache = {}

    def evaluate(v):
        key = tuple(round(x, 10) for x in v)
        if key not in cache:
            m = exp.evaluate(to_design(v))
            cache[key] = (score(m), m)
        return cache[key]

    # ---- S1 random search -------------------------------------------------
    pool = []
    for _ in range(96):
        v = clip([10 ** RNG.uniform(math.log10(3e-5), math.log10(B['theta_a'][1])),
                  RNG.uniform(*B['relative_leak']),
                  math.exp(RNG.uniform(math.log(B['ec50_mg_dl'][0]), math.log(B['ec50_mg_dl'][1]))),
                  math.exp(RNG.uniform(math.log(B['hill_n'][0]), math.log(18.0))),
                  math.exp(RNG.uniform(math.log(0.5), math.log(B['tau_min'][1])))])
        s, _ = evaluate(v)
        pool.append((s, v))
    pool.sort(key=lambda r: -r[0])

    # ---- S2 coordinate hill-climb ----------------------------------------
    best = pool[0]
    for _, v0 in pool[:3]:
        v, s = list(v0), evaluate(v0)[0]
        st = np.full(5, 0.25)
        for _ in range(9):
            moved = False
            for i in range(5):
                for sgn in (1.0, -1.0):
                    c = list(v)
                    if i in (0, 2, 4):
                        c[i] *= math.exp(sgn * st[i])
                    else:
                        c[i] += sgn * st[i] * (0.6 if i == 3 else 1.0)
                    cs, _ = evaluate(clip(c))
                    if cs > s + 1e-6:
                        v, s, moved = clip(c), cs, True
            if not moved:
                st *= 0.45
        if s > best[0]:
            best = (s, v)
    v_opt = best[1]

    # ---- S3 safety scaling on held-out meal seeds -------------------------
    holdout = [6111013, 6111014, 6111015, 6111016]
    hexp = Experiment(INST, seeds=holdout)
    table = {}
    for amp in (0.93, 0.95, 0.97, 0.99, 1.01):
        m = hexp.evaluate(to_design(v_opt, amp))
        table[amp] = (m['mean_tir'], m['max_trajectory_tbr70'],
                      m['max_trajectory_tbr54'], m['minimum_glucose'])
        print(amp, [round(x, 2) for x in table[amp]])
    ok = [(t[0], a) for a, t in table.items()
          if t[3] >= 74.5 and t[1] <= 0.2 and t[2] <= 0.05]
    amp = max(ok)[1] if ok else max((t[3], a) for a, t in table.items())[1]

    design = to_design(v_opt, amp)
    design['parameters'] = {k: float(x) for k, x in design['parameters'].items()}
    save_design(design)
    json.dump({'amplitude_scale': amp, 'holdout': {str(k): v for k, v in table.items()},
               'training': {k: val for k, val in exp.evaluate(design).items() if k != 'rows'},
               'evaluations': exp.evaluations}, open('/work/output/search_log.json', 'w'), indent=2)
    return design


if __name__ == '__main__':
    print(json.dumps(main()))
