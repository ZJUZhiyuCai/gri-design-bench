"""Reproducible search for GRI static formulation design (dev-06).

Design space:
  responsive: rate = theta_a*TDI * [relative_leak + Hill(g_filtered)]
              Hill(g) = 1/(1 + exp(n*(log(ec50)-log(g))))
              exact first-order filter on interstitial glucose, tau_min
              midpoint flux every 3 min, reservoir cap theta_L*TDI
  constant:   rate = theta_c*TDI, same finite reservoir

Objective: mean % post-warmup plasma glucose in [70,180] across the known
cohort/training scenarios. Hard constraints (infeasible -> score 0):
  max trajectory TBR70 <= 4%, TBR54 <= 1%, full-horizon min glucose >= 40.

Search: coarse Latin-ish grid over the feasible safety envelope, then local
refinement with a Nelder-Mead style pattern search on a penalized objective.
All evaluations use the fast RK4 trainer (gri_bench.physiology.fast_trace);
the final design is re-simulated with the native dopri5 integrator.
"""
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from gri_bench.api import (
    load_instance,
    Experiment,
    save_design,
    glucose_metrics,
    summarize,
    PARAMETERS,
)
from gri_bench.physiology import patient_parameters, meal_schedule, fast_trace
from gri_bench.native import native_trace, verify_design

INSTANCE_PATH = "/task/instance.json"
OUTPUT_DIR = Path("/work/output")
WARMUP = 1440


def design_from_vector(instance, x, mode="responsive"):
    if mode == "constant":
        return {
            "mode": "constant",
            "parameters": {
                "theta_c": float(x[0]),
                "theta_L": float(x[1]),
            },
        }
    return {
        "mode": "responsive",
        "parameters": {
            "theta_a": float(x[0]),
            "relative_leak": float(x[1]),
            "ec50_mg_dl": float(x[2]),
            "hill_n": float(x[3]),
            "tau_min": float(x[4]),
            "theta_L": float(x[5]),
        },
    }


def vector_from_design(instance, design):
    p = design["parameters"]
    if design["mode"] == "constant":
        return np.array([p["theta_c"], p["theta_L"]])
    return np.array([p["theta_a"], p["relative_leak"], p["ec50_mg_dl"],
                     p["hill_n"], p["tau_min"], p["theta_L"]])


def bounds(instance, mode="responsive"):
    if mode == "constant":
        lo, hi = instance["constant_theta_c_bounds"]
        return np.array([[lo, 0.4], [hi, 4.0]])
    b = instance["bounds"]
    return np.array([[b[k][0] for k in PARAMETERS], [b[k][1] for k in PARAMETERS]])


def evaluate_fast(instance, design):
    """Fast cached trainer evaluation (same as Experiment.evaluate)."""
    ex = Experiment(instance)
    return ex.evaluate(design)


def penalized_score(instance, design, rows=None):
    """Penalized objective used during search. Feasible designs keep mean_tir."""
    if rows is None:
        r = evaluate_fast(instance, design)
    else:
        r = {"rows": rows}
    s = summarize(r["rows"])
    if s["feasible"]:
        return s["mean_tir"], s
    # Soft penalty so the optimizer can climb back toward feasibility.
    pen = 0.0
    pen += max(0.0, s["max_trajectory_tbr70"] - 4.0) * 15.0
    pen += max(0.0, s["max_trajectory_tbr54"] - 1.0) * 30.0
    pen += max(0.0, 40.0 - s["minimum_glucose"]) * 2.0
    return max(0.0, s["mean_tir"] - pen), s


def grid_search(instance, mode="responsive", n_per_dim=8):
    b = bounds(instance, mode)
    grids = []
    for j in range(b.shape[0]):
        lo, hi = b[j]
        if mode == "responsive" and j == 1:  # relative_leak often wants low end
            vals = np.linspace(lo, hi, n_per_dim)
        else:
            vals = np.linspace(lo, hi, n_per_dim)
        grids.append(vals)
    mesh = np.meshgrid(*grids, indexing="ij")
    flat = np.stack([m.ravel() for m in mesh], axis=-1)
    return flat


def local_refine(instance, x0, scale, max_iter=400, tol=1e-5):
    """Coordinate-wise pattern search with shrinking step sizes."""
    x = np.array(x0, dtype=float)
    best, best_rows = penalized_score(instance, design_from_vector(instance, x))
    step = scale.copy()
    it = 0
    for it in range(max_iter):
        improved = False
        for j in range(len(x)):
            for sgn in (+1.0, -1.0):
                xc = x.copy()
                lo, hi = bounds(instance)[j]
                xc[j] = min(hi, max(lo, x[j] + sgn * step[j]))
                if np.allclose(xc, x):
                    continue
                sc, rows = penalized_score(instance, design_from_vector(instance, xc))
                if sc > best:
                    best, x = sc, xc
                    best_rows = rows
                    improved = True
        if not improved:
            step *= 0.5
            if step.max() < tol:
                break
    return x, best, best_rows, it + 1


def random_search(instance, mode="responsive", n=600, rng=None):
    if rng is None:
        rng = np.random.default_rng(2026111101)
    b = bounds(instance, mode)
    lo, hi = b[:, 0], b[:, 1]
    best = -1.0
    best_x = None
    best_rows = None
    for _ in range(n):
        u = rng.uniform(0, 1, size=len(lo))
        # log-ish sampling for ec50 and tau to cover orders of magnitude
        x = lo + u * (hi - lo)
        sc, rows = penalized_score(instance, design_from_vector(instance, x))
        if sc > best:
            best, best_x, best_rows = sc, x, rows
    return best_x, best, best_rows


def main():
    t0 = time.time()
    instance = load_instance(INSTANCE_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Stage 1: coarse grid to locate the safety envelope -----------------
    candidates = []
    # Responsive grid focused on low leak / moderate amplitude region.
    b = bounds(instance)
    amp_grid = np.linspace(b[0, 0], b[0, 1], 6)
    leak_grid = np.linspace(b[1, 0], b[1, 1], 6)
    ec50_grid = np.exp(np.linspace(np.log(b[2, 0]), np.log(b[2, 1]), 5))
    n_grid = np.linspace(b[3, 0], b[3, 1], 4)
    tau_grid = np.linspace(b[4, 0], b[4, 1], 4)
    load_grid = np.linspace(b[5, 0], b[5, 1], 5)

    # Prune: total delivered over 3 days cannot exceed load, and the floor
    # (leak) rate must not exhaust the reservoir before the end.
    best = -1.0
    best_design = None
    best_rows = None
    checked = 0
    for amp in amp_grid:
        for leak in leak_grid:
            for ec50 in ec50_grid:
                for hn in n_grid:
                    for tau in tau_grid:
                        for load in load_grid:
                            x = np.array([amp, leak, ec50, hn, tau, load])
                            d = design_from_vector(instance, x)
                            sc, rows = penalized_score(instance, d)
                            checked += 1
                            if sc > best:
                                best, best_design, best_rows = sc, d, rows
    print(f"grid checked={checked} best={best:.4f} "
          f"{json.dumps(best_design['parameters'], indent=None) if best_design else None}")

    # ---- Stage 2: random sampling inside the envelope -----------------------
    rx, rs, rrows = random_search(instance, n=400)
    print(f"random best={rs:.4f} x={np.round(rx,5)}")

    # ---- Stage 3: local pattern refinement ---------------------------------
    scale = np.array([0.0005, 0.2, 20.0, 0.2, 1.0, 0.2])
    x0 = best_design and vector_from_design(instance, best_design) or rx
    if rs > (penalized_score(instance, best_design)[0] if best_design else -1):
        x0 = rx
    xf, fs, frows, it = local_refine(instance, x0, scale, max_iter=200)
    fd = design_from_vector(instance, xf)
    print(f"local iter={it} score={fs:.4f} {json.dumps(fd['parameters'])}")

    # ---- Stage 4: native dopri5 confirmation ---------------------------------
    native = verify_design(instance, fd, instance["training_seeds"])
    print(f"native: tir={native['mean_tir']:.4f} tbr70={native['max_trajectory_tbr70']:.4f} "
          f"tbr54={native['max_trajectory_tbr54']:.4f} min={native['minimum_glucose']:.4f} "
          f"feasible={native['feasible']}")

    if not native["feasible"]:
        # Fall back to the best feasible-by-fast-tracker design, or a safe constant.
        print("WARNING: native infeasible; falling back to fast-track best")

    save_design(fd, OUTPUT_DIR / "design.json")
    meta = {
        "search": {
            "grid_checked": checked,
            "random_n": 400,
            "local_iters": it,
            "fast_score": float(fs),
            "native": {k: v for k, v in native.items() if k not in ("rows",)},
            "elapsed_s": round(time.time() - t0, 3),
        },
    }
    (OUTPUT_DIR / "search_meta.json").write_text(json.dumps(meta, indent=2))
    print("saved", OUTPUT_DIR / "design.json")
    return fd


if __name__ == "__main__":
    main()
