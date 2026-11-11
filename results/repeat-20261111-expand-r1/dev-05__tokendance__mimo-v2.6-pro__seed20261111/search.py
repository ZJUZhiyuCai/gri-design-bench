#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (instance dev-05).

Objective: maximize mean post-warmup TIR in [70,180] mg/dL over meal
scenarios, with hard safety: every patient/variant/seed trajectory must have
TBR70 <= 4%, TBR54 <= 1% and full-horizon (incl. warmup) min glucose >= 40.

Method (deterministic, seeded):
  Phase A  seeded random search on the training scenarios
           (seed 6111005 x variants ordinary/missed_lunch/large_dinner).
  Phase B  robustness screen of the top candidates on extra meal seeds.
  Phase C  coordinate + pattern refinement around the robust incumbent,
           evaluated jointly on training seed + one extra seed.
  Phase D  final validation on three held-out-style seeds; the winner is
           written with gri_bench.api.save_design (atomic replace).

A process-time guard stops sampling and saves the incumbent before the
container CPU budget is exhausted.
"""
import time
import json
import numpy as np

from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

TRAIN_SEEDS = [6111005]
EXTRA_SEEDS = [771001, 771002, 771003, 771004]   # fresh meal seeds for validation
N_RANDOM = 90
CPU_GUARD = 24.0                                 # seconds of process time

t_start = time.process_time()
def cpu_left():
    return CPU_GUARD - (time.process_time() - t_start)

BOX = {   # sampling box (kept inside instance bounds)
    'theta_a':       (0.00015, 0.00100),
    'relative_leak': (1.5,     3.5),
    'ec50_mg_dl':    (110.0,   260.0),
    'hill_n':        (0.8,     12.0),
    'tau_min':       (3.0,     20.0),
    'theta_L':       (2.6,     4.0),
}


def clip(p, bounds):
    return {k: float(min(max(p[k], bounds[k][0]), bounds[k][1])) for k in p}


def sample(rng, bounds):
    p = {}
    for k, (lo, hi) in BOX.items():
        u = rng.uniform(np.log(lo), np.log(hi)) if k == 'hill_n' else rng.uniform(lo, hi)
        p[k] = float(np.exp(u)) if k == 'hill_n' else float(u)
    return clip(p, bounds)


def design(p):
    return {'mode': 'responsive', 'parameters': {k: p[k] for k in PARAMETERS}}


def trajectory_stats(metrics):
    rows = metrics['rows']
    mins = [r['metrics']['minimum'] for r in rows]
    return dict(
        tir=float(np.mean([r['metrics']['tir'] for r in rows])),
        min_g=min(mins),
        tbr70=max(r['metrics']['tbr70'] for r in rows),
        tbr54=max(r['metrics']['tbr54'] for r in rows),
    )


def hard_ok(s):
    """Verifier thresholds, with search-side safety margins."""
    return s['min_g'] >= 45.0 and s['tbr70'] <= 3.0 and s['tbr54'] <= 0.8


def eval_multi(experiments, p):
    """Evaluate on several experiments (seeds); return worst-case stats."""
    stats = [trajectory_stats(e.evaluate(design(p))) for e in experiments]
    return dict(tir=float(np.mean([s['tir'] for s in stats])),
                min_g=min(s['min_g'] for s in stats),
                tbr70=max(s['tbr70'] for s in stats),
                tbr54=max(s['tbr54'] for s in stats))


def rank(s):
    """Feasibility first, then mean TIR, then safety margin."""
    ok = hard_ok(s)
    return (ok, round(s['tir'], 6) if ok else 0.0, s['min_g'] - 5.0 * s['tbr70'] - 10.0 * s['tbr54'])


def main():
    inst = load_instance()
    bounds = inst['bounds']
    train = Experiment(inst, seeds=TRAIN_SEEDS, variants=inst['variants'])
    rng = np.random.default_rng(2026111101)
    board = []   # (rank_key, p, stats)

    def record(p, s, tag):
        board.append((rank(s), dict(p), s, tag))
        board.sort(key=lambda t: t[0], reverse=True)
        del board[12:]

    # ---- Phase A: random search on training scenarios ----
    for i in range(N_RANDOM):
        if cpu_left() < 12:
            break
        p = sample(rng, bounds)
        record(p, eval_multi([train], p), f'rand{i}')

    # ---- Phase B: robustness screen on one extra seed ----
    screen = Experiment(inst, seeds=[EXTRA_SEEDS[0]], variants=inst['variants'])
    for key, p, s, tag in list(board)[:10]:
        if cpu_left() < 9:
            break
        record(p, eval_multi([train, screen], p), tag + '+scr')

    # ---- Phase C: coordinate refinement on train + extra seed ----
    ref = Experiment(inst, seeds=[TRAIN_SEEDS[0], EXTRA_SEEDS[0]], variants=inst['variants'])
    step = {'theta_a': 8e-5, 'relative_leak': 0.4, 'ec50_mg_dl': 25.0,
            'hill_n': 0.8, 'tau_min': 3.0, 'theta_L': 0.3}
    for _ in range(3):
        if cpu_left() < 5:
            break
        key, incumbent, s0, tag = board[0]
        improved = False
        for k in PARAMETERS:
            for sgn in (+1, -1):
                if cpu_left() < 3:
                    break
                p = clip({**incumbent, k: incumbent[k] + sgn * step[k]}, bounds)
                s = eval_multi([ref], p)
                if rank(s) > key:
                    record(p, s, 'refine')
                    key, incumbent, improved = rank(s), p, True
        for k in step:
            step[k] *= 0.6
        if not improved:
            continue

    # ---- Phase D: final validation on fresh seeds; save winner ----
    val_seeds = EXTRA_SEEDS[1:4]
    val = [Experiment(inst, seeds=[sv], variants=inst['variants']) for sv in val_seeds]
    finalists = []
    for key, p, s, tag in list(board)[:6]:
        if cpu_left() < 1.5:
            break
        sv = eval_multi(val, p)
        finalists.append((rank(sv), p, sv, tag))
        print('FINALIST', tag, {k: round(v, 3) for k, v in sv.items()}, p)
    finalists.sort(key=lambda t: t[0], reverse=True)

    key, p, s, tag = finalists[0] if finalists else board[0]
    save_design(design(p))
    print('WINNER', tag, {k: round(v, 3) for k, v in s.items()})
    print('PARAMS', json.dumps(p))
    for k, pp, ss, tg in board[:6]:
        print('BOARD', tg, {a: round(b, 3) for a, b in ss.items()})


if __name__ == '__main__':
    main()


# ---------------------------------------------------------------------------
# Stage 2 (run with `python search.py --stage 2`): fine refinement around the
# stage-1 winner, judged jointly on the training seed + two extra seeds with
# tighter safety margins, plus a few contrast probes to escape local optima.
STAGE1_WINNER = {'theta_a': 0.0001559750702494655, 'relative_leak': 3.528831916047923,
                 'ec50_mg_dl': 164.1034174603239, 'hill_n': 5.895278923819172,
                 'tau_min': 3.7128666181501453, 'theta_L': 3.405413751518485}


def hard_ok2(s):
    return s['min_g'] >= 58.0 and s['tbr70'] <= 1.0 and s['tbr54'] <= 0.4


def rank2(s):
    ok = hard_ok2(s)
    return (ok, round(s['tir'], 6) if ok else 0.0, s['min_g'] - 5.0 * s['tbr70'] - 10.0 * s['tbr54'])


def stage2():
    inst = load_instance()
    bounds = inst['bounds']
    exps = [Experiment(inst, seeds=[TRAIN_SEEDS[0]], variants=inst['variants']),
            Experiment(inst, seeds=[EXTRA_SEEDS[0]], variants=inst['variants']),
            Experiment(inst, seeds=[EXTRA_SEEDS[1]], variants=inst['variants'])]
    board = []

    def record(p, s, tag):
        board.append((rank2(s), dict(p), s, tag))
        board.sort(key=lambda t: t[0], reverse=True)
        del board[10:]
        print(tag, {k: round(v, 3) for k, v in s.items()})

    record(STAGE1_WINNER, eval_multi(exps, STAGE1_WINNER), 'start')
    # contrast probes: wider responsive swing / lower threshold / constant-mode sanity
    probes = [
        {'theta_a': 0.00032, 'relative_leak': 1.5, 'ec50_mg_dl': 150.0, 'hill_n': 4.0, 'tau_min': 6.0, 'theta_L': 3.4},
        {'theta_a': 0.00025, 'relative_leak': 1.5, 'ec50_mg_dl': 130.0, 'hill_n': 2.5, 'tau_min': 10.0, 'theta_L': 3.4},
        {'theta_a': 0.00022, 'relative_leak': 2.2, 'ec50_mg_dl': 145.0, 'hill_n': 8.0, 'tau_min': 4.0, 'theta_L': 3.6},
        {'theta_a': 0.00020, 'relative_leak': 3.5, 'ec50_mg_dl': 175.0, 'hill_n': 10.0, 'tau_min': 3.0, 'theta_L': 3.4},
        {'theta_a': 0.00018, 'relative_leak': 4.5, 'ec50_mg_dl': 165.0, 'hill_n': 6.0, 'tau_min': 5.0, 'theta_L': 3.3},
        {'theta_a': 0.000156, 'relative_leak': 3.53, 'ec50_mg_dl': 120.0, 'hill_n': 12.0, 'tau_min': 3.7, 'theta_L': 3.4},
        {'theta_a': 0.000156, 'relative_leak': 3.53, 'ec50_mg_dl': 210.0, 'hill_n': 3.0, 'tau_min': 3.7, 'theta_L': 3.4},
    ]
    for i, p in enumerate(probes):
        if cpu_left() < 8:
            break
        record(clip(p, bounds), eval_multi(exps, clip(p, bounds)), f'probe{i}')

    step = {'theta_a': 2.5e-5, 'relative_leak': 0.35, 'ec50_mg_dl': 12.0,
            'hill_n': 0.6, 'tau_min': 1.2, 'theta_L': 0.15}
    for _ in range(4):
        if cpu_left() < 5:
            break
        key, incumbent, s0, tag = board[0]
        improved = False
        for k in PARAMETERS:
            for sgn in (+1, -1):
                if cpu_left() < 3:
                    break
                p = clip({**incumbent, k: incumbent[k] + sgn * step[k]}, bounds)
                s = eval_multi(exps, p)
                if rank2(s) > key:
                    record(p, s, 'ref2')
                    key, incumbent, improved = rank2(s), p, True
        for k in step:
            step[k] *= 0.6
        if not improved:
            continue

    val = [Experiment(inst, seeds=[sv], variants=inst['variants']) for sv in EXTRA_SEEDS[2:4]]
    finalists = []
    for key, p, s, tag in list(board)[:5]:
        if cpu_left() < 1.2:
            break
        sv = eval_multi(val, p)
        finalists.append((rank2(sv), p, sv, tag))
        print('S2FINAL', tag, {k: round(v, 3) for k, v in sv.items()})
    finalists.sort(key=lambda t: t[0], reverse=True)
    key, p, s, tag = finalists[0] if finalists else board[0]
    save_design(design(p))
    print('S2WINNER', tag, {k: round(v, 3) for k, v in s.items()})
    print('S2PARAMS', json.dumps(p))


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2 and sys.argv[2] == '2':
        stage2()
    else:
        main()
