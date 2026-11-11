"""Reproducible search for the GRI static design (instance dev-01).

Pipeline: coarse randomized sampling on the training scenario -> multi-seed
validation of top candidates (training seed + 3 held-out meal seeds, all 3
variants) -> local multiplicative refinement -> final re-ranking.  Every
trajectory must meet strict safety margins (TBR70<=3%, TBR54<=0.5%, min>=48
mg/dL) because the official grading uses fresh meal seeds with a zero-tolerance
gate (TBR70<=4%, TBR54<=1%, min>=40 mg/dL).  Only design.json is graded; this
file is the auditable source of the design.
"""
import json
import time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design

INST = load_instance('/task/instance.json')
BND = INST['bounds']
RNG = np.random.default_rng(20261111)
TRAIN_SEEDS = INST['training_seeds']
VAL_SEEDS = [111, 222, 333]

EX_COARSE = Experiment(INST, seeds=TRAIN_SEEDS, variants=['ordinary'])
EX_TRAIN = Experiment(INST)
EX_VAL = Experiment(INST, seeds=VAL_SEEDS)
EX_MED = Experiment(INST, seeds=TRAIN_SEEDS + [111])
SAFE = dict(tbr70=3.0, tbr54=0.5, mn=48.0)


def make(p):
    return {'mode': 'responsive',
            'parameters': {k: float(np.clip(p[k], *BND[k])) for k in
                           ('theta_a', 'relative_leak', 'ec50_mg_dl',
                            'hill_n', 'tau_min', 'theta_L')}}


def sample():
    lo, hi = BND['relative_leak']
    return make({
        'theta_a': np.exp(RNG.uniform(np.log(5e-5), np.log(2.5e-3))),
        'relative_leak': np.exp(RNG.uniform(np.log(lo), np.log(min(hi, 5.0)))),
        'ec50_mg_dl': np.exp(RNG.uniform(np.log(70.), np.log(600.))),
        'hill_n': RNG.uniform(0.6, 9.0),
        'tau_min': np.exp(RNG.uniform(np.log(0.6), np.log(20.))),
        'theta_L': np.exp(RNG.uniform(np.log(1.6), np.log(4.0))),
    })


def score(design, ex):
    m = ex.evaluate(design)
    ok = (m['max_trajectory_tbr70'] <= SAFE['tbr70'] and
          m['max_trajectory_tbr54'] <= SAFE['tbr54'] and
          m['minimum_glucose'] >= SAFE['mn'])
    return dict(design=design, tir=m['mean_tir'], tbr70=m['max_trajectory_tbr70'],
                tbr54=m['max_trajectory_tbr54'], mn=m['minimum_glucose'], ok=ok)


def robust(design):
    a, b = EX_TRAIN.evaluate(design), EX_VAL.evaluate(design)
    return dict(design=design,
                all_tir=0.25 * a['mean_tir'] + 0.75 * b['mean_tir'],
                worst_tbr70=max(a['max_trajectory_tbr70'], b['max_trajectory_tbr70']),
                worst_tbr54=max(a['max_trajectory_tbr54'], b['max_trajectory_tbr54']),
                worst_mn=min(a['minimum_glucose'], b['minimum_glucose']))


def is_ok(r):
    return (r['worst_tbr70'] <= SAFE['tbr70'] and r['worst_tbr54'] <= SAFE['tbr54']
            and r['worst_mn'] >= SAFE['mn'])


if __name__ == '__main__':
    t0 = time.time()
    coarse = [score(sample(), EX_COARSE) for _ in range(260)]
    coarse.sort(key=lambda r: -r['tir'])
    print('coarse feasible:', sum(r['tbr70'] <= 4 and r['tbr54'] <= 1 and r['mn'] >= 45
                                 for r in coarse), '/', len(coarse))

    pool, seen = [], set()
    for r in coarse[:60]:
        key = tuple(round(v, 8) for v in r['design']['parameters'].values())
        if key not in seen:
            seen.add(key)
            pool.append(robust(r['design']))
    pool.sort(key=lambda r: -r['all_tir'])
    best = next((r for r in pool if is_ok(r)), None)
    if best is None:
        pool.sort(key=lambda r: (-(r['worst_mn'] > 45), -r['all_tir']))
        best = pool[0]
    print('validated leader:', round(best['all_tir'], 1), 'tbr70', round(best['worst_tbr70'], 2),
          'min', round(best['worst_mn'], 1))
    save_design(best['design'])  # atomic checkpoint

    step = dict(theta_a=.35, relative_leak=.35, ec50_mg_dl=.35, hill_n=.35,
                tau_min=.35, theta_L=.2)
    cur = dict(best['design']['parameters'])
    cur_rec = score(best['design'], EX_MED)
    for _ in range(45):
        cand = {}
        for k, v in cur.items():
            lo, hi = BND[k]
            if v > 0 and RNG.random() < 0.8:
                nv = v * np.exp(RNG.normal(0, step[k]))
            else:
                nv = v + RNG.normal(0, (hi - lo) * 0.02)
            cand[k] = np.clip(nv, lo, hi)
        d = make(cand)
        r = score(d, EX_MED)
        if r['ok'] and r['tir'] > cur_rec['tir']:
            cur, cur_rec = cand, r
    print('refined:', round(cur_rec['tir'], 1))

    finalists = [make(cur)] + [r['design'] for r in pool[:4]]
    ranked = sorted((robust(d) for d in finalists),
                    key=lambda r: (-is_ok(r), -r['all_tir']))
    for r in ranked:
        print('TIR', round(r['all_tir'], 1), 'TBR70', round(r['worst_tbr70'], 2),
              'TBR54', round(r['worst_tbr54'], 2), 'min', round(r['worst_mn'], 1))
    save_design(ranked[0]['design'])
    print('SAVED', json.dumps(ranked[0]['design']))
    print('elapsed', round(time.time() - t0, 1))
