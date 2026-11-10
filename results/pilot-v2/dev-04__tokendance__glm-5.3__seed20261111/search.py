"""Reproducible design search for GRI instance dev-04 (adult#004-006).

Strategy: insulin is scarce (3-day reservoir theta_L*TDI < 3x basal needs for
2 of 3 patients), so the responsive shape must act as a bang-bang allocator:
near-zero delivery at/below a setpoint EC50, near-max above it, letting
filtered interstitial glucose self-regulate around EC50 while spending the
reservoir preferentially during hyperglycemic post-meal periods.
Coordinate (log-line) search on the training seed, then robustness re-ranking
on fresh meal seeds. Saves best design atomically.
"""
import json, time
from pathlib import Path
import numpy as np
from gri_bench.api import Experiment, save_design, PARAMETERS

T0 = time.process_time()
CPU_BUDGET = 14.0
INST = json.loads(Path('/task/instance.json').read_text())

def design_of(p):
    return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, [float(v) for v in p]))}

def score(mean_tir, tbr70, tbr54, gmin):
    s = mean_tir
    s -= 60.0 * max(0.0, tbr70 - 3.0)      # margin below the 4% trip
    s -= 60.0 * max(0.0, tbr54 - 0.8)      # margin below the 1% trip
    s -= 60.0 * max(0.0, 45.0 - gmin)      # margin above the 40 mg/dL trip
    return s

def res_score(r):
    return score(r['mean_tir'], r['max_trajectory_tbr70'], r['max_trajectory_tbr54'], r['minimum_glucose'])

def main():
    ex = Experiment(INST)
    lo = np.array([8e-5, 0.5125, 100.0, 1.5, 0.3, 0.9])
    hi = np.array([8e-4, 2.5, 420.0, 16.0, 12.0, 1.25])
    x = np.array([2.6e-4, 0.6, 210.0, 6.0, 3.0, 1.25])
    cache = {}
    def ev(p):
        k = tuple(np.round(p, 9))
        if k not in cache:
            r = ex.evaluate(design_of(p))
            cache[k] = (res_score(r), r)
        return cache[k]
    (bs, br), bx = ev(x), x.copy()
    sweep_list = [[0.45, 0.7, 1.0, 1.4, 2.2], [0.7, 0.85, 1.0, 1.15, 1.4], [0.9, 0.95, 1.0, 1.05, 1.1]]
    for sweeps in sweep_list:
        for i in range(6):
            for f in sweeps:
                if time.process_time() - T0 > CPU_BUDGET:
                    break
                y = bx.copy(); y[i] = float(np.clip(bx[i] * f, lo[i], hi[i]))
                s, r = ev(y)
                if s > bs:
                    bs, br, bx = s, r, y
        if time.process_time() - T0 > CPU_BUDGET:
            break
    # Robustness re-rank of top candidates on fresh meal seeds.
    cand = sorted(cache.items(), key=lambda kv: -kv[1][0])[:8]
    vex = Experiment(INST, seeds=[7717, 424243])
    best_k, best_v = None, -1e18
    for k, (s, r) in cand:
        if time.process_time() - T0 > CPU_BUDGET + 6.0:
            break
        d = design_of(np.array(k))
        v = vex.evaluate(d)
        vs = res_score(v)
        tot = 0.4 * s + 0.6 * vs
        print('cand', [f'{q:.6g}' for q in k], 'train', round(s, 2), 'val', round(vs, 2),
              'valtir', round(v['mean_tir'], 2), 'tbr70', round(v['max_trajectory_tbr70'], 2),
              'tbr54', round(v['max_trajectory_tbr54'], 2), 'min', round(v['minimum_glucose'], 1))
        if tot > best_v:
            best_v, best_k = tot, k
    final = design_of(np.array(best_k if best_k is not None else bx))
    print('FINAL', final, 'train_score', round(bs, 2), 'detail', br)
    save_design(final)
    Path('/work/output/search_result.json').write_text(json.dumps(
        {'final': final, 'train_score': bs, 'train_metrics': br}, indent=2))

if __name__ == '__main__':
    main()
