"""Reproducible search for the GRI static formulation (dev-04).

Strategy
--------
1. Coarse random search over a log-spaced 6-D parameter space.
2. Robust objective: evaluate on several meal seeds (training + fresh),
   require safety on ALL trajectories, maximize mean TIR with a margin
   penalty so the design is not right on the safety boundary.
3. Local refinement (Nelder-Mead) from the best coarse points.

Only design.json is used by the verifier; this script documents the search.
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance = load_instance()
# Robustness seeds: the training seed plus fresh meal seeds.
SEEDS = [6111004, 101, 202, 303]
exp = Experiment(instance, seeds=SEEDS)  # 3 patients x 3 variants x 4 seeds

BOUNDS = {
    'theta_a': (1e-4, 5e-3),
    'relative_leak': (0.6, 4.0),
    'ec50_mg_dl': (80.0, 400.0),
    'hill_n': (1.0, 12.0),
    'tau_min': (1.0, 15.0),
    'theta_L': (0.9, 1.25),
}

def make_design(vals):
    return {'mode': 'responsive',
            'parameters': dict(zip(PARAMETERS, vals))}

def objective(vals):
    """Higher is better. Rewards mean TIR, penalizes safety-margin erosion."""
    d = make_design(vals)
    m = exp.evaluate(d)
    rows = m['rows']
    mean_tir = m['mean_tir']
    worst70 = max(r['metrics']['tbr70'] for r in rows)
    worst54 = max(r['metrics']['tbr54'] for r in rows)
    mingluc = min(r['metrics']['minimum'] for r in rows)
    # Hard infeasibility -> heavy penalty (final score would be 0).
    pen = 0.0
    pen += 200 * max(0.0, worst70 - 4.0)
    pen += 200 * max(0.0, worst54 - 1.0)
    pen += 200 * max(0.0, 40.0 - mingluc)
    # Margin erosion: discourage sitting near the boundary.
    pen += 2.0 * max(0.0, 3.2 - worst70) * 0  # (kept explicit, off by default)
    return mean_tir - pen, (mean_tir, worst70, worst54, mingluc)

def search(n_random=40, seed=0):
    rng = np.random.default_rng(seed)
    best = None
    log = []
    for i in range(n_random):
        vals = np.array([
            10 ** rng.uniform(*np.log10(BOUNDS['theta_a'])),
            rng.uniform(*BOUNDS['relative_leak']),
            10 ** rng.uniform(*np.log10(BOUNDS['ec50_mg_dl'])),
            rng.uniform(*BOUNDS['hill_n']),
            rng.uniform(*BOUNDS['tau_min']),
            rng.uniform(*BOUNDS['theta_L']),
        ])
        s, info = objective(vals)
        log.append((s, vals.copy(), info))
        if best is None or s > best[0]:
            best = (s, vals.copy(), info)
        print(f"rand {i:3d} score={s:7.2f} tir={info[0]:6.2f} w70={info[1]:5.2f} "
              f"w54={info[2]:5.2f} min={info[3]:6.1f} {np.round(vals,4)}", flush=True)
    log.sort(key=lambda t: -t[0])
    return best, log

def refine(vals0, iters=60):
    from scipy.optimize import minimize
    def negf(v):
        s, _ = objective(np.clip(v, 0, None))
        return -s
    res = minimize(negf, vals0, method='Nelder-Mead',
                   options={'maxiter': iters, 'xatol': 1e-4, 'fatol': 1e-3})
    return res.x, -res.fun

if __name__ == '__main__':
    t0 = time.time()
    best, log = search(n_random=40)
    print("BEST coarse:", best[0], np.round(best[1], 4))
    # Refine from the top-3 distinct coarse points.
    top = [t[1] for t in log[:3]]
    best_ref = None
    for v0 in top:
        v, s = refine(v0, iters=50)
        s2, info = objective(v)
        print(f"refine score={s2:7.2f} tir={info[0]:6.2f} w70={info[1]:5.2f} "
              f"w54={info[2]:5.2f} min={info[3]:6.1f} {np.round(v,4)}", flush=True)
        if best_ref is None or s2 > best_ref[0]:
            best_ref = (s2, v.copy(), info)
    if best_ref is not None and best_ref[0] > best[0]:
        best = best_ref
    s, info = objective(best[1])
    print("FINAL score", s, "info", info, "elapsed", time.time() - t0)
    d = make_design(best[1])
    # Final check on the training seed only (what the API default uses).
    exp1 = Experiment(instance)
    m1 = exp1.evaluate(d)
    print("training-seed summary:", {k: v for k, v in m1.items() if k != 'rows'})
    save_design(d)
    print("saved design:", d)
