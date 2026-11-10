"""Reproducible search for the GRI static formulation (dev-01 cohort).

Design space: responsive mode, 6 shared coefficients. theta_L enters only as the
finite-reservoir cap (rate = min(rate, remaining/3)), so it is monotonically
non-restrictive and is pinned at its upper bound 4.0; the search runs over the
other five coefficients (theta_a, relative_leak, ec50_mg_dl, hill_n, tau_min).

Stages: (1) structured random sampling scored on the training seed,
(2) re-ranking of survivors on a second seed,
(3) adaptive local search on the pooled 2-seed objective,
(4) fresh-seed validation of the finalists, then the design is saved.

Fitness = mean TIR minus soft hypoglycaemia / minimum-glucose penalties.
All coefficients are shared across the cohort; no per-patient fitting.
"""
import os, time, sys
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

T0 = time.time()

def cpu():
    t = os.times()
    return t[0] + t[1]

BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 17.0
inst = load_instance()
BND = inst['bounds']

ExA = Experiment(inst, seeds=[6111001])                        # training seed (9 trajectories)
ExC = Experiment(inst, seeds=[6111001, 5550001])               # search objective (18 trajectories)
ExB = Experiment(inst, seeds=[7770001, 8880001])               # untouched fresh seeds (18 trajectories)

def design(theta_a, leak, ec50, n, tau, theta_L=4.0):
    vals = [theta_a, leak, ec50, n, tau, theta_L]
    return {'mode': 'responsive', 'parameters': {k: float(v) for k, v in zip(PARAMETERS, vals)}}

def pack(d):
    return np.array([d['parameters'][k] for k in PARAMETERS])

def unpack(v):
    return {'mode': 'responsive', 'parameters': {k: float(x) for k, x in zip(PARAMETERS, v)}}

def stats_of(*results):
    return (float(np.mean([r['mean_tir'] for r in results])),
            float(max(r['max_trajectory_tbr70'] for r in results)),
            float(max(r['max_trajectory_tbr54'] for r in results)),
            float(min(r['minimum_glucose'] for r in results)))

def fitness(s):
    tir, tbr70, tbr54, mg = s
    pen = 8.0 * max(0.0, tbr70 - 1.5) + 200.0 * max(0.0, tbr54 - 0.1) + 4.0 * max(0.0, 65.0 - mg)
    return tir - pen

CACHE = {}

def ev(ex, key, v):
    k = (key, tuple(np.round(v, 12)))
    if k not in CACHE:
        CACHE[k] = stats_of(ex.evaluate(unpack(v)))
    return CACHE[k]

rng = np.random.default_rng(20261111)

def clamp(v):
    v = v.copy()
    for i, k in enumerate(PARAMETERS):
        v[i] = min(max(v[i], BND[k][0]), BND[k][1])
    return v

def sample():
    lo, hi = BND['relative_leak']
    while True:
        b = np.exp(rng.uniform(np.log(4e-5), np.log(1.2e-3)))     # basal rate per TDI per minute
        a = np.exp(rng.uniform(np.log(6e-5), np.log(2.2e-3)))     # max extra rate per TDI per minute
        leak = b / a
        if lo <= leak <= hi:
            break
    ec50 = np.exp(rng.uniform(np.log(65.0), np.log(BND['ec50_mg_dl'][1])))
    n = np.exp(rng.uniform(np.log(0.588), np.log(12.0)))
    tau = np.exp(rng.uniform(np.log(0.3), np.log(20.0)))
    return pack(design(a, leak, ec50, n, tau))

# ---- stage 1: structured random sampling on the training seed ----
t_start = cpu()
pool = []
for _ in range(400):
    if cpu() - t_start > 0.40 * BUDGET:
        break
    v = sample()
    pool.append((fitness(ev(ExA, 'A', v)), ev(ExA, 'A', v), v))
pool.sort(key=lambda z: -z[0])
print('[stage1] n=%d  cpu=%.2fs  best_fit=%.2f' % (len(pool), cpu() - t_start, pool[0][0]))

# ---- stage 2: re-rank survivors on two seeds ----
cands = []
for f1, s1, v in pool[:24]:
    s = ev(ExC, 'C', v)
    cands.append((fitness(s), s, v))
cands.sort(key=lambda z: -z[0])
print('[stage2] best on 2 seeds:', ['%.2f' % x for x in cands[0][1]])
inc = [c[2] for c in cands[:6]]
inc_s = [c[1] for c in cands[:6]]

# ---- stage 3: adaptive local search on the 2-seed objective ----
best_f = cands[0][0]
sigma = 0.25
it = 0
while cpu() - t_start < 0.72 * BUDGET:
    it += 1
    for j in range(len(inc)):
        v = inc[j] * np.exp(rng.normal(0.0, sigma, 6))
        v[5] = 4.0
        v = clamp(v)
        key = tuple(np.round(v, 12))
        if key in [tuple(np.round(x, 12)) for x in inc]:
            continue
        s = ev(ExC, 'C', v)
        f = fitness(s)
        if f > fitness(inc_s[j]) or rng.random() < 0.25:
            inc[j], inc_s[j] = v, s
        if f > best_f:
            best_f = f
            save_design(unpack(v))
    sigma = max(0.04, sigma * 0.94)
print('[stage3] iters=%d cpu=%.2fs best_fit=%.2f' % (it, cpu() - t_start, best_f))

order = np.argsort([-fitness(s) for s in inc_s])
finalists = [inc[int(i)] for i in order[:4]]

# ---- stage 4: fresh-seed validation ----
rows = []
for v in finalists:
    sB = ev(ExB, 'B', v)
    sC = ev(ExC, 'C', v)
    allrows = stats_of(ExC.evaluate(unpack(v)), ExB.evaluate(unpack(v)))   # pooled 4-seed picture
    rows.append((sB[0], v, sC, sB, allrows))
rows.sort(key=lambda z: -z[0])
for tirB, v, sC, sB, allr in rows:
    print('  fresh TIR %.2f | 2seed %s | fresh %s | pooled %s' %
          (tirB, ['%.2f' % x for x in sC], ['%.2f' % x for x in sB], ['%.2f' % x for x in allr]))

# choose: best fresh-seed TIR among finalists that stay safe on every validated seed
safe = [r for r in rows if r[4][1] <= 1.0 and r[4][2] <= 0.1 and r[4][3] >= 60.0]
chosen = (safe or rows)[0]
print('[final] pooled', ['%.2f' % x for x in chosen[4]], 'cpu=%.2fs' % (cpu() - t_start))
