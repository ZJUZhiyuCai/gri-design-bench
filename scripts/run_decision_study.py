"""Measure how additional evidence changes a simulated formulation-screening decision."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np

from gri_bench.api import Experiment, individual_design, validate_design
from gri_bench.native import native_trace
from gri_bench.timing_study import measure, replay, replay_rates


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results/v0.2/calibration/robust-reference.json"
VARIANTS = ("ordinary", "missed_lunch", "large_dinner")
FLOORS = (0, 5, 10)
PRIMARY_FLOOR = 5
METHODS = ("initial", "more_ordinary", "mixed_meals")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_plan():
    paths = [Path(__file__), REFERENCE, ROOT / "requirements-lock.txt"]
    paths.extend(ROOT / "src/gri_bench" / name for name in
                 ("api.py", "native.py", "physiology.py", "release.py", "timing_study.py"))
    cases = {}
    references = read(REFERENCE)["cases"]
    for index, row in enumerate(sorted(references, key=lambda r: r["case"])):
        case = row["case"]
        path = ROOT / "instances/dev" / f"{case}.json"
        paths.append(path)
        instance = read(path)
        validate_design(row["design"], instance)
        start = 990_070_000 + 100 * index
        cases[case] = {
            "patients": instance["patients"],
            "initial": list(range(start, start + 2)),
            "review": list(range(start + 10, start + 16)),
            "independent": list(range(start + 30, start + 38)),
        }
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "Does checking a mixed meal panel change which fixed responsive designs merit follow-up, and do those decisions agree with a separate mixed meal panel?",
        "scope": "Exploratory, six previously seen public development cohorts. Fixed historical designs. No model trials or clinical dose selection.",
        "cases": cases,
        "policies": {
            "initial": "Two ordinary seeds. Retain this initial decision without additional observations.",
            "more_ordinary": "Six fresh ordinary seeds. Recompute the decision on the review panel alone.",
            "mixed_meals": "First two of the six review seeds, crossed with all three variants. Recompute on the review panel alone.",
            "independent": "Eight separate seeds crossed with all three variants. Run after decisions are written.",
        },
        "unit_of_decision": "One fixed responsive formulation and its public three-patient cohort.",
        "control": "Open-loop rate uniform within each of days 2 and 3, with daily delivered amounts and day-one rate history matched to responsive.",
        "primary_floor_pp": PRIMARY_FLOOR,
        "sensitivity_floors_pp": list(FLOORS),
        "advance_rule": "Mean paired TIR gain meets the stated floor, mean paired TBR70 change is at most zero, and no responsive trajectory breaches TBR70 >4%, TBR54 >1%, or minimum <40 mg/dL. These are finite-panel research-screening criteria.",
        "files_sha256": {str(p.resolve().relative_to(ROOT)): digest(p) for p in paths},
    }


def evaluate_case(job):
    case, instance, design, panels = job
    results = {}
    # Share identical patient/seed/variant calculations within the review stage.
    # Each policy receives just its declared observations.
    cache = {}
    for panel, seeds, variants in panels:
        rows = []
        for patient, seed, variant, _, _, meals in Experiment(instance, seeds, variants).jobs:
            key = (patient, seed, variant)
            if key not in cache:
                trace, plasma = native_trace(
                    patient, meals, individual_design(design, instance["tdi"][patient]), instance["patient_seed"]
                )
                rate = trace[:, 2]
                flat = replay_rates(rate)["daily_flat"]
                replayed = replay(patient, meals, flat, instance["patient_seed"])
                dose = rate.reshape(3, 480).sum(axis=1) * 3
                control_dose = flat.reshape(3, 480).sum(axis=1) * 3
                dose_error = float(np.max(np.abs(dose - control_dose)))
                warmup = instance["warmup_minutes"]
                if dose_error > 1e-9 or not np.allclose(plasma[:warmup + 1], replayed[:warmup + 1], rtol=0, atol=1e-5):
                    raise ValueError(f"Dose or warmup mismatch for {case} {key}")
                cache[key] = {
                    "patient": patient, "seed": seed, "variant": variant,
                    "responsive": measure(plasma, warmup),
                    "daily_flat": measure(replayed, warmup),
                    "daily_dose_max_difference_u": dose_error,
                }
            rows.append(cache[key])
        results[panel] = rows
    print(case, {panel: len(rows) for panel, rows in results.items()}, flush=True)
    return case, results


def phase(plan, stage, workers):
    references = {row["case"]: row["design"] for row in read(REFERENCE)["cases"]}
    jobs = []
    for case, seeds in plan["cases"].items():
        instance = read(ROOT / "instances/dev" / f"{case}.json")
        if stage == "initial":
            panels = [("initial", seeds["initial"], ("ordinary",))]
        elif stage == "review":
            panels = [("more_ordinary", seeds["review"], ("ordinary",)),
                      ("mixed_meals", seeds["review"][:2], VARIANTS)]
        elif stage == "independent":
            panels = [("independent", seeds["independent"], VARIANTS)]
        else:
            raise ValueError(f"Unknown phase {stage}")
        jobs.append((case, instance, references[case], panels))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(evaluate_case, jobs))


def observations(rows):
    keys = {(row["patient"], row["seed"], row["variant"]) for row in rows}
    if not rows or len(keys) != len(rows):
        raise ValueError("Panel requires nonempty, unique scenarios")
    deltas = {
        metric: statistics.mean(row["responsive"][metric] - row["daily_flat"][metric] for row in rows)
        for metric in ("tir", "tbr70", "tbr54")
    }
    failures = []
    for row in rows:
        values = row["responsive"]
        if values["tbr70"] > 4 or values["tbr54"] > 1 or values["minimum"] < 40:
            failures.append({key: row[key] for key in ("patient", "seed", "variant", "responsive")})
    return {"scenarios": len(rows), "mean_responsive_minus_flat": deltas,
            "responsive_failures": failures}


def decision(summary, floor):
    change = summary["mean_responsive_minus_flat"]
    reasons = []
    if change["tir"] < floor:
        reasons.append("insufficient_tir_gain")
    if change["tbr70"] > 0:
        reasons.append("higher_mean_tbr70")
    if summary["responsive_failures"]:
        reasons.append("responsive_low_glucose_gate")
    return {"advance": not reasons, "reasons_to_defer": reasons}


def compare(decisions, independent):
    result = {}
    for floor in map(str, FLOORS):
        target = {case: record[floor]["advance"] for case, record in independent.items()}
        policies = {}
        for method in METHODS:
            predicted = {case: records[method][floor]["advance"] for case, records in decisions.items()}
            policies[method] = {
                "matches": sum(predicted[case] == target[case] for case in target),
                "unsupported_advances": [case for case in target if predicted[case] and not target[case]],
                "missed_advances": [case for case in target if not predicted[case] and target[case]],
                "advance": [case for case in target if predicted[case]],
                "changed_from_initial": [
                    case for case, records in decisions.items()
                    if predicted[case] != records["initial"][floor]["advance"]
                ],
            }
        result[floor] = {"independent_advance": [case for case in target if target[case]], "policies": policies}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    plan = make_plan()
    write(out / "plan.json", plan)

    initial = phase(plan, "initial", args.workers)
    write(out / "initial-evidence.json", initial)
    initial_summaries = {case: observations(record["initial"]) for case, record in initial.items()}
    initial_decisions = {case: {str(floor): decision(summary, floor) for floor in FLOORS}
                         for case, summary in initial_summaries.items()}
    write(out / "initial-decisions.json", initial_decisions)

    review = phase(plan, "review", args.workers)
    write(out / "review-evidence.json", review)
    summaries = {
        case: {"initial": initial_summaries[case], **{method: observations(rows) for method, rows in panels.items()}}
        for case, panels in review.items()
    }
    decisions = {
        case: {"initial": initial_decisions[case], **{
            method: {str(floor): decision(panels[method], floor) for floor in FLOORS}
            for method in METHODS[1:]
        }}
        for case, panels in summaries.items()
    }
    write(out / "decisions-before-independent.json", {
        "plan_sha256": digest(out / "plan.json"),
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "decisions": decisions,
    })

    final = phase(plan, "independent", args.workers)
    write(out / "independent-evidence.json", final)
    reference = {}
    for case, panels in final.items():
        summaries[case]["independent"] = observations(panels["independent"])
        reference[case] = {str(floor): decision(summaries[case]["independent"], floor) for floor in FLOORS}
    result = {
        "plan_sha256": digest(out / "plan.json"),
        "decisions_sha256": digest(out / "decisions-before-independent.json"),
        "primary_floor_pp": PRIMARY_FLOOR,
        "decisions_by_floor": compare(decisions, reference),
        "independent_decisions": reference,
        "case_observations": summaries,
        "interpretation": "Agreement on a finite held-out simulation panel, not biological or clinical correctness.",
    }
    write(out / "summary.json", result)
    print(json.dumps(result["decisions_by_floor"][str(PRIMARY_FLOOR)], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
