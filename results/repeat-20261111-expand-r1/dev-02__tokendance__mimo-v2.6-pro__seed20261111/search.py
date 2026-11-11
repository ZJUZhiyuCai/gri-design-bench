"""Reproducible seeded search for the GRI static formulation (instance dev-02).

Objective: maximize mean post-warmup TIR over the cohort's training scenarios,
subject to hard safety (TBR70<=4%, TBR54<=1%, full-horizon min glucose>=40).
All coefficients are shared across the cohort (no per-patient fitting).

Stages
  1. coarse log-space random search on the training seed (fast screening)
  2. coordinate/pattern refinement on the training seed
  3. robustness validation of the top candidates on extra meal seeds
     (fresh-seed generalisation proxy), selecting the best robust design
  4. robust local refinement and atomic checkpointing of design.json

Run: python search.py   (CPU-guarded; see MAX_CPU_SECONDS)
"""
import json
import time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

MAX_CPU_SECONDS = 16.0
SEED = 2026111101
INSTANCE = load_instance()
BOUNDS = INSTANCE['bounds']
EXP_TRAIN = Experiment(INSTANCE)                       # 3 patients x 3 variants
EXP_ROBUST = Experiment(INSTANCE, seeds=[6111002, 77001, 77002],
                        variants=INSTANCE['variants'])
RNG = np.random.default_rng(SEED)
START = time.process_time()


def clip(p):
    return {k: float(min(BOUNDS[k][1], max(BOUNDS[k][0], p[k]))) for k in PARAMETERS}


def score(p, exp):
    m = exp.evaluate({'mode': 'responsive', 'parameters': p})
    return m['safe_tir'], m


def robust_score(p):
    """Mean TIR across seeds minus spread penalty; infeasible => 0."""
    s, mm = score(p, EXP_ROBUST)
    if not mm['feasible']:
        return 0.0, mm
    tirs = [r['metrics']['tir'] for r in mm['rows']]
    return float(np.mean(tirs) - 0.5 * np.std(tirs)), mm


def sample_prior():
    """Log-uniform-ish draw biased to physiologically plausible regions."""
    theta_a = float(np.exp(RNG.uniform(np.log(6e-5), np.log(1.2e-3))))
    leak = float(np.exp(RNG.uniform(np.log(0.55), np.log(3.0))))
    ec50 = float(np.exp(RNG.uniform(np.log(80.0), np.log(450.0))))
    hill = float(np.exp(RNG.uniform(np.log(1.0), np.log(12.0))))
    tau = float(np.exp(RNG.uniform(np.log(1.0), np.log(16.0))))
    # reservoir sized so 3-day delivery is not truncated too early
    need = 4320.0 * theta_a * (leak + 0.5)
    if RNG.random() < 0.7:
        theta_L = float(np.clip(1.15 * need, *BOUNDS['theta_L']))
    else:
        theta_L = float(np.exp(RNG.uniform(np.log(0.8), np.log(4.0))))
    return clip({'theta_a': theta_a, 'relative_leak': leak, 'ec50_mg_dl': ec50,
                 'hill_n': hill, 'tau_min': tau, 'theta_L': theta_L})


def main():
    log = []
    # ---- stage 1: coarse random screen on the training seed -----------------
    cands = []
    base = {'theta_a': 0.00025, 'relative_leak': 1.2, 'ec50_mg_dl': 160.0,
            'hill_n': 4.0, 'tau_min': 6.0, 'theta_L': 3.0}
    for p in [base] + [sample_prior() for _ in range(34)]:
        s, _ = score(p, EXP_TRAIN)
        cands.append((s, p))
    cands.sort(key=lambda t: -t[0])
    best_s, best_p = cands[0]
    log.append(('coarse', best_s))

    # ---- stage 2: pattern refinement on the training seed ------------------
    step = {'theta_a': 0.45, 'relative_leak': 0.35, 'ec50_mg_dl': 0.30,
            'hill_n': 0.50, 'tau_min': 0.60, 'theta_L': 0.18}
    for it in range(42):
        if time.process_time() - START > MAX_CPU_SECONDS * 0.45:
            break
        scale = 0.45 if it < 21 else 0.18
        cand = {k: best_p[k] * np.exp(RNG.normal(0, step[k] * scale)) for k in PARAMETERS}
        cand = clip(cand)
        s, _ = score(cand, EXP_TRAIN)
        if s > best_s:
            best_s, best_p = s, cand
        if it % 12 == 0:
            for k in PARAMETERS:                       # axis probes
                for d in (1.18, 1 / 1.18):
                    probe = clip({**best_p, k: best_p[k] * d})
                    sp, _ = score(probe, EXP_TRAIN)
                    if sp > best_s:
                        best_s, best_p = sp, probe
    log.append(('refine', best_s))

    # ---- stage 3: robustness validation of top designs on extra seeds ------
    pool = [best_p] + [p for _, p in cands[:6]]
    robust = []
    for p in pool:
        if time.process_time() - START > MAX_CPU_SECONDS * 0.75:
            break
        r, _ = robust_score(p)
        robust.append((r, p))
    robust.sort(key=lambda t: -t[0])
    best_r, best_p = robust[0]
    log.append(('robust', best_r))

    # ---- stage 4: robust local refinement + checkpointing ------------------
    for it in range(20):
        if time.process_time() - START > MAX_CPU_SECONDS * 0.95:
            break
        scale = 0.30 if it < 10 else 0.12
        cand = clip({k: best_p[k] * np.exp(RNG.normal(0, step[k] * scale)) for k in PARAMETERS})
        r, _ = robust_score(cand)
        if r > best_r:
            best_r, best_p = r, cand
            save_design({'mode': 'responsive', 'parameters': best_p})
    save_design({'mode': 'responsive', 'parameters': best_p})
    _, final_m = robust_score(best_p)
    print(json.dumps({'log': log, 'robust_score': best_r, 'parameters': best_p,
                      'robust_metrics': {k: v for k, v in final_m.items() if k != 'rows'}},
                     indent=2, default=str))


if __name__ == '__main__':
    main()
