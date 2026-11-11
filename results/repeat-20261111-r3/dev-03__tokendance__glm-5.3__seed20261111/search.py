"""Reproducible search for the dev-03 static formulation (responsive mode).

Stage A: coarse grid with the training seed (9 trajectories/eval).
Stage B: re-score top candidates on 4 meal seeds (robustness to fresh seeds).
Stage C: coordinate refinement of the incumbent on all 4 seeds.
The best feasible candidate is checkpointed atomically to /work/output/design.json.
"""
import json, os, time
import numpy as np
from gri_bench.api import load_instance, validate_design, save_design, glucose_metrics
from gri_bench.physiology import fast_trace, patient_parameters, meal_schedule

WARMUP = 1440
B_SEEDS = [6111003, 424242, 987654, 20261112]

def build_jobs(instance, seeds):
    jobs = []
    for s in seeds:
        for v in instance['variants']:
            sched = meal_schedule(s, instance['days'], v)
            for name in instance['patients']:
                p, initial = patient_parameters(name)
                jobs.append((name, s, v, p, initial, sched*p.BW/instance['reference_weight_kg'],
                             instance['tdi'][name]))
    return jobs

def run(par, jobs):
    tbr70 = tbr54 = 0.0; gmin = 1e9; tirs = []
    d = np.array([par['theta_a'], par['relative_leak'], par['ec50_mg_dl'],
                  par['hill_n'], par['tau_min'], par['theta_L']])
    for (name, s, v, p, initial, meals, tdi) in jobs:
        dd = d.copy(); dd[0] *= tdi; dd[5] *= tdi
        m = glucose_metrics(fast_trace(p, initial, meals, dd), WARMUP)
        tirs.append(m['tir'])
        tbr70 = max(tbr70, m['tbr70']); tbr54 = max(tbr54, m['tbr54'])
        gmin = min(gmin, m['minimum'])
    return {'tir': float(np.mean(tirs)), 'tbr70': tbr70, 'tbr54': tbr54, 'minimum': gmin}

def score(r):
    return (r['tir'] - 80*max(0.0, r['tbr70']-0.4) - 80*max(0.0, r['tbr54']-0.15)
            - 2.5*max(0.0, 62.0-r['minimum']))

def save(par):
    design = {'mode': 'responsive', 'parameters': {k: float(v) for k, v in par.items()}}
    validate_design(design, INSTANCE)
    tmp = '/work/output/design.json.tmp'
    with open(tmp, 'w') as f:
        json.dump(design, f, indent=2); f.write('\n')
    os.replace(tmp, '/work/output/design.json')

INSTANCE = load_instance()
BASE = {'theta_a': 0.00045, 'relative_leak': 0.5124966150526034, 'ec50_mg_dl': 220.0,
        'hill_n': 3.0, 'tau_min': 10.0, 'theta_L': 4.0}
jobsA = build_jobs(INSTANCE, [6111003])
jobsB = build_jobs(INSTANCE, B_SEEDS)

if __name__ == '__main__':
    t0 = time.time()
    stage = os.environ.get('STAGE', 'ABC')
    best = None
    if 'A' in stage:
        cands = [dict(BASE, theta_a=ta, ec50_mg_dl=ec, hill_n=n, tau_min=ta_)
                 for ta in (0.00042, 0.00046, 0.0005, 0.00055)
                 for ec in (180., 240., 300.)
                 for n in (2., 4., 8.)
                 for ta_ in (4., 10., 18.)]
        scored = sorted(((score(run(c, jobsA)), c) for c in cands), key=lambda x: -x[0])
        print('A top5:', [(round(s,1)) for s, _ in scored[:5]], f'{time.time()-t0:.1f}s')
        pool = [c for _, c in scored[:10]]
    else:
        pool = [dict(BASE, theta_a=ta, ec50_mg_dl=ec, hill_n=n, tau_min=tv)
                for ta in (0.00046, 0.0005) for ec in (240., 300.)
                for n in (4., 8.) for tv in (10., 18.)]
    if 'B' in stage:
        rescored = sorted(((score(run(c, jobsB)), c) for c in pool), key=lambda x: -x[0])
        for s, c in rescored[:4]:
            r = run(c, jobsB)
            print(f"B tir={r['tir']:.1f} tbr70={r['tbr70']:.2f} tbr54={r['tbr54']:.2f} min={r['minimum']:.0f} sc={s:.1f} par={c}")
        best = rescored[0][1]
        save(best)
    if 'C' in stage and False:
        steps = {'theta_a': 3e-5, 'ec50_mg_dl': 25.0, 'hill_n': 1.0, 'tau_min': 3.0,
                 'relative_leak': 0.25, 'theta_L': 0.5}
        for _ in range(3):
            improved = False
            for k, st in steps.items():
                for sgn in (1, -1):
                    c = dict(best); c[k] = min(max(c[k] + sgn*st, 1e-12), 1e9)
                    try:
                        r = run(c, jobsB)
                    except Exception:
                        continue
                    if score(r) > score(run(best, jobsB)) + 1e-9:
                        best = c; improved = True
            save(best)
            if not improved:
                break
        r = run(best, jobsB)
        print('C final:', {k: round(v, 6) for k, v in best.items()},
              f"tir={r['tir']:.1f} tbr70={r['tbr70']:.2f} tbr54={r['tbr54']:.2f} min={r['minimum']:.0f}")
    print('elapsed', round(time.time()-t0, 1))
