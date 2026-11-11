#!/usr/bin/env python3
"""Reproducible search for GRI static formulation (instance dev-02).

Usage: python3 search.py --budget <cpu_seconds>
Evaluates candidate designs with gri_bench Experiment, keeps the best SAFE
design (TBR70<=4%, TBR54<=1%, min glucose>=40) by mean TIR; saves design.json
atomically after every improvement (checkpointing).
"""
import argparse, json, os, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ["theta_a", "relative_leak", "ec50_mg_dl", "hill_n", "tau_min", "theta_L"]

def design_from(x):
    return {"mode": "responsive", "parameters": {k: float(v) for k, v in zip(KEYS, x)}}

def atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)

def get_first(d, names, collect=False, out=None):
    """Recursively find metrics by key name (metrics dict shape unknown)."""
    if out is None: out = []
    if isinstance(d, dict):
        for n in names:
            if n in d: out.append(d[n])
        for v in d.values(): get_first(v, names, True, out)
    elif isinstance(d, (list, tuple)):
        for v in d: get_first(v, names, True, out)
    return out

def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=15.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    from gri_bench.api import load_instance, Experiment
    inst = load_instance()
    exp = Experiment(inst)
    bounds = [inst["bounds"][k] for k in KEYS]
    x0 = np.array([0.0002, 1.5, 200.0, 2.0, 10.0, 1.0])
    rng = np.random.default_rng(args.seed)
    best = [None]
    n_eval = [0]

    def try_x(x, tag=""):
        n_eval[0] += 1
        d = design_from(x)
        try:
            m = exp.evaluate(d)
        except Exception as e:
            print("ERR", tag, e, flush=True); return None
        tir = get_first(m, ["mean_tir"])
        tir = max(tir) if tir else None
        tbr70 = max(get_first(m, ["tbr70"]) or [9.9])
        tbr54 = max(get_first(m, ["tbr54"]) or [9.9])
        ming  = min(get_first(m, ["min_glucose", "min_g", "minimum_glucose"]) or [-9.9])
        safe = tir is not None and tbr70 <= 0.04 and tbr54 <= 0.01 and ming >= 40.0
        key = (tir if safe else tir - 10.0)
        if best[0] is None or key > best[0][0]:
            best[0] = (key, x.copy())
            atomic_json(os.path.join(HERE, "design.json"), d)
            atomic_json(os.path.join(HERE, "best_metrics.json"), m)
            print("BEST%s" % tag, np.round(x, 6).tolist(), "tir=%.4f" % tir,
                  "tbr70=%.5f tbr54=%.5f ming=%.1f" % (tbr70, tbr54, ming),
                  "safe=%s" % safe, flush=True)
        return key

    try_x(x0, "-x0")
    i = 0
    while time.time() - t0 < args.budget:
        i += 1
        scale = 0.5 ** (1 + i // 6)
        base = best[0][1] if (best[0] is not None and i % 2 == 1) else x0
        x = np.array(base, float)
        j = int(rng.integers(0, len(x)))
        lo, hi = bounds[j]
        if base[j] > 0:
            x[j] = float(np.clip(base[j] * (1 + scale * rng.normal()), lo, hi))
        else:
            x[j] = float(rng.uniform(lo, hi))
        try_x(x)
    print("done evals=%d" % n_eval[0], "wall=%.1f" % (time.time() - t0), flush=True)

if __name__ == "__main__":
    main()
