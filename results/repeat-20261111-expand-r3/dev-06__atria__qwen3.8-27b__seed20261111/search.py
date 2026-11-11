# Reproducible search for GRI static formulation (dev-06)
# Strategy: coarse grid + local refinement over responsive parameters,
# scored by mean post-warmup TIR with hard safety penalties.
import json, numpy as np
from gri_bench.api import load_instance, Experiment, save_design

def score(design, exp):
    m = exp.evaluate(design)
    tir = m["mean_tir"]
    # hard constraints: TBR70<=4%, TBR54<=1%, min glucose >=40
    pen = 0.0
    if m["mean_tbr70"] > 4.0: pen += (m["mean_tbr70"]-4.0)*10
    if m["mean_tbr54"] > 1.0: pen += (m["mean_tbr54"]-1.0)*10
    if m["min_glucose"] < 40.0: pen += (40.0-m["min_glucose"])*10
    return tir - pen, m

def main():
    inst = load_instance()
    exp = Experiment(inst)
    best = (0.0, None)
    # coarse grid
    for ta in [0.0002, 0.0005, 0.001]:
        for rl in [1.0, 2.0, 3.0]:
            for ec in [150.0, 250.0]:
                for hn in [1.5, 2.5]:
                    for tm in [8.0, 15.0]:
                        for tl in [0.8, 1.5]:
                            d = {"mode":"responsive","parameters":{"theta_a":ta,"relative_leak":rl,
                                 "ec50_mg_dl":ec,"hill_n":hn,"tau_min":tm,"theta_L":tl}}
                            s, m = score(d, exp)
                            if s > best[0]:
                                best = (s, d)
                                print("best", s, d)
    save_design(best[1])

if __name__ == "__main__":
    main()
