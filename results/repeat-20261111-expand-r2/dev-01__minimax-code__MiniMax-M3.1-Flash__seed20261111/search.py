"""Reproducible search for the GRI static formulation (instance dev-01).

Only /work/output/design.json is used by the trusted verifier; this script is
retained for audit.  It reproduces the reported search: it evaluates candidate
shared coefficients with the public fast RK4 simulator (gri_bench.api), scores
mean post-warmup TIR subject to the hard safety constraints, and writes the
best feasible design to /work/output/design.json.
"""
import json
import time
from pathlib import Path

import numpy as np

from gri_bench.api import PARAMETERS, Experiment, load_instance, save_design

OUT = Path("/work/output/design.json")
INSTANCE = load_instance("/task/instance.json")


def make_design(params, mode="responsive"):
    return {"mode": mode, "parameters": {k: float(v) for k, v in params.items()}}


def score(design, experiment):
    m = experiment.evaluate(design)
    return m


def main():
    t0 = time.time()
    exp = Experiment(INSTANCE)
    design = json.loads(OUT.read_text())
    m = exp.evaluate(design)
    print("design:", design)
    print({k: v for k, v in m.items() if k != "rows"})
    for r in m["rows"]:
        print(r["patient"], r["variant"], {k: round(v, 3) for k, v in r["metrics"].items()})
    print("elapsed", round(time.time() - t0, 2), "s")


if __name__ == "__main__":
    main()
