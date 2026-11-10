"""Reproducible search for /work/output/design.json (GRI static formulation, dev-04).

Model recap (see /opt/gri_bench/physiology.py):
  responsive rate = theta_a*TDI*(relative_leak + Hill(filtered interstitial glucose))
  total insulin available = theta_L*TDI (finite reservoir, hard cap)
  response rises with glucose above ec50_mg_dl => basal + meal-driven extra insulin.
Search: quasi-random Sobol sampling over the instance bounds with theta_L pinned near its
upper bound (total insulin is the binding resource), then coordinate/genetic refinement.
Selection: hard safety margin first (max TBR70 <= 1%, TBR54 == 0, full-horizon min >= 60),
then mean TIR on the training scenarios.
"""
import json, time, sys
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

inst = load_instance()
ex = Experiment(inst)
B = inst['bounds']
ORDER = PARAMETERS

def design(v):
    return {"mode": "responsive", "parameters": dict(zip(ORDER, map(float, v)))}

def score(metrics):
    # penalty keeps infeasible candidates ordered but strictly below safe ones
    feas = (metrics['max_trajectory_tbr70'] <= 1.0 and
            metrics['max_trajectory_tbr54'] <= 0.0 and metrics['minimum_glucose'] >= 60.0)
    pen = (max(0.0, metrics['max_trajectory_tbr70'] - 1.0) * 10 +
           metrics['max_trajectory_tbr54'] * 20 +
           max(0.0, 60.0 - metrics['minimum_glucose']) * 0.5)
    return (0.0 if feas else -1000.0 - pen) + metrics['mean_tir']

def clip(v):
    lo = np.array([B[k][0] for k in ORDER]); hi = np.array([B[k][1] for k in ORDER])
    return np.minimum(np.maximum(v, lo), hi)

rng = np.random.default_rng(20260404)
t0 = time.time()
best = None; log = []
from scipy.stats import qmc
sampler = qmc.Sobol(d=6, scramble=True, seed=7)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
u = sampler.random(N)
# bias sampling: theta_a small, theta_L high, tau mid-range
lo = np.array([B[k][0] for k in ORDER]); hi = np.array([B[k][1] for k in ORDER])
u[:, 0] = u[:, 0] ** 2                      # theta_a
u[:, 5] = hi[5] - (hi[5] - lo[5]) * 0.35 * u[:, 5] ** 2   # theta_L pinned near top
for i in range(N):
    v = clip(lo + (hi - lo) * u[i])
    m = ex.evaluate(design(v))
    s = score(m)
    log.append((s, list(v), m['mean_tir'], m['max_trajectory_tbr70'], m['minimum_glucose']))
    if best is None or s > best[0]:
        best = (s, v.copy(), m)
        print('new best', round(s, 2), np.round(v, 6).tolist(), 'tir', round(m['mean_tir'], 2),
              'tbr70', round(m['max_trajectory_tbr70'], 2), 'min', round(m['minimum_glucose'], 1), flush=True)

# local refinement: shrinking gaussian mutation around the incumbent
v = best[1].copy(); s = best[0]
scales = (hi - lo) * np.array([0.25, 0.25, 0.2, 0.25, 0.3, 0.05])
for step in range(3):
    improved = 0
    for i in range(25):
        cand = clip(v + rng.normal(size=6) * scales * (0.6 ** step))
        m = ex.evaluate(design(cand)); sc = score(m)
        if sc > s:
            v, s, best = cand, sc, (sc, cand.copy(), m); improved += 1
            print('refine', step, round(sc, 2), np.round(cand, 6).tolist(), 'tir', round(m['mean_tir'], 2),
                  'tbr70', round(m['max_trajectory_tbr70'], 2), 'min', round(m['minimum_glucose'], 1), flush=True)
    if improved == 0:
        break
print('elapsed', round(time.time() - t0, 2), 'evals', ex.evaluations)
print('BEST', round(best[0], 3), json.dumps(design(best[1])))
print({k: round(v, 3) for k, v in best[2].items() if k != 'rows'})
save_design(design(best[1]))
json.dump([{'score': s, 'params': p} for s, p, *_ in log], open('/work/output/search_log.json', 'w'), indent=1)
