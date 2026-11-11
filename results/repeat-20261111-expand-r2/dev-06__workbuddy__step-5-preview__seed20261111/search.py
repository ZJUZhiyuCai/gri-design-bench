"""Reproducible search for GRI static formulation design (instance dev-06).

Objective: maximise mean TIR (post-warmup plasma glucose in [70,180] mg/dL)
over the known cohort (child#004/005/006) x training variants, subject to hard
safety (TBR70<=4%, TBR54<=1%, full-horizon minute glucose>=40 mg/dL).
A soft margin is imposed so the design generalises to unseen meal seeds.
Final metrics are recomputed by the trusted verifier (native dopri5); nothing
here modifies the simulator.
"""
import json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/opt')
from gri_bench.api import load_instance, Experiment, save_design, validate_design

OUT = Path('/work/output')
FALLBACK = {"mode": "responsive", "parameters": {
    "theta_a": 0.0002, "relative_leak": 1.0, "ec50_mg_dl": 150.0,
    "hill_n": 2.0, "tau_min": 8.0, "theta_L": 4.0}}
KEYS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')


def write_all(design, rationale):
    validate_design(design, load_instance())
    save_design(design, str(OUT / 'design.json'))
    (OUT / 'rationale.md').write_text(rationale)
    Path(__file__).write_text(Path(__file__).read_text())


def clamp(v, lo, hi):
    return float(np.clip(v, lo, hi))


def main():
    inst = load_instance()
    exp = Experiment(inst)                              # 3 patients x 3 variants
    val = Experiment(inst, seeds=[8111006, 7223344])    # held-out meal seeds
    B = inst['bounds']
    LO = np.array([5.0e-5, B['relative_leak'][0], B['ec50_mg_dl'][0],
                   B['hill_n'][0], 2.0, 0.4])
    HI = np.array([8.0e-4, B['relative_leak'][1], B['ec50_mg_dl'][1],
                   B['hill_n'][1], 20.0, 4.0])
    best = np.array([FALLBACK['parameters'][k] for k in KEYS], dtype=float)

    def evaluate(vec, obj):
        d = {"mode": "responsive", "parameters": {k: float(v) for k, v in zip(KEYS, vec)}}
        r = (obj if obj is exp else val).evaluate(d)
        pen = (max(0.0, r['max_trajectory_tbr70'] - 3.0) * 60.0
               + max(0.0, r['max_trajectory_tbr54'] - 0.5) * 200.0
               + max(0.0, 60.0 - r['minimum_glucose']) * 3.0)
        return r['mean_tir'] - pen, r

    score, rep = evaluate(best, exp)
    vs, vrep = evaluate(best, val)
    rationale = (
        "# GRI static formulation design (dev-06)\n\n"
        "Mode: responsive shared coefficients. Fallback design already written.\n"
        "Seed: %s\n" % time.strftime('%Y-%m-%d %H:%M:%S'))
    write_all({"mode": "responsive",
               "parameters": {k: float(v) for k, v in zip(KEYS, best)}}, rationale)
    print('fallback written', score, {k: v for k, v in rep.items() if k != 'rows'})

    # ---- derivative-free coordinate refinement with safety margin -------------
    steps = np.array([1.2e-4, 0.9, 45.0, 0.45, 2.0, 0.4])
    rng = np.random.default_rng(0)
    for it in range(160):
        trial = best.copy()
        for _ in range(rng.integers(1, 4)):
            j = rng.integers(0, 6)
            trial[j] = clamp(trial[j] + rng.normal(0.0, steps[j]), LO[j], HI[j])
        if trial[0] > 4.5e-4:
            trial[0] = 4.5e-4
        s, _ = evaluate(trial, exp)
        if s > score:
            best, score = trial, s
            steps *= 0.98
        else:
            steps *= 0.985
        if it % 40 == 39:
            print(it, round(score, 2), np.round(best, 5).tolist())

    vs, vrep = evaluate(best, val)
    rationale += (
        "\n## Selected coefficients\n\n"
        + json.dumps({k: float(v) for k, v in zip(KEYS, best)}, indent=2)
        + "\n\nTraining (seed 6111006, 3 variants x 3 patients): %s\n"
        % {k: v for k, v in rep.items() if k != 'rows'}
        + "\nHeld-out seeds: %s\n" % {k: v for k, v in vrep.items() if k != 'rows'}
        + "\nSearch: random-restart coordinate refinement with penalty for\n"
          "TBR70>3%, TBR54>0.5%, minute glucose<60 mg/dL; amplitude capped at\n"
          "4.5e-4 because larger shared rates drive child patients hypoglycaemic.\n")
    write_all({"mode": "responsive",
               "parameters": {k: float(v) for k, v in zip(KEYS, best)}}, rationale)
    print('FINAL', {k: v for k, v in rep.items() if k != 'rows'})
    print('VAL  ', {k: v for k, v in vrep.items() if k != 'rows'})


if __name__ == '__main__':\n    main()\nPYEOF
python -c "compile(open('/work/output/search.py').read(),'s','exec')" && echo OK
