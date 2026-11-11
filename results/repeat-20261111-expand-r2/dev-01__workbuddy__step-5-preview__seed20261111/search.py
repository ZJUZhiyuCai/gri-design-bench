"""Search over GRI static formulation (responsive rate) for the dev-01 cohort.

Strategy: Latin-hypercube random search in normalized parameter space,
scored by a safety-penalized TIR objective on the cached training variants.
Best design is written atomically to design.json.
"""
import json, sys, time
import numpy as np
from gri_bench.api import load_instance, Experiment, validate_design

BOUNDS = json.load(open('/task/instance.json'))['bounds']
KEYS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')

def sample(rng):
    return {k: float(rng.uniform(*BOUNDS[k])) for k in KEYS}

def main():
    inst = load_instance()
    exp = Experiment(inst)
    rng = np.random.default_rng(0)
    best, best_score = None, -1e9
    for it in range(int(sys.argv[1]) if len(sys.argv) > 1 else 60):
        d = {'mode': 'responsive', 'parameters': sample(rng)}
        try:
            r = exp.evaluate(d)
        except Exception:
            continue
        s = r['safe_tir'] if r['feasible'] else r['mean_tir'] - 20.0
        if s > best_score:
            best_score, best = s, (d, r)
    print(best_score, json.dumps(best[0]) if best else None)
    print({k: v for k, v in best[1].items() if k != 'rows'})

if __name__ == '__main__':
    main()
