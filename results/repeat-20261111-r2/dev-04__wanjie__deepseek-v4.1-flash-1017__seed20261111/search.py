"""Reproducible search for the GRI static formulation, instance dev-04.

Findings that drove the search (all obtained with gri_bench.api.Experiment):

1. The finite reservoir is *the* binding constraint: total insulin over the
   three days is theta_L * TDI <= 1.25 * TDI, i.e. at most ~0.42 * TDI/day,
   which is far below the roughly 1 * TDI/day these patients need. Glucose is
   therefore driven upward; peaks beyond ~600 mg/dL are effectively
   unrecoverable in this model, so insulin spent *before* an excursion is worth
   much more than insulin spent after it.  A uniform constant-rate design at
   the reservoir limit (`python search.py scan`) reaches only ~9% TIR, while a
   glucose-responsive design that concentrates the same fixed load in the
   hyperglycaemic region reaches ~30%.
2. Aggressive designs (theta_a * relative_leak > ~1e-3 /min, i.e. more than a
   full TDI per day) drain the reservoir in under a day and then crash
   (TBR54 >> 1%, minimum glucose < 40) -- see the `extremes` stage.  The safe
   frontier sits near a low-glucose rate of ~0.0005 * TDI /min with a Hill
   response centred at ~400 mg/dL.
3. Safety is the hard gate (any trajectory TBR70 > 4%, TBR54 > 1% or any
   minute < 40 mg/dL zeroes the score), so candidates are ranked with an
   explicit margin penalty (minimum glucose >= 65, TBR70 <= 1%) and the final
   candidate is re-validated on unseen meal seeds.

Stages: scan | random | refine | extremes | validate
"""
import json
import sys

import numpy as np

from gri_bench.api import PARAMETERS, Experiment, load_instance, save_design

INST = load_instance()
BOUNDS = INST['bounds']
EXP = Experiment(INST)                      # train seed 6111004, 3 variants
TRAJ = len(EXP.jobs)                        # 3 patients x 3 variants x 1 seed


def score(metrics):
    """TIR, heavily penalised for safety-margin violations."""
    if not metrics['feasible']:
        return -1e6 + metrics['mean_tir']
    penalty = 400.0 * max(0.0, metrics['max_trajectory_tbr70'] - 1.0)
    penalty += 800.0 * max(0.0, metrics['max_trajectory_tbr54'] - 0.2)
    penalty += 4.0 * max(0.0, 65.0 - metrics['minimum_glucose'])
    return metrics['mean_tir'] - penalty


def clip(params):
    return {k: float(np.clip(v, *BOUNDS[k])) for k, v in params.items()}


def run(params, experiment=EXP, mode='responsive'):
    p = clip(params)
    m = experiment.evaluate({'mode': mode, 'parameters': p})
    return score(m), m, p


def show(tag, s, m, p):
    print(f"{tag:>10} score={s:8.2f} tir={m['mean_tir']:6.2f} "
          f"tbr70={m['max_trajectory_tbr70']:5.2f} tbr54={m['max_trajectory_tbr54']:5.2f} "
          f"min={m['minimum_glucose']:7.1f} {json.dumps({k: round(v, 6) for k, v in p.items()})}")


def rows(m):
    for r in sorted(m['rows'], key=lambda r: r['metrics']['tir']):
        print('   ', r['patient'], f"{r['variant']:<12}",
              {k: round(v, 1) for k, v in r['metrics'].items()})


def stage_scan():
    """Constant-rate reference: shows the reservoir-limited baseline."""
    for tc in [1.25 / 4320, 1.6 / 4320, 2.0 / 4320, 2.5 / 4320, 3.0 / 4320]:
        d = {'theta_c': tc, 'theta_L': 1.25}
        m = EXP.evaluate({'mode': 'constant', 'parameters': d})
        show(f'c={tc:.6f}', score(m), m, d)


def stage_random(n=70, seed=7):
    rng = np.random.default_rng(seed)
    best = (-1e9, None, None)
    for i in range(n):
        cand = {'theta_a': float(10 ** rng.uniform(-4.2, -2.2)),
                'relative_leak': float(rng.uniform(*BOUNDS['relative_leak'])),
                'ec50_mg_dl': float(10 ** rng.uniform(np.log10(70), np.log10(500))),
                'hill_n': float(10 ** rng.uniform(np.log10(0.8), np.log10(12))),
                'tau_min': float(10 ** rng.uniform(np.log10(0.2), np.log10(20))),
                'theta_L': float(rng.uniform(0.75, 1.25))}
        s, m, p = run(cand)
        if s > best[0]:
            best = (s, m, p)
            show(f'rnd{i}', s, m, p)
    return best


def stage_refine(base, n=60, seed=11):
    rng = np.random.default_rng(seed)
    sd = {'theta_a': .30, 'relative_leak': .30, 'ec50_mg_dl': .25,
          'hill_n': .40, 'tau_min': .70, 'theta_L': .12}
    best = run(base)
    show('seed', *best)
    for i in range(n):
        cand = {k: float(v * np.exp(rng.normal(0, sd[k]))) for k, v in best[2].items()}
        s, m, p = run(cand)
        if s > best[0]:
            best = (s, m, p)
            show(f'ref{i}', s, m, p)
    return best


def stage_extremes():
    """Show the crash boundary that rules out high theta_a * relative_leak."""
    for c0 in [0.0009, 0.0013, 0.0020]:
        for leak in [0.6, 1.2]:
            for ec50, n in [(200., 2.0), (450., 4.0), (700., 1.0)]:
                d = {'theta_a': c0 / leak, 'relative_leak': leak, 'ec50_mg_dl': ec50,
                     'hill_n': n, 'tau_min': 6.0, 'theta_L': 1.25}
                s, m, p = run(d)
                show('ext', s, m, p)


def stage_validate(base):
    """Unseen meal seeds: safety must hold with a wide margin."""
    for seeds in ([6111004], [7777001, 7777002], [20261111, 31415926]):
        e = Experiment(INST, seeds=seeds)
        m = e.evaluate({'mode': 'responsive', 'parameters': base})
        print(seeds, {k: (round(v, 2) if isinstance(v, float) else v)
                      for k, v in m.items() if k != 'rows'})


DESIGN = {"mode": "responsive", "parameters": {
    "theta_a": 0.0003030586600846902, "relative_leak": 1.6669272559973654,
    "ec50_mg_dl": 395.2202625164729, "hill_n": 2.497051520624576,
    "tau_min": 0.9437522560492609, "theta_L": 1.2266215707816106}}

if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'validate'
    if stage == 'scan':
        stage_scan()
    elif stage == 'random':
        print(json.dumps(stage_random()[2]))
    elif stage == 'refine':
        print(json.dumps(stage_refine(DESIGN['parameters'])[2]))
    elif stage == 'extremes':
        stage_extremes()
    else:
        stage_validate(DESIGN['parameters'])
        m = EXP.evaluate(DESIGN)
        show('final', score(m), m, DESIGN['parameters'])
        rows(m)
        save_design(DESIGN)
