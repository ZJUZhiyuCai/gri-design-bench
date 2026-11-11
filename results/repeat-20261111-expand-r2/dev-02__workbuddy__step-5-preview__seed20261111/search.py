"""GRI static formulation search (dev-02 cohort: adolescent#001-003).

Objective: maximize mean TIR over post-warmup plasma glucose in [70,180] mg/dL
across 3 patients x 3 scenario variants, subject to safety:
  per-trajectory TBR70 <= 4%, TBR54 <= 1%, and no minute (full 3 days) below 40.

Method: the design space is 6-dimensional (theta_a, relative_leak, ec50_mg_dl,
hill_n, tau_min, theta_L).  We (1) probe a small set of physically motivated
baselines with the fast RK4 trainer, (2) refine the best region with a
derivative-free search (bounded Nelder-Mead / coordinate descent on the
penalized objective), and (3) validate on held-out meal seeds and report the
safety-margin table.
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS

INSTANCE = load_instance()
BOUNDS = np.array([INSTANCE['bounds'][k] for k in PARAMETERS], float)


def design_from(x):
    x = np.clip(np.asarray(x, float), BOUNDS[:, 0], BOUNDS[:, 1])
    return {'mode': 'responsive',
            'parameters': {k: float(v) for k, v in zip(PARAMETERS, x)}}


def penalized(metrics):
    """safe_tir with a smooth safety margin penalty used only for search."""
    tir = metrics['mean_tir']
    pen = 0.0
    for r in metrics['rows']:
        m = r['metrics']
        pen += 30 * max(0.0, m['tbr70'] - 3.5) ** 1.5
        pen += 60 * max(0.0, m['tbr54'] - 0.8) ** 1.5
        pen += 0.4 * max(0.0, 45.0 - m['minimum'])
    return tir - pen / max(1, len(metrics['rows']))


def main():
    exp = Experiment(INSTANCE)
    print('jobs', len(exp.jobs))
    x0 = np.array([0.00025, 0.8, 110.0, 4.0, 8.0, 2.5])
    t0 = time.time()
    m = exp.evaluate(design_from(x0))
    print('one eval seconds', time.time() - t0)
    print({k: v for k, v in m.items() if k != 'rows'})
    for r in m['rows']:
        print(r['patient'], r['variant'], r['metrics'])


if __name__ == '__main__':
    main()
