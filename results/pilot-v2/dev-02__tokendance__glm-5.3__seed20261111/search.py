#!/usr/bin/env python3
"""Reproducible budgeted search for GRI dev-02 (shared responsive-shape design).

Stage A: hand anchors + log-uniform random sampling in the instance bounds.
Stage B: local Gaussian refinement around the best feasible candidate.
Stage C: revalidation of the top candidates on extra RandomScenario seeds.
Scoring: mean_tir with hard-safety penalties (TBR70>4, TBR54>1, min<40 => huge).
Everything is deterministic (fixed RNG seeds); best design saved atomically.
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

T0 = time.process_time()
DL_SEARCH, DL_TOTAL = 13.0, 21.0
BOUNDS = np.array([
    [0.0, 0.007],
    [0.5124966150526034, 5.518918645844859],
    [59.26305046791457, 816.1143093473472],
    [0.5880395112623367, 24.0],
    [0.05, 20.0],
    [0.4, 4.0]])

def design(x):
    ta, lk, ec, n, tau, L = [float(v) for v in x]
    return {"mode": "responsive", "parameters": {
        "theta_a": ta, "relative_leak": lk, "ec50_mg_dl": ec,
        "hill_n": n, "tau_min": tau, "theta_L": L}}

def pen(res):
    if res["feasible"]:
        return 0.0
    return (max(0.0, res["max_trajectory_tbr70"] - 4.0) / 4.0
            + max(0.0, res["max_trajectory_tbr54"] - 1.0)
            + max(0.0, 40.0 - res["minimum_glucose"]) / 40.0)

def obj(res):
    return res["mean_tir"] - 2000.0 * pen(res)

def to_x(u):
    return BOUNDS[:, 0] + np.clip(u, 0, 1) * (BOUNDS[:, 1] - BOUNDS[:, 0])

def to_u(x):
    return (np.asarray(x, float) - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])

def main():
    instance = load_instance()
    train = Experiment(instance)
    hist = []

    def probe(u, tag=""):
        x = to_x(u)
        r = train.evaluate(design(x))
        hist.append((obj(r), u.copy(), r))
        print("%6.2fs %-4s tir=%6.2f pen=%.3f min=%5.1f tbr70=%.2f p=%s" % (
            time.process_time() - T0, tag, r["mean_tir"], pen(r), r["minimum_glucose"],
            r["max_trajectory_tbr70"], np.round(x, 5).tolist()), flush=True)
        return r

    anchors = [
        [5.6e-4, 0.8, 150.0, 3.0, 12.0, 3.5],
        [4.5e-4, 0.6, 160.0, 2.5, 18.0, 4.0],
        [8.0e-4, 0.55, 120.0, 6.0, 10.0, 4.0],
        [3.5e-4, 1.2, 200.0, 2.0, 20.0, 4.0],
        [1.0e-3, 0.5125, 130.0, 10.0, 8.0, 4.0]]
    for i, a in enumerate(anchors):
        probe(np.clip(to_u(a), 0, 1), "A%d" % i)
        if time.process_time() - T0 > DL_SEARCH:
            break
    rng = np.random.default_rng(2026111101)
    n_rand = 0
    while time.process_time() - T0 < DL_SEARCH * 0.55 and n_rand < 45:
        probe(rng.random(6), "R%d" % n_rand)
        n_rand += 1
    if hist:
        hist.sort(key=lambda t: -t[0])
        best_u = hist[0][1].copy(); best_o = hist[0][0]
        sigma = 0.14
        k = 0
        while time.process_time() - T0 < DL_SEARCH and k < 60:
            u = np.clip(best_u + rng.normal(0, sigma, 6), 0, 1)
            x = to_x(u); r = train.evaluate(design(x)); k += 1
            o = obj(r)
            if o > best_o:
                best_o, best_u = o, u.copy()
            if k % 5 == 0:
                print("%6.2fs L%-3d tir=%6.2f pen=%.3f best=%.2f sig=%.3f" % (
                    time.process_time() - T0, k, r["mean_tir"], pen(r), best_o, sigma), flush=True)
            if k % 12 == 0:
                sigma = max(0.04, sigma * 0.6)
            hist.append((o, u.copy(), r))
        hist.sort(key=lambda t: -t[0])

    print("=== validation on extra seeds ===", flush=True)
    top = []
    seen = set()
    for o, u, r in hist:
        key = tuple(np.round(u, 4))
        if key in seen:
            continue
        seen.add(key); top.append((o, u, r))
        if len(top) >= 4:
            break
    seeds = instance["training_seeds"] + [424242, 909909]
    val = Experiment(instance, seeds=seeds)
    final, final_score, final_res = None, -1e9, None
    for o, u, r0 in top:
        if time.process_time() - T0 > DL_TOTAL:
            break
        res = val.evaluate(design(to_x(u)))
        worst = min(tir if fea else -1e9 for tir, fea in ((rr["metrics"]["tir"], True) for rr in res["rows"]))
        feas = res["feasible"]
        sc = (res["mean_tir"] if feas else -1e6) - 2000.0 * pen(res)
        print("  val tir=%6.2f feas=%s min=%5.1f tbr70=%.2f score=%.2f p=%s" % (
            res["mean_tir"], feas, res["minimum_glucose"], res["max_trajectory_tbr70"],
            sc, np.round(to_x(u), 5).tolist()), flush=True)
        if sc > final_score:
            final, final_score, final_res = design(to_x(u)), sc, res
    if final is None:
        hist.sort(key=lambda t: -t[0])
        final = design(to_x(hist[0][1])); final_res = hist[0][2]
    save_design(final)
    print("=== FINAL ===", json.dumps(final))
    if final_res is not None and "rows" in final_res:
        for rr in final_res["rows"]:
            m = rr["metrics"]
            print("  %s s%s %-13s tir=%6.2f tbr70=%5.2f tbr54=%5.2f min=%6.1f mean=%6.1f" % (
                rr["patient"], rr["seed"], rr["variant"], m["tir"], m["tbr70"], m["tbr54"], m["minimum"], m["mean_glucose"]))
    print("cpu_total=%.2f" % (time.process_time() - T0))

if __name__ == "__main__":
    main()
