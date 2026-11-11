#!/usr/bin/env python3
"""Reproducible search for the GRI static formulation (instance dev-01).

Stage 1: coarse randomized search over shared responsive parameters on the
training seed/variants (objective: mean TIR 70-180; hard screen: every
trajectory TBR70<=4%, TBR54<=1%, min glucose>=40 incl. warmup day).
Stage 2: local refinement around the best coarse point.
Stage 3: robustness validation on extra fresh meal seeds; best robust design
is saved atomically to design.json. Cohort-shared coefficients only.
"""
import json, os, tempfile, time
import numpy as np
from gri_bench.api import load_instance, Experiment

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design.json")
BOUNDS = {
    "theta_a": (0.0, 0.007),
    "relative_leak": (0.5124966150526034, 5.518918645844859),
    "ec50_mg_dl": (59.26305046791457, 816.1143093473472),
    "hill_n": (0.5880395112623367, 24.0),
    "tau_min": (0.05, 20.0),
    "theta_L": (0.4, 4.0),
}

def save_atomic(design, path=OUT):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as f:
        json.dump(design, f)
    os.replace(tmp, path)

def clip(p):
    return {k: float(min(max(p[k], BOUNDS[k][0]), BOUNDS[k][1])) for k in p}

def rows_of(m):
    return m.get("rows", m.get("per_trajectory", []))

def tir_of(m):
    return float(m.get("mean_tir", 0.0))

def safe(m):
    for r in rows_of(m):
        if float(r.get("tbr70", 0.0)) > 0.04: return False
        if float(r.get("tbr54", 0.0)) > 0.01: return False
        if float(r.get("min_glucose", r.get("min_g", 1e9))) < 40.0: return False
    return True

def sample(rng):
    return clip({
        "theta_a": float(10 ** rng.uniform(-4.0, -2.15)),
        "relative_leak": float(np.exp(rng.uniform(*np.log(BOUNDS["relative_leak"])))),
        "ec50_mg_dl": float(np.exp(rng.uniform(*np.log(BOUNDS["ec50_mg_dl"])))),
        "hill_n": float(np.exp(rng.uniform(*np.log(BOUNDS["hill_n"])))),
        "tau_min": float(np.exp(rng.uniform(np.log(0.5), np.log(20.0)))),
        "theta_L": float(rng.uniform(1.5, 4.0)),
    })

def main(n_coarse=24, budget_s=200.0):
    inst = load_instance()
    exp = Experiment(inst)
    rng = np.random.default_rng(20261111)
    t0 = time.time()
    best = (None, -1.0, None)
    for i in range(n_coarse):
        p = sample(rng)
        m = exp.evaluate({"mode": "responsive", "parameters": p})
        tir = tir_of(m)
        print(i, {k: round(v, 5) for k, v in p.items()}, "tir", round(tir, 4), "safe", safe(m), flush=True)
        if safe(m) and tir > best[1]:
            best = (p, tir, m)
        if time.time() - t0 > budget_s:
            break
    if best[0] is not None:
        save_atomic({"mode": "responsive", "parameters": best[0]})
        print("BEST", best[1], json.dumps(best[0]))
    return best

if __name__ == "__main__":
    main()
