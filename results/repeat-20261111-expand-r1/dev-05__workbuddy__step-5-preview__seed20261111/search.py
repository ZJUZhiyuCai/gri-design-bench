#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation design (dev-05)."""
import json, sys, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, individual_design
from gri_bench.physiology import fast_trace, glucose_metrics

INSTANCE = load_instance()
TDI = INSTANCE['tdi']
NAMES = INSTANCE['patients']
LO = np.array([INSTANCE['bounds'][k][0] for k in PARAMETERS])
HI = np.array([INSTANCE['bounds'][k][1] for k in PARAMETERS])
TRAIN_SEEDS = [6111005]
VAL_SEEDS = [6111005, 700001, 700002, 700003]


def build_jobs(seeds, variants):
    jobs = []
    from gri_bench.physiology import patient_parameters, meal_schedule
    sched = {(s, v): meal_schedule(s, INSTANCE['days'], v) for s in seeds for v in variants}
    for n in NAMES:
        p, init = patient_parameters(n)
        for (s, v), base in sched.items():
            jobs.append((n, s, v, p, init, base * p.BW / INSTANCE['reference_weight_kg']))
    return jobs


def score_vector(vec, jobs):
    """vec = scaled responsive params (per-unit-TDI)."""
    rows = []
    for n, s, v, p, init, meals in jobs:
        d = np.array([vec[0] * TDI[n], vec[1], vec[2], vec[3], vec[4], vec[5] * TDI[n]])
        m = glucose_metrics(fast_trace(p, init, meals, d), INSTANCE['warmup_minutes'])
        rows.append(m)
    tir = np.mean([r['tir'] for r in rows])
    tbr70 = max(r['tbr70'] for r in rows)
    tbr54 = max(r['tbr54'] for r in rows)
    gmin = min(r['minimum'] for r in rows)
    pen = 0.0
    pen += 30.0 * max(0.0, tbr70 - 4.0)
    pen += 60.0 * max(0.0, tbr54 - 1.0)
    pen += 60.0 * max(0.0, 40.0 - gmin) if gmin < 40 else 0.0
    return tir - pen, dict(tir=tir, tbr70=tbr70, tbr54=tbr54, gmin=gmin)


def main():
    t0 = time.time()
    jobs = build_jobs(TRAIN_SEEDS, INSTANCE['variants'])
    rng = np.random.default_rng(0)
    best, best_s = None, -1e9
    for _ in range(400):
        vec = LO + rng.random(6) * (HI - LO)
        s, _ = score_vector(vec, jobs)
        if s > best_s:
            best, best_s = vec, s
    print('best', best, best_s, 'in %.1fs' % (time.time() - t0))
    design = {'mode': 'responsive',
              'parameters': {k: float(best[i]) for i, k in enumerate(PARAMETERS)}}
    json.dump(design, open('/work/output/design.json', 'w'), indent=2)


if __name__ == '__main__':
    main()
