"""Reproducible search for the GRI static formulation (instance dev-06).
Stage 1: diagnostics (basal need vs TDI). Stage 2: differential evolution on the
responsive parameters with a hypoglycemia penalty. Stage 3: validation of top
candidates on fresh meal seeds. Best design is checkpointed atomically.
Env: SEARCH_CPU (seconds of process CPU for the search), SEARCH_SEED.
"""
import os, time
import numpy as np
from gri_bench.api import Experiment, PARAMETERS, load_instance, save_design
from gri_bench.physiology import patient_parameters

INSTANCE = load_instance()
T0 = time.process_time()
CPU = float(os.environ.get('SEARCH_CPU', '18'))
RNG = np.random.default_rng(int(os.environ.get('SEARCH_SEED', '0')))
VAL_SEEDS = [6111007, 6111008, 6111009]
BOUNDS = np.array([[3e-4, 2e-3], [0.53, 5.0], [80., 420.], [0.8, 4.0], [2., 14.], [2.2, 4.0]])


def clip(x):
    return np.minimum(np.maximum(x, BOUNDS[:, 0]), BOUNDS[:, 1])


def evaluate(exp, x):
    d = {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, x)))}
    r = exp.evaluate(d)
    s = (r['mean_tir']
         - 40.0 * max(0.0, r['max_trajectory_tbr70'] - 3.0)
         - 40.0 * max(0.0, r['max_trajectory_tbr54'] - 0.8)
         - 1.5 * max(0.0, 46.0 - r['minimum_glucose'])
         - 0.05 * max(0.0, r['max_trajectory_tbr70'] - 1.0))
    return s, r


def left():
    return CPU - (time.process_time() - T0)


def log(x, s, r):
    print(f'{time.process_time()-T0:6.2f}s sc={s:7.2f} tir={r["mean_tir"]:5.1f} '
          f'feas={int(r["feasible"])} tbr70={r["max_trajectory_tbr70"]:5.2f} '
          f'tbr54={r["max_trajectory_tbr54"]:5.2f} min={r["minimum_glucose"]:5.1f} '
          + np.array2string(np.asarray(x), precision=4), flush=True)


def main():
    for name in INSTANCE['patients']:
        p, _ = patient_parameters(name)
        basal = p.u2ss * p.BW / 6000.0 * 1440.0
        tdi = INSTANCE['tdi'][name]
        print(f'{name} basal/day={basal:.2f} TDI={tdi:.2f} ratio={tdi/basal:.3f}')
    train = Experiment(INSTANCE)
    anchors = np.array([[6e-4, 0.53, 150., 2.5, 6., 3.],
                        [4e-4, 0.75, 150., 3.0, 6., 3.],
                        [9e-4, 0.6, 120., 3.0, 5., 3.5],
                        [1.2e-3, 0.8, 200., 2.0, 8., 3.]])
    pop = []
    for x in list(anchors) + list(clip(BOUNDS[:, 0] + RNG.random((10, 6)) * (BOUNDS[:, 1] - BOUNDS[:, 0]))):
        s, r = evaluate(train, x)
        log(x, s, r)
        pop.append([s, x, r])
        if left() < 0.6:
            break
    best = max(pop, key=lambda t: t[0])
    save_design({'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, best[1])))})
    F, CR, KEEPTOP = 0.7, 0.9, 6
    while left() > 0.8:
        trial_pop = []
        for i in range(len(pop)):
            if left() < 0.5:
                break
            idx = RNG.choice(len(pop), 3, replace=False)
            while i in idx:
                idx = RNG.choice(len(pop), 3, replace=False)
            a, b, c = pop[idx[0]][1], pop[idx[1]][1], pop[idx[2]][1]
            mut = clip(a + F * (b - c))
            cross = RNG.random(6) < CR
            if not cross.any():
                cross[RNG.integers(6)] = True
            x = np.where(cross, mut, pop[i][1])
            s, r = evaluate(train, x)
            log(x, s, r)
            trial_pop.append([s, x, r])
        pop = sorted(pop + trial_pop, key=lambda t: -t[0])[:max(KEEPTOP, len(pop))]
        save_design({'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, pop[0][1])))})
    print('=== top candidates on fresh seeds ===')
    val = Experiment(INSTANCE, seeds=VAL_SEEDS)
    top = sorted(pop, key=lambda t: -t[0])[:KEEPTOP]
    winner, best_val = None, -1e9
    for s, x, r in top:
        d = {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, x)))}
        rv = val.evaluate(d)
        ok = rv['feasible'] and rv['minimum_glucose'] >= 45 and rv['max_trajectory_tbr70'] <= 3.0 and rv['max_trajectory_tbr54'] <= 0.8
        print(f'val tir={rv["mean_tir"]:5.2f} feas={int(rv["feasible"])} tbr70={rv["max_trajectory_tbr70"]:5.2f} '
              f'tbr54={rv["max_trajectory_tbr54"]:5.2f} min={rv["minimum_glucose"]:5.1f} '
              + np.array2string(np.asarray(x), precision=4), flush=True)
        if ok and rv['mean_tir'] > best_val:
            winner, best_val = x, rv['mean_tir']
    if winner is None:
        winner = sorted(pop, key=lambda t: -t[0])[0][1]
    save_design({'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, winner)))})
    print('winner', np.array2string(np.asarray(winner), precision=5), 'val_tir', best_val)


if __name__ == '__main__':
    main()
