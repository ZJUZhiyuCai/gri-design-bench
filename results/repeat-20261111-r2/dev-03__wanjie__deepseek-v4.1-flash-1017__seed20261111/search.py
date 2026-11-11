"""Reproducible search for GRI static formulation (instance dev-03).

Stages (env var STAGE):
  probe   : print patient basal/initial-glucose facts and time one evaluation
  search  : random + local (coordinate) search on score = mean_tir - safety margins
Designs are written atomically to /work/output/design.json whenever the best
score improves.
"""
import json, os, time, math, itertools
import numpy as np
from pathlib import Path

T_START = time.time()
OUT = Path('/work/output')
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS
from gri_bench.physiology import patient_parameters

INST = load_instance()
B = INST['bounds']
TDI = INST['tdi']
SAFE_MIN = float(os.environ.get('SAFE_MIN', '82'))


def clamp_params(p):
    p = dict(p)
    for k, v in list(p.items()):
        lo, hi = B[k]
        p[k] = float(min(hi, max(lo, v)))
    return p


def score(m):
    """Safety-margin-aware objective: zero TBR preferred, min glucose >= ~75."""
    pen = (8.0 * max(0.0, m['max_trajectory_tbr70'])
           + 30.0 * max(0.0, m['max_trajectory_tbr54'])
           + 4.0 * max(0.0, SAFE_MIN - m['minimum_glucose'])
           + 10.0 * max(0.0, 40.0 - m['minimum_glucose']))
    return m['mean_tir'] - pen


def main():
    stage = os.environ.get('STAGE', 'probe')
    deadline = float(os.environ.get('DEADLINE', '8'))
    if stage == 'probe':
        for name in INST['patients']:
            p, init = patient_parameters(name)
            print(name, 'BW', round(p.BW, 1), 'u2ss', p.u2ss,
                  'basal U/min', round(p.u2ss * p.BW / 6000, 5),
                  'init plasma G', round(init[3] / p.Vg, 1),
                  'theta_c equiv', round(p.u2ss * p.BW / 6000 / TDI[name], 6))
        exp = Experiment(INST)
        designs = [
            {'mode': 'constant', 'parameters': {'theta_c': 0.0005, 'theta_L': 3.0}},
            {'mode': 'constant', 'parameters': {'theta_c': 0.0008, 'theta_L': 3.0}},
            {'mode': 'responsive', 'parameters': {'theta_a': 0.002, 'relative_leak': 1.0,
             'ec50_mg_dl': 150.0, 'hill_n': 3.0, 'tau_min': 10.0, 'theta_L': 4.0}},
        ]
        for d in designs:
            t = time.time(); m = exp.evaluate(d); el = time.time() - t
            print(json.dumps({'design': d, 'mean_tir': round(m['mean_tir'], 2),
                              'tbr70': round(m['max_trajectory_tbr70'], 2),
                              'tbr54': round(m['max_trajectory_tbr54'], 2),
                              'min': round(m['minimum_glucose'], 1),
                              'sec': round(el, 3)}))
        print('total wall', round(time.time() - T_START, 2))
        return

    exp = Experiment(INST)
    best = {'score': -1e9, 'design': None, 'metrics': None}
    log = []

    def consider(design, tag=''):
        nonlocal best
        m = exp.evaluate(design)
        s = score(m)
        rec = {'tag': tag, 'score': round(s, 3), 'tir': round(m['mean_tir'], 2),
               'tbr70': round(m['max_trajectory_tbr70'], 2),
               'tbr54': round(m['max_trajectory_tbr54'], 2),
               'min': round(m['minimum_glucose'], 1),
               'p': {k: round(v, 5) for k, v in design['parameters'].items()},
               'mode': design['mode']}
        log.append(rec)
        if s > best['score']:
            best = {'score': s, 'design': design, 'metrics': m}
            save_design(design)
            rec['best'] = True
        return s

    rng = np.random.default_rng(int(os.environ.get('SEED', '7')))

    def rand_resp():
        return clamp_params({'theta_a': rng.uniform(0.00008, 0.00045),
                             'relative_leak': rng.uniform(0.5125, 4.0),
                             'ec50_mg_dl': rng.uniform(90, 450),
                             'hill_n': rng.uniform(1.0, 20.0),
                             'tau_min': rng.uniform(0.3, 20.0),
                             'theta_L': 4.0})

    # --- coarse random over responsive shapes ---
    n_random = int(os.environ.get('N_RANDOM', '25'))
    cands = [rand_resp() for _ in range(n_random)]
    for p in cands:
        if time.time() - T_START > deadline:
            break
        consider({'mode': 'responsive', 'parameters': p}, 'random')

    # --- multi-start coordinate refinement (top random starts) ---
    top = sorted(log, key=lambda r: -r['score'])[:5]
    steps0 = {'theta_a': 0.00010, 'relative_leak': 0.25, 'ec50_mg_dl': 35.0,
              'hill_n': 1.5, 'tau_min': 4.0}
    for start in top:
        if time.time() - T_START > deadline:
            break
        base = dict(start['p'])
        steps = dict(steps0)
        cur = start['score']
        while time.time() - T_START < deadline:
            improved = False
            for k, st in steps.items():
                for sgn in (1, -1):
                    if time.time() - T_START > deadline:
                        break
                    p = dict(base); p[k] = base[k] + sgn * st
                    p = clamp_params({**p, 'theta_L': 4.0})
                    sc = consider({'mode': 'responsive', 'parameters': p}, 'refine')
                    if sc > cur:
                        cur = sc; base = p; improved = True
            if not improved:
                steps = {k: v * 0.5 for k, v in steps.items()}
                if max(steps.values()) < 1e-4:
                    break
    log.sort(key=lambda r: -r['score'])
    (OUT / 'search_log.json').write_text(json.dumps({'best': best['design'], 'log': log[:60]}, indent=1))
    print('evals', exp.evaluations, 'wall', round(time.time() - T_START, 2))
    print(json.dumps(log[:8], indent=0))


if __name__ == '__main__':
    main()


def validate(cands, seeds):
    """Multi-seed robustness table for a list of responsive designs."""
    exp = Experiment(INST, seeds=seeds)
    out = []
    for c in cands:
        m = exp.evaluate({'mode': 'responsive', 'parameters': clamp_params({**c, 'theta_L': 4.0})})
        worst_tbr = max(r['metrics']['tbr70'] for r in m['rows'])
        worst_min = min(r['metrics']['minimum'] for r in m['rows'])
        tirs = [r['metrics']['tir'] for r in m['rows']]
        out.append({'p': {k: round(v, 5) for k, v in c.items()},
                    'mean_tir': round(m['mean_tir'], 2), 'min_traj_tir': round(min(tirs), 2),
                    'max_tbr70': round(worst_tbr, 2), 'min_g': round(worst_min, 1),
                    'feasible': m['feasible']})
    out.sort(key=lambda r: -(r['mean_tir'] if r['feasible'] else r['mean_tir'] - 50))
    print(json.dumps(out, indent=0))


# ---------------------------------------------------------------------------
# FINAL DESIGN (validated on seeds 6111003, 20250101, 424242, 777001 x 3 variants)
#   responsive: theta_a=0.00017, relative_leak=1.8208, ec50_mg_dl=100.0,
#               hill_n=18.28731, tau_min=9.83632, theta_L=4.0
#   multi-seed metrics: mean_tir ~79.6, worst-trajectory TIR ~62, max TBR70=0,
#   max TBR54=0, minimum plasma glucose ~76.6 mg/dL (hard limit 40).
FINAL = {"mode": "responsive", "parameters": {"theta_a": 0.00017, "relative_leak": 1.8208,
         "ec50_mg_dl": 100.0, "hill_n": 18.28731, "tau_min": 9.83632, "theta_L": 4.0}}

VALIDATED_CANDIDATES = [
    # (theta_a, relative_leak, ec50, hill_n, tau): seed-mean TIR / worst TBR70 / min G
    (0.00017, 1.8208, 100.0, 18.28731, 9.83632),   # FINAL  79.6 / 0.0 / 76.6
    (0.00017, 1.8208, 111.91921, 18.28731, 9.83632),  # 79.0 / 0.0 / 77.2
    (0.00017, 1.8208, 111.91921, 18.28731, 9.83632),  # theta_a 0.000165: 76.1 / 0.0 / 80.7
    (0.00017, 1.8208, 111.91921, 12.0, 12.0),       # 75.6 / 0.0 / 80.3
    (0.00017, 1.9, 130.0, 12.0, 9.83632),           # 73.8 / 0.0 / 82.0
    (0.00016, 1.8208, 111.91921, 18.28731, 9.83632),  # 72.0 / 0.0 / 84.1
    (0.00017, 1.7, 111.91921, 18.28731, 9.83632),   # 69.4 / 0.0 / 86.2
    # Rejected: (0.00018, 2.2358, 206.45, 6.728, 16.739) -> training-seed TIR 74.8
    # but max TBR70 8.0% on fresh seeds (overfit to the single training seed).
]
