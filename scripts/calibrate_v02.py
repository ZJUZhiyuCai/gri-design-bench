"""Run the preregistered v0.2 baseline CPU curves on the public development set."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

from gri_bench.api import Experiment
from gri_bench.runner import ROOT, load_case, verify_runtime_lock
from gri_bench.v02.search import search, training_seeds, zero_design

CASES = tuple(f"dev-{i:02d}" for i in range(1, 7))
SEED = 20261113
MILESTONES = (30, 300, 3000)


def write(path, record):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def cpu_curve(case, output):
    instance, old_eval = load_case(case)
    seeds = training_seeds(instance)
    if set(seeds) & set(old_eval):
        raise ValueError(f"Training/evaluation seed overlap in {case}")
    # Warm the shared simulator before either search, as in the trial container.
    Experiment(instance).evaluate(zero_design(instance))
    for mode in ("constant", "responsive"):
        def checkpoint(record):
            record.update(case=case, mode=mode, search_seed=SEED, training_seeds=seeds)
            target = output / f"{case}-{mode}-{record['cpu_budget_seconds']}.json"
            write(target, record)
            print(f"{case} {mode} {record['cpu_budget_seconds']} CPU s: "
                  f"{record['completed_candidates']} candidates, training TIR "
                  f"{record['training']['mean_tir']:.2f}", flush=True)

        search(instance, mode, SEED, (30,) if mode == "constant" else MILESTONES, checkpoint)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    verify_runtime_lock()
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "protocol.json", {
        "cases": CASES, "workers": args.workers, "host": platform.platform(),
        "cpu": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        if sys.platform == "darwin" else platform.processor(),
        "python": platform.python_version(), "numpy": np.__version__,
        "responsive_cpu_milestones": MILESTONES, "constant_cpu_milestones": [30],
        "optimizer_sha256": hashlib.sha256((ROOT / "src/gri_bench/v02/search.py").read_bytes()).hexdigest(),
        "search_seed": SEED, "timing": "Single-process CPU time on the local host after simulator warmup.",
        "training_margins": {"tbr70": 3.0, "tbr54": 0.5, "minimum": 45.0},
    })
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(cpu_curve, case, args.output) for case in CASES]):
            future.result()


if __name__ == "__main__":
    main()
