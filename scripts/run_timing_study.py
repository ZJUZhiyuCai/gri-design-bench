"""Run the fixed public-development panel for the dose-matched timing study."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

from gri_bench.api import Experiment, validate_design
from gri_bench.timing_study import ARMS, METRICS, evaluate_scenario


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results/v0.2/calibration/robust-reference.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def prepare_panel():
    references = json.loads(REFERENCE.read_text())["cases"]
    cases = []
    for index, reference in enumerate(sorted(references, key=lambda row: row["case"])):
        case_id = reference["case"]
        instance = json.loads((ROOT / "instances/dev" / f"{case_id}.json").read_text())
        design = validate_design(reference["design"], instance)
        seeds = [980_031_001 + 100 * index + offset for offset in range(4)]
        cases.append({"case": case_id, "instance": instance, "design": design, "seeds": seeds})
    return cases


def run_case(case):
    instance = case["instance"]
    experiment = Experiment(instance, seeds=case["seeds"])
    rows, identity_errors = [], []
    for patient, seed, variant, _, _, meals in experiment.jobs:
        arms, error = evaluate_scenario(instance, case["design"], patient, seed, variant, meals)
        rows.extend({"case": case["case"], **{k: v for k, v in row.items() if k != "rate_u_min"}} for row in arms)
        identity_errors.append(error)
    print(case["case"], len(identity_errors), "paired scenarios", flush=True)
    return rows, identity_errors


def describe(rows):
    scenarios = {}
    for row in rows:
        key = tuple(row[k] for k in ("case", "patient", "seed", "variant"))
        arms = scenarios.setdefault(key, {})
        if row["arm"] in arms:
            raise ValueError(f"Duplicate timing arm for {key}")
        arms[row["arm"]] = row

    def summary(group):
        stats = {}
        for arm in ARMS:
            runs = [scenario[arm] for scenario in group]
            stats[arm] = {"scenarios": len(runs), **{
                f"mean_{metric}": statistics.mean(row[metric] for row in runs) for metric in METRICS
            }, "any_low_glucose_gate_violations": sum(
                row["tbr70"] > 4 or row["tbr54"] > 1 or row["minimum"] < 40 for row in runs
            )}
        contrasts = {}
        for control in ARMS[1:]:
            effects = {metric: [s["responsive"][metric] - s[control][metric] for s in group] for metric in METRICS}
            contrasts[control] = {
                "mean_responsive_minus_control": {metric: statistics.mean(values) for metric, values in effects.items()},
                "tir_higher": sum(value > 1e-10 for value in effects["tir"]),
                "tbr70_higher": sum(value > 1e-10 for value in effects["tbr70"]),
                "tbr54_higher": sum(value > 1e-10 for value in effects["tbr54"]),
            }
        return {"arms": stats, "contrasts": contrasts}

    return {
        "overall": summary(list(scenarios.values())),
        "by_case": {case: summary([s for key, s in scenarios.items() if key[0] == case])
                    for case in sorted({key[0] for key in scenarios})},
        "by_variant": {variant: summary([s for key, s in scenarios.items() if key[3] == variant])
                       for variant in sorted({key[3] for key in scenarios})},
        "max_daily_dose_difference_u": max(
            abs(a - b) for s in scenarios.values() for arm in ARMS[1:]
            for a, b in zip(s["responsive"]["daily_dose_u"], s[arm]["daily_dose_u"], strict=True)
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    cases = prepare_panel()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [REFERENCE, Path(__file__), *(ROOT / "src/gri_bench" / name for name in
              ("api.py", "native.py", "physiology.py", "release.py", "timing_study.py"))]
    plan = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "For fixed designs in this simulator, what changes when within-day release timing is changed at the same daily delivered dose?",
        "scope": "Exploratory public development cohorts, fixed historical responsive designs, new meal seeds. No model trials.",
        "comparison": "Same patient, meals and first-day release. Days 2 and 3 either retain feedback, flatten each day's rate or rotate it by 12 hours. Each daily dose is preserved.",
        "endpoints": "Days 2–3 TIR, TBR70 and TBR54 on three-minute plasma endpoints; 72-hour minimum on minute endpoints including initial value.",
        "cases": cases,
        "files_sha256": {str(path.resolve().relative_to(ROOT)): sha(path) for path in paths},
    }
    write(args.output / "plan.json", plan)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        outcomes = list(pool.map(run_case, cases))
    rows = [row for records, _ in outcomes for row in records]
    summary = describe(rows)
    summary.update({
        "scope": plan["scope"], "plan_sha256": sha(args.output / "plan.json"),
        "paired_scenarios": len(rows) // len(ARMS), "physiology_outcomes": len(rows),
        "identity_replays": sum(len(errors) for _, errors in outcomes),
        "max_identity_replay_error_mg_dl": max(error for _, errors in outcomes for error in errors),
    })
    write(args.output / "outcomes.json", rows)
    write(args.output / "summary.json", summary)
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()
