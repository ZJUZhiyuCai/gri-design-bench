"""Reproducible search for the GRI static formulation (dev-06).

Optimizes a penalized training objective over the known cohort (3 patients x 3
variants x 1 training seed) using the fast RK4 training integrator, then validates
the finalist with a handful of held-out meal seeds.
"""
import json, itertools, math, os, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

INSTANCE_PATH = '/task/instance.json'
OUT_DIR = '/work/output'


def load_instance(path=INSTANCE_PATH):
    return json.loads(open(path).read())


def objective(rows, instance):
    """Mean TIR with heavy penalties for any safety violation (soft during search)."""
    m = []
    for r in rows:
        x = r['metrics']
        m.append(x['tir']
                 - 200. * max(0., x['tbr70'] - 4.)
                 - 500. * max(0., x['tbr54'] - 1.)
                 - 100. * max(0., 40. - x['minimum']))
    return float(np.mean(m))


def evaluate(instance, design, seeds=None, variants=None):
    e = Experiment(instance, seeds=seeds, variants=variants)
    return e.evaluate(design)


def clamp(p, bounds):
    return {k: max(b[0], min(b[1], v)) for k, v in p.items() for b in [bounds[k]]}


def main():
    t0 = time.time()
    instance = load_instance()
    bounds = instance['bounds']
    best = None

    # ---- coarse grid over the most influential knobs -----------------------
    grid = {
        'theta_a': [0.0005, 0.001, 0.002, 0.0035],
        'relative_leak': [0.55, 0.8, 1.2, 2.0],
        'ec50_mg_dl': [120, 200, 320],
        'hill_n': [1.0, 2.0, 3.0],
        'tau_min': [4.0, 8.0, 14.0],
        'theta_L': [1.0, 1.6, 2.5, 3.5],
    }
    keys = list(grid.keys())
    for combo in itertools.product(*(grid[k] for k in keys)):
        p = dict(zip(keys, combo))
        design = {'mode': 'responsive', 'parameters': p}
        try:
            res = evaluate(instance, design)
        except Exception as ex:
            continue
        sc = objective(res['rows'], instance)
        if best is None or sc > best[0]:
            best = (sc, dict(p), res)
            print(f"grid new best {sc:.2f} tir={res['mean_tir']:.2f} "
                  f"tbr70={res['max_trajectory_tbr70']:.3f} tbr54={res['max_trajectory_tbr54']:.4f} "
                  f"min={res['minimum_glucose']:.1f} {p}")

    # ---- local coordinate ascent around the best grid point ----------------
    p = dict(best[1])
    for it in range(4):
        improved = True
        while improved:
            improved = False
            for k in keys:
                for factor in (1.4, 0.7):
                    q = dict(p); q[k] = q[k] * factor
                    q = clamp(q, bounds)
                    if q[k] == p[k]:
                        continue
                    design = {'mode': 'responsive', 'parameters': q}
                    try:
                        res = evaluate(instance, design)
                    except Exception:
                        continue
                    sc = objective(res['rows'], instance)
                    if sc > best[0]:
                        best = (sc, dict(q), res)
                        p = dict(q)
                        improved = True
                        print(f"  local {k}*{factor} -> {sc:.2f} tir={res['mean_tir']:.2f} "
                              f"tbr70={res['max_trajectory_tbr70']:.3f} "
                              f"tbr54={res['max_trajectory_tbr54']:.4f} min={res['minimum_glucose']:.1f}")
                        break
                if improved:
                    break

    # ---- robustness check on extra seeds -----------------------------------
    design = {'mode': 'responsive', 'parameters': best[1]}
    extra = [6111007, 6111008, 6111009, 6111010]
    r_extra = evaluate(instance, design, seeds=extra)
    print(f"robustness: mean_tir={r_extra['mean_tir']:.2f} tbr70={r_extra['max_trajectory_tbr70']:.3f} "
          f"tbr54={r_extra['max_trajectory_tbr54']:.4f} min={r_extra['minimum_glucose']:.1f} "
          f"feasible={r_extra['feasible']}")

    save_design(design, os.path.join(OUT_DIR, 'design.json'))
    print(f"saved design in {time.time()-t0:.1f}s, evaluations={best[2]['_evals'] if '_evals' in best[2] else '?'}")


if __name__ == '__main__':
    main()
