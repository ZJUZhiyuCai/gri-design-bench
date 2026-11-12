"""Check how evaluation panel size affects safety classifications on public cases."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from math import comb
from pathlib import Path

import numpy as np

from calibrate_v02 import CASES, write
from gri_bench.api import Experiment, glucose_metrics, individual_design, summarize, validate_design
from gri_bench.evaluate import strict_json
from gri_bench.native import native_trace
from gri_bench.runner import ROOT, load_case
from gri_bench.v02.search import training_seeds, zero_design

SAMPLE = {"mode": "responsive", "parameters": {
    "theta_a": 0.0002, "relative_leak": 1.5, "ec50_mg_dl": 200.0,
    "hill_n": 2.0, "tau_min": 10.0, "theta_L": 1.0,
}}
SIZES = (2, 4, 8, 16, 32, 64)
COHORT = strict_json(ROOT / "experiments/expansion-2026-11-11/plan.json")
TAGS = COHORT["prior_comparable_round_tags"] + COHORT["tags"]


def margin(metrics):
    return min(
        (4.0 - metrics["max_trajectory_tbr70"]) / 4.0,
        1.0 - metrics["max_trajectory_tbr54"],
        (metrics["minimum_glucose"] - 40.0) / 40.0,
    )


def inputs(case, instance, cpu, phase):
    checkpoints = (("constant", 30), ("responsive", 30)) if phase == "initial" else (
        ("responsive", 300), ("responsive", 3000))
    candidates = []
    for mode, seconds in checkpoints:
        path = cpu / f"{case}-{mode}-{seconds}.json"
        record = strict_json(path)
        candidates.append((f"{mode}_{seconds}", record["design"], path.name))

    if phase == "initial":
        candidates.extend([
            ("zero", zero_design(instance), "no release"),
            ("old_prompt_example", SAMPLE, "docs/AGENT_TASK.md"),
        ])
        path = ROOT / f"results/repeat-20261111-r1/{case}__codex__gpt-6.1-sol__seed20261111/design.json"
        candidates.append(("prior_gpt_round_1", strict_json(path), str(path.relative_to(ROOT))))
        options = []
        for tag in TAGS:
            for p in (ROOT / "results" / tag).glob(case + "__*/result.json"):
                score = strict_json(p)["score"]
                design_path = p.with_name("design.json")
                if score.get("format_valid") and "minimum_glucose" in score and design_path.is_file():
                    options.append((abs(margin(score)), design_path))
        _, path = min(options)
        candidates.append(("prior_near_safety_boundary", strict_json(path), str(path.relative_to(ROOT))))
    return candidates


def sensitivity(case, cpu, phase):
    instance, old_eval = load_case(case)
    seeds = np.random.default_rng(2026111300 + int(case[-2:])).choice(
        np.arange(700_000_000, 700_010_000), size=64, replace=False
    ).tolist()
    if set(seeds) & (set(training_seeds(instance)) | set(old_eval)):
        raise ValueError("Scenario seed collision")
    study = Experiment(instance, seeds=seeds)
    results = []
    for name, design, source in inputs(case, instance, cpu, phase):
        result = {"case": case, "control": name, "source": source, "design": design}
        results.append(result)
        try:
            validate_design(design, instance)
        except ValueError as error:
            result.update(format_valid=False, reason=str(error))
            continue
        fast = study.evaluate(design)
        rows = fast.pop("rows")
        groups = {seed: [r for r in rows if r["seed"] == seed] for seed in seeds}
        by_seed = [dict(seed=seed, **summarize(groups[seed])) for seed in seeds]
        passes = sum(r["feasible"] for r in by_seed)
        # Conditional on this finite reference panel, a k-seed sample falsely
        # accepts iff it contains only passing seeds and the full panel fails.
        discordance = {str(k): 0.0 if passes == len(seeds) or passes < k else
                       comb(passes, k) / comb(len(seeds), k) for k in SIZES}
        good = [r for r in by_seed if r["feasible"]]
        bad = [r for r in by_seed if not r["feasible"]]
        nearest = [min(group, key=lambda r: abs(margin(r)))["seed"] for group in (good, bad) if group]
        representative = sorted(by_seed, key=lambda r: r["mean_tir"])[len(seeds) // 2]["seed"]
        audit_seeds = sorted(set(nearest + [representative]))
        native_checks = []
        for job, row in zip(study.jobs, rows, strict=True):
            patient, seed, variant, _, _, meals = job
            if seed not in audit_seeds:
                continue
            trace, minute = native_trace(
                patient, meals, individual_design(design, instance["tdi"][patient]), instance["patient_seed"]
            )
            native_checks.append({
                "patient": patient, "seed": seed, "variant": variant,
                "fast": row["metrics"], "native": glucose_metrics(trace, instance["warmup_minutes"], minute),
            })
        results[-1].update(
            format_valid=True, fast_panel=fast, passing_seeds=passes, per_seed=by_seed,
            disagreement_probability=discordance, native_checks=native_checks,
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", type=Path, required=True)
    parser.add_argument("--phase", choices=("initial", "long"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(sensitivity, case, args.cpu, args.phase): case for case in CASES}
        for future in as_completed(futures):
            case = futures[future]
            results = future.result()
            write(args.output / f"{case}.json", results)
            print(case, [(r["control"], r.get("passing_seeds")) for r in results], flush=True)


if __name__ == "__main__":
    main()
