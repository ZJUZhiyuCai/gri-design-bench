"""Refine long-search incumbents on additional training meals, then verify once."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
import time

import numpy as np

from gri_bench.api import PARAMETERS, Experiment
from gri_bench.evaluate import strict_json
from gri_bench.native import verify_design
from gri_bench.v02.matrix import DEV_CASES, load_v02_case
from gri_bench.v02.protocol import atomic_json
from gri_bench.v02.search import robust_loss, zero_design

AMPLITUDE_FACTORS = (1.05, 1.02, 1.0, 0.99, 0.98, 0.97, 0.96, 0.94, 0.92, 0.90, 0.85, 0.80)


def refine(task):
    case, cpu = task
    instance, heldout = load_v02_case(case, "development")
    rng = np.random.default_rng(2026111310 + int(case[-2:]))
    seeds = rng.choice(np.arange(735_000_000, 735_010_000), size=16, replace=False).tolist()
    if set(seeds) & (set(heldout) | set(instance["training_seeds"])):
        raise ValueError("Training/evaluation seed overlap")
    experiment = Experiment(instance, seeds=seeds)
    # The verifier panel is opened for scoring after selection has finished.
    start = time.process_time()
    best = None
    tested = set()
    low, high = np.array([instance["bounds"][key] for key in PARAMETERS]).T
    log_lo = np.log(np.maximum(low, 1e-7))
    log_width = np.log(high) - log_lo

    def candidate(design):
        nonlocal best
        values = tuple(design["parameters"][k] for k in PARAMETERS)
        if values in tested:
            return
        tested.add(values)
        metrics = experiment.evaluate(design)
        loss = robust_loss(metrics)
        if best is None or loss < best["loss"]:
            best = {"design": design, "loss": loss,
                    "training": {k: v for k, v in metrics.items() if k != "rows"}}

    candidate(zero_design(instance, "responsive"))
    for seconds in (30, 300, 3000):
        checkpoint = strict_json(cpu / f"{case}-responsive-{seconds}.json")["design"]
        for factor in AMPLITUDE_FACTORS:
            values = dict(checkpoint["parameters"])
            values["theta_a"] = float(np.clip(values["theta_a"] * factor, low[0], high[0]))
            candidate({"mode": "responsive", "parameters": values})

    for step in (0.07, 0.035):
        for dimension in range(len(PARAMETERS)):
            incumbent = np.array([best["design"]["parameters"][key] for key in PARAMETERS])
            coordinates = (np.log(np.maximum(incumbent, 1e-7)) - log_lo) / log_width
            for sign in (-1, 1):
                varied = coordinates.copy()
                varied[dimension] += sign * step
                values = np.clip(np.exp(log_lo + np.clip(varied, 0.0, 1.0) * log_width), low, high)
                candidate({"mode": "responsive", "parameters": dict(zip(PARAMETERS, map(float, values)))})

    elapsed = time.process_time() - start
    design = best["design"]
    score = verify_design(instance, design, heldout)
    return {
        "case": case, "training_seeds": seeds, "refinement_cpu_seconds": elapsed,
        "candidates": len(tested), **best, "score": {k: v for k, v in score.items() if k != "rows"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    with ProcessPoolExecutor(max_workers=3, mp_context=get_context("spawn")) as pool:
        records = list(pool.map(refine, ((case, args.cpu) for case in DEV_CASES)))
    atomic_json(args.output, {
        "scope": "Post-search refinement on 16 independent training seeds. Native evaluation follows selection.",
        "cases": records,
    })
    print([(r["case"], round(r["score"]["safe_tir"], 2)) for r in records], flush=True)


if __name__ == "__main__":
    main()
