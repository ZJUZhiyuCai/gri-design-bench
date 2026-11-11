"""GRI static formulation search (reproducible).

Searches the shared responsive parameter space for the known cohort,
maximizing mean post-warmup TIR subject to safety margins, then validates
the top candidates on fresh meal seeds. theta_L is set to its upper bound
(a larger reservoir only relaxes the mass cap, never hurts).
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, individual_design, glucose_metrics
from gri_bench.physiology import fast_trace

# safety margins (final: tbr70<=4, tbr54<=1, min>=40)
M_TBR70, M_TBR54, M_MIN = 3.0, 0.7, 44.0

def score_of(rows):
    tirs = [r['tir'] for r in rows]
    tbr70 = max(r['tbr70'] for r in rows)
    tbr54 = max(r['tbr54'] for r in rows)
    ming = min(r['minimum'] for r in rows)
    mean_tir = float(np.mean(tirs))
    feasible = (tbr70 <= M_TBR70 and tbr54 <= M_TBR54 and ming >= M_MIN)
    pen = (10*max(0., tbr70-M_TBR70) + 10*max(0., tbr54-M_TBR54) + 10*max(0., M_MIN-ming))
    return mean_tir - pen, feasible, mean_tir, tbr70, tbr54, ming

def run(exp, instance, params):
    design = {"mode":"responsive","parameters":{**params,"theta_L":4.0}}
    rows = []
    for name,seed,variant,p,initial,meals in exp.jobs:
        tr = fast_trace(p, initial, meals, individual_design(design, instance['tdi'][name]))
        rows.append(glucose_metrics(tr, 1440))
    return score_of(rows)

def sample(rng):
    return {
        "theta_a": float(np.exp(rng.uniform(np.log(1.5e-4), np.log(1.5e-3)))),
        "relative_leak": float(rng.uniform(1.5, 4.0)),
        "ec50_mg_dl": float(np.exp(rng.uniform(np.log(80), np.log(320)))),
        "hill_n": float(np.exp(rng.uniform(np.log(1.0), np.log(10.0)))),
        "tau_min": float(np.exp(rng.uniform(np.log(1.0), np.log(12.0)))),
    }

def main():
    instance = load_instance()
    exp = Experiment(instance)
    rng = np.random.default_rng(0)
    best = None
    t0 = time.time()
    # Phase 1: random
    for i in range(110):
        p = sample(rng)
        s, feas, mt, a, b, m = run(exp, instance, p)
        if best is None or s > best[0]:
            best = (s, p, feas, mt, a, b, m)
            print(f"[r{i}] score={s:.2f} feas={feas} tir={mt:.1f} tbr70={a:.2f} tbr54={b:.2f} min={m:.1f} {p}", flush=True)
    # Phase 2: local refinement around best
    cur = dict(best[1]); cur_s = best[0]
    for i in range(45):
        p = {k: float(np.clip(v*np.exp(rng.normal(0, 0.25)), lo, hi))
             for k, v in cur.items() for lo, hi in [(instance['bounds'][k][0], instance['bounds'][k][1])]}
        s, feas, mt, a, b, m = run(exp, instance, p)
        if s > cur_s:
            cur_s, cur = s, p
            if s > best[0]:
                best = (s, p, feas, mt, a, b, m)
            print(f"[l{i}] score={s:.2f} feas={feas} tir={mt:.1f} tbr70={a:.2f} tbr54={b:.2f} min={m:.1f}", flush=True)
    print("BEST(train):", best[0], best[2], {k: round(v,5) for k,v in best[1].items()}, flush=True)
    # Phase 3: validate top design on fresh seeds
    from gri_bench.api import Experiment as E2
    for vseed in [111, 222, 333, 444]:
        ev = E2(instance, seeds=[vseed])
        s, feas, mt, a, b, m = run(ev, instance, best[1])
        print(f"[val seed={vseed}] score={s:.2f} feas={feas} tir={mt:.1f} tbr70={a:.2f} tbr54={b:.2f} min={m:.1f}", flush=True)
    design = {"mode":"responsive","parameters":{**best[1],"theta_L":4.0}}
    from gri_bench.api import save_design
    save_design(design)
    print("SAVED", design, "elapsed", time.time()-t0, flush=True)

if __name__ == "__main__":
    main()
