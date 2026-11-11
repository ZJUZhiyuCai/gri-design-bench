# Reproducible search for GRI static formulation (dev-02)
# Strategy: random + local refinement over responsive parameters,
# objective = mean post-warmup TIR with hard safety penalties.
import json, numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

def score(design, exp):
    m = exp.evaluate(design)
    tir = m["mean_tir"]
    # hard safety: any TBR70>4%, TBR54>1%, or min glucose <40 -> 0
    if m.get("max_tbr70", 0) > 4.0 or m.get("max_tbr54", 0) > 1.0 or m.get("min_glucose", 999) < 40.0:
        return 0.0
    return tir

def main():
    inst = load_instance()
    exp = Experiment(inst)
    rng = np.random.default_rng(0)
    lo = [0.0001, 0.6, 80.0, 0.8, 1.0, 0.5]
    hi = [0.002, 3.0, 400.0, 6.0, 15.0, 2.0]
    best, bs = None, -1
    for i in range(40):
        x = rng.uniform(lo, hi)
        d = {"mode":"responsive","parameters":dict(zip(PARAMETERS, x))}
        s = score(d, exp)
        if s > bs: bs, best = s, d
    print(best, bs)
    save_design(best)

if __name__ == "__main__":
    main()
