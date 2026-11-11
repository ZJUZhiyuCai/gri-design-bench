"""Reproducible search for the GRI static formulation of instance dev-04.

Responsive design:  rate(t) = theta_a*TDI * [relative_leak + Hill(G_filt; ec50, n)]
                    filtered interstitial glucose (exact first-order filter),
                    midpoint flux every 3 min, finite reservoir theta_L*TDI.
Mode: responsive. All six coefficients are shared by the whole cohort.

Pipeline
--------
1. Start population: log-uniform random draws + structured guesses spanning the two
   qualitative regimes (flat/uniform spend vs. sharp high-threshold switch).
2. (6+1) evolution strategy in normalised log-parameter space, scoring each
   candidate with the fast RK4 cohort evaluator (3 patients x 3 variants):
       score = mean post-warmup TIR, gated to a large negative value if any
       trajectory violates TBR70<=4%, TBR54<=1% or min plasma glucose<40 mg/dL,
       minus a small margin penalty on minima below 70 mg/dL.
3. Robustness screen: top candidates are re-evaluated on additional unseen meal
   seeds (6111005, 6111006); the submitted design maximises the worst-seed TIR
   subject to feasibility on every seed.

Run:  python search.py      (writes /work/output/design.json)
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

SEED0 = 20261111
EXTRA_SEEDS = [6111005, 6111006]


def to_design(v):
    return {"mode": "responsive",
            "parameters": {k: float(x) for k, x in zip(PARAMETERS, v)}}


def score(m):
    """Feasibility-gated mean TIR with a soft safety margin on the minimum glucose."""
    if not m["feasible"]:
        return -1000.0 - 10.0 * m["max_trajectory_tbr70"] - 100.0 * m["max_trajectory_tbr54"]
    return m["mean_tir"] - 0.5 * max(0.0, 70.0 - m["minimum_glucose"])


def main(evals=175):
    inst = load_instance()
    b = inst["bounds"]
    LO = np.array([b[k][0] for k in PARAMETERS], float)
    HI = np.array([b[k][1] for k in PARAMETERS], float)
    ex = Experiment(inst)                      # training seed 6111004
    rng = np.random.default_rng(SEED0)

    def raw_to_v(z):
        lo = np.maximum(LO, 1e-4)
        return np.clip(np.exp(np.log(lo) + z * (np.log(HI) - np.log(lo))), LO, HI)

    def v_to_z(v):
        lo = np.maximum(LO, 1e-4)
        return (np.log(np.maximum(v, 1e-4)) - np.log(lo)) / (np.log(HI) - np.log(lo))

    zs = [rng.random(6) for _ in range(24)]
    for a, leak, ec, n, tau in [(2e-4, 0.6, 170., 8., 3.), (4e-4, 0.6, 170., 8., 3.),
                                (4e-4, 1.1, 210., 5., 0.5), (1.5e-4, 0.6, 150., 10., 6.),
                                (7e-4, 0.8, 200., 6., 2.), (1e-3, 0.6, 250., 12., 1.),
                                (7e-5, 5.5, 200., 3., 2.)]:
        zs.append(v_to_z(np.array([a, leak, ec, n, tau, 1.25])))
    pop = [np.clip(z, 0.0, 1.0) for z in zs]
    fit = [score(ex.evaluate(to_design(raw_to_v(z)))) for z in pop]
    n_ev, sigma, t0 = len(pop), 0.18, time.time()
    while n_ev < evals:
        order = np.argsort(fit)[::-1]
        mu = [pop[i] for i in order[:6]]
        child = np.clip(mu[rng.integers(len(mu))] + sigma * rng.standard_normal(6), -0.05, 1.05)
        s = score(ex.evaluate(to_design(raw_to_v(child))))
        n_ev += 1
        worst = int(np.argmin(fit))
        if s > fit[worst]:
            pop[worst], fit[worst] = child, s
        if n_ev % 40 == 0:
            sigma = max(0.05, 0.9 * sigma)
    print("evals", n_ev, "elapsed", round(time.time() - t0, 1))

    order = np.argsort(fit)[::-1]
    results = []
    for i in order[:5]:
        design = to_design(raw_to_v(pop[i]))
        tir, ok, mins = [], True, []
        for sd in [6111004] + EXTRA_SEEDS:
            mx = ex if sd == 6111004 else Experiment(inst, seeds=[sd])
            m = mx.evaluate(design)
            tir.append(m["mean_tir"]); ok &= m["feasible"]; mins.append(m["minimum_glucose"])
        results.append((raw_to_v(pop[i]), tir, ok, min(mins)))
        print("cand", np.round(results[-1][0], 6).tolist(), "TIR", np.round(tir, 1).tolist(),
              "feasible", ok, "minG", round(min(mins), 1))
    feasible = [r for r in results if r[2]] or results
    best = max(feasible, key=lambda r: (min(r[1]), float(np.mean(r[1]))))
    design = to_design(best[0])
    print("CHOSEN", json.dumps(design))
    save_design(design)
    return design


if __name__ == "__main__":
    main()
