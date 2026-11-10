"""Reproducible search for GRI static formulation design (instance dev-01).

Strategy: grid/random search over shared responsive-mode parameters using the
gri_bench Experiment API (fast RK4), scoring mean TIR with hard safety
penalties (TBR70<=4%, TBR54<=1%, min glucose>=40). Best design saved to
design.json atomically.
"""
import json, os, itertools
from gri_bench.api import load_instance, Experiment

BOUNDS = {
    "theta_a": (0.0, 0.007),
    "relative_leak": (0.5124966150526034, 5.518918645844859),
    "ec50_mg_dl": (59.26305046791457, 816.1143093473472),
    "hill_n": (0.5880395112623367, 24.0),
    "tau_min": (0.05, 20.0),
    "theta_L": (0.4, 4.0),
}

def clip(p):
    q = dict(p)
    for k,(lo,hi) in BOUNDS.items():
        q[k] = min(hi, max(lo, q[k]))
    return q

def score(m, penalty=100.0):
    s = m["mean_tir"]
    viol = 0.0
    for row in m.get("rows", []):
        viol += max(0.0, row["tbr70"]-0.04) + max(0.0, row["tbr54"]-0.01)
        viol += max(0.0, 0.40 - row["min_glucose"])
    return s - penalty*viol, viol

def main():
    inst = load_instance()
    exp = Experiment(inst)
    best = None
    grid = {
        "theta_a": [0.0008, 0.0013, 0.002, 0.003],
        "relative_leak": [0.6, 1.0, 1.6],
        "ec50_mg_dl": [120.0, 200.0, 320.0],
        "hill_n": [2.0, 4.0],
        "tau_min": [8.0, 14.0],
        "theta_L": [1.5, 2.5],
    }
    keys = list(grid)
    for vals in itertools.product(*[grid[k] for k in keys]):
        p = dict(zip(keys, vals))
        d = {"mode":"responsive","parameters":p}
        m = exp.evaluate(d)
        sc, viol = score(m)
        if best is None or sc > best[0]:
            best = (sc, viol, p, m["mean_tir"])
    print("BEST", best)
    d = {"mode":"responsive","parameters":clip(best[2])}
    tmp = "/work/output/design.json.tmp"
    with open(tmp,"w") as f: json.dump(d,f)
    os.replace(tmp, "/work/output/design.json")

if __name__ == "__main__":
    main()
