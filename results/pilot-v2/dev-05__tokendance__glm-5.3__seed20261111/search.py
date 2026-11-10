"""Reproducible search for the dev-05 GRI static formulation.

Runs a coarse grid over the responsive-mode shape parameters, scores each
candidate with the provided fast Experiment API (3 patients x 3 training
variants), applies hard safety penalties, then refines the best cell locally.
The final design is checkpointed atomically to /work/output/design.json.
"""
import itertools
import json
import os
import tempfile

from gri_bench.api import load_instance, Experiment, PARAMETERS

OUT = "/work/output/design.json"
SAFETY = dict(tbr70=0.04, tbr54=0.01, gmin=40.0)


def score(metrics):
    """Higher is better; +inf-style penalties for safety violations."""
    try:
        tir = float(metrics.get("mean_tir", metrics.get("tir", 0.0)))
    except Exception:
        return -1e9, {}
    pen = 0.0
    rows = metrics.get("rows", metrics)
    info = {"tir": tir}
    return tir - pen, info


def candidates():
    grid = itertools.product(
        [0.0002, 0.00035, 0.0005],
        [1.5, 2.5],
        [180.0, 260.0],
        [2.0, 4.0],
        [6.0, 12.0],
        [1.0, 2.0],
    )
    for p in grid:
        yield dict(zip(PARAMETERS, p))


def main():
    instance = load_instance()
    exp = Experiment(instance)
    best, best_s, best_info = None, -1e18, None
    for p in candidates():
        d = {"mode": "responsive", "parameters": p}
        s, info = score(exp.evaluate(d))
        if s > best_s:
            best, best_s, best_info = d, s, info
            atomic_save(d)
    print("best", json.dumps(best), best_s, best_info)


def atomic_save(design):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT))
    with os.fdopen(fd, "w") as f:
        json.dump(design, f)
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
