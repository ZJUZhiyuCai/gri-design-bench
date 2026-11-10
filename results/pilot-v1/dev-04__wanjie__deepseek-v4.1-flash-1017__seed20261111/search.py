"""Reproducible search for the GRI static formulation (dev-04 cohort).

Strategy: random search in log-transformed shape space (plus a small constant-mode
grid), scored on the fast RK4 training evaluator, then multi-seed robustness
re-ranking of the top candidates to avoid overfitting to one meal seed.
Every improvement of the incumbent robust design is checkpointed atomically to
/work/output/design.json.
"""
import json, numpy as np, os, sys, time
from pathlib import Path
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

OUT = Path('/work/output')
BOUNDS = None
LOGN = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min')

def to_design(v, mode='responsive'):
    if mode == 'responsive':
        p = {k: float(np.exp(x)) if k in LOGN else float(x) for k, x in zip(PARAMETERS, v)}
        # keep theta_a allowed to be 0 in principle; log-space keeps it positive
        return {'mode': 'responsive', 'parameters': p}
    return {'mode': 'constant', 'parameters': {'theta_c': float(np.exp(v[0])), 'theta_L': float(v[1])}}

def sample(rng, mode='responsive'):
    if mode == 'responsive':
        v = []
        for k in PARAMETERS:
            lo, hi = BOUNDS[k]
            if k in LOGN:
                v.append(rng.uniform(np.log(max(lo, 1e-6)), np.log(hi)))
            else:
                v.append(rng.uniform(lo, hi))
        return np.array(v)
    lo, hi = BOUNDS['theta_c'] if 'theta_c' in BOUNDS else (1e-5, 0.007)
    return np.array([rng.uniform(np.log(1e-5), np.log(0.007)), rng.uniform(*BOUNDS['theta_L'])])

def pen(m, tbr70_lim=1.5, tbr54_lim=0.3, min_lim=60.0):
    """Risk-averse surrogate score: TIR minus safety violations."""
    s = m['mean_tir']
    s -= 6.0 * max(0.0, m['max_trajectory_tbr70'] - tbr70_lim)
    s -= 40.0 * max(0.0, m['max_trajectory_tbr54'] - tbr54_lim)
    s -= 1.5 * max(0.0, min_lim - m['minimum_glucose'])
    return s

def main(budget_s=14.0):
    global BOUNDS
    inst = load_instance()
    BOUNDS = dict(inst['bounds'])
    BOUNDS['theta_c'] = inst['constant_theta_c_bounds']
    t0 = time.process_time()
    ex1 = Experiment(inst)                                   # training seed only (fast)
    ex3 = Experiment(inst, seeds=inst['training_seeds'] + [6111005, 6111006])
    rng = np.random.default_rng(20261111)

    results = []   # (score1, mode, v, design, metrics)
    def run(v, mode, ex):
        d = to_design(v, mode)
        try:
            m = ex.evaluate(d)
        except Exception:
            return None
        return m

    # incumbent from any previously checkpointed design
    best_robust = (-1e9, None, None)
    def consider(v, mode):
        nonlocal best_robust
        m1 = run(v, mode, ex1)
        if m1 is None:
            return
        results.append((pen(m1), mode, np.array(v, float), m1))
        if len(results) % 15 == 0 or pen(m1) > 6:
            pass

    # ---- phase A: broad random sampling on the training seed ----
    cands = []
    while time.process_time() - t0 < 0.55 * budget_s:
        mode = 'responsive' if rng.random() < 0.82 else 'constant'
        v = sample(rng, mode)
        m1 = run(v, mode, ex1)
        if m1 is None:
            continue
        results.append((pen(m1), mode, np.array(v, float), m1))
        cands.append((pen(m1), mode, np.array(v, float)))
        if pen(m1) > 8.0:                                  # warm-start seeds for refinement
            cands.append((pen(m1), mode, np.array(v, float)))
    results.sort(key=lambda r: -r[0])
    print('phaseA evals=%d best=%.2f' % (len(results), results[0][0]))

    # ---- phase B: multi-seed re-ranking of the top single-seed candidates ----
    top = results[:18]
    robust = []
    for s1, mode, v, m1 in top:
        if time.process_time() - t0 > 0.80 * budget_s:
            break
        m3 = run(v, mode, ex3)
        if m3 is None:
            continue
        robust.append((pen(m3), mode, v, m3))
    robust.sort(key=lambda r: -r[0])
    if robust:
        best_robust = robust[0]
        print('phaseB best=%.2f infeasible_ok' % robust[0][0])

    # ---- phase C: local refinement (stochastic hill climb) on multi-seed score ----
    seeds = [(mode, v) for _, mode, v, _ in robust[:4]] or [(mode, v) for _, mode, v in top[:4]]
    scale = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.15])
    cur = best_robust
    while time.process_time() - t0 < budget_s and seeds:
        i = int(rng.integers(len(seeds)))
        mode, v = seeds[i]
        step = scale * rng.normal(size=v.shape) * (0.5 if rng.random() < 0.7 else 1.5)
        v2 = np.array(v, float)
        if mode == 'responsive':
            for j, k in enumerate(PARAMETERS):
                if k in LOGN:
                    v2[j] = np.clip(np.exp(np.log(v2[j]) + step[j]), max(BOUNDS[k][0], 1e-6), BOUNDS[k][1])
                else:
                    v2[j] = np.clip(v2[j] + step[j] * (BOUNDS[k][1] - BOUNDS[k][0]) * 0.05, BOUNDS[k][0], BOUNDS[k][1])
        else:
            v2[0] = np.clip(np.exp(np.log(v2[0]) + step[0]), 1e-5, BOUNDS['theta_c'][1])
            v2[1] = np.clip(v2[1] + step[1] * 0.1, BOUNDS['theta_L'][0], BOUNDS['theta_L'][1])
        m = run(v2, mode, ex3)
        if m is None:
            continue
        s = pen(m)
        seeds.append((mode, v2))
        if s > cur[0]:
            cur = (s, mode, v2, m)
            json.dump({'score': s, 'mode': mode, 'v': v2.tolist()}, open(OUT / '_best.json', 'w'))
            print('  improve %.3f  tir=%.2f tbr70=%.2f tbr54=%.2f min=%.1f' % (
                s, m['mean_tir'], m['max_trajectory_tbr70'], m['max_trajectory_tbr54'], m['minimum_glucose']))
            save_design(to_design(v2, mode))
        if len(seeds) > 12:
            seeds.pop(0)

    # ---- final report + checkpoint ----
    if cur[1] is not None:
        d = to_design(cur[2], cur[1])
        m1 = ex1.evaluate(d); m3 = ex3.evaluate(d)
        print('FINAL', json.dumps(d))
        for tag, m in (('train', m1), ('multi', m3)):
            print(tag, {k: round(v, 3) if isinstance(v, float) else v for k, v in m.items() if k != 'rows'})
        save_design(d)
        np.save(OUT / '_top.npy', np.array([cur[2], ], dtype=float)) if False else None
        Path(OUT / '_final.json').write_text(json.dumps({'design': d, 'train': {k: v for k, v in m1.items() if k != 'rows'},
                                                         'multi': {k: v for k, v in m3.items() if k != 'rows'}}, indent=1))
    print('cpu used %.2f' % (time.process_time() - t0))

if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 14.0)
