"""Simulate material uncertainty, lock assay decisions, then verify on fresh meals."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import statistics
import time

import numpy as np

from gri_bench.api import Experiment, individual_design, validate_design
from gri_bench.native import native_trace
from gri_bench.timing_study import measure, replay, replay_rates


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments/material-validation-2026-11-13/protocol.json"
ASSAYS = ("leak", "delay")
POLICIES = ("no_assay", "fixed_leak", "fixed_delay", "selected_fixed", "case_specific", "both_assays")


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs():
    protocol = read(PROTOCOL)
    source = ROOT / protocol["candidate_source"]
    reference = {row["case"]: row["design"] for row in read(source)["cases"]}
    paths = [Path(__file__).resolve(), PROTOCOL, source, ROOT / "requirements-lock.txt"]
    paths.extend(ROOT / "src/gri_bench" / f"{name}.py" for name in
                 ("api", "native", "physiology", "release", "timing_study"))
    cases = {}
    registered_seeds = set()
    for index, case in enumerate(protocol["cases"]):
        instance_path = ROOT / "instances/dev" / f"{case}.json"
        paths.append(instance_path)
        instance = read(instance_path)
        nominal = validate_design(reference[case], instance)
        states = {}
        for (leak, leak_value), (delay, tau) in product(
                protocol["leak_levels"].items(), protocol["tau_levels_minutes"].items()):
            name = f"{leak}_leak_{delay}_response"
            parameters = {**nominal["parameters"], "relative_leak": leak_value, "tau_min": tau}
            design = validate_design({"mode": "responsive", "parameters": parameters}, instance)
            states[name] = {"leak": leak, "delay": delay, "design": design}
        spec = protocol["seeds"]
        base = spec["base"] + index * spec["case_stride"]
        panels = {stage: [base + offset for offset in spec[f"{stage}_offsets"]]
                  for stage in ("planning", "independent")}
        for seeds in panels.values():
            if len(set(seeds)) != len(seeds) or registered_seeds.intersection(seeds):
                raise ValueError("Meal seeds must be unique across cases and panels")
            registered_seeds.update(seeds)
        cases[case] = {"instance": instance, "nominal": nominal, "states": states, "panels": panels}
    return {"frozen_utc": now(), "protocol": protocol, "cases": cases,
            "files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}}


def evaluate_state(case, state, instance, design, seeds, variants):
    started = time.process_time()
    rows = []
    warmup = instance["warmup_minutes"]
    for patient, seed, variant, _, _, meals in Experiment(instance, seeds, variants).jobs:
        parameters = individual_design(design, instance["tdi"][patient])
        trace, plasma = native_trace(patient, meals, parameters, instance["patient_seed"])
        rates = trace[:, 2]
        flat = replay_rates(rates)["daily_flat"]
        flat_plasma = replay(patient, meals, flat, instance["patient_seed"])
        amount = 3 * rates.reshape(3, -1).sum(axis=1)
        control_amount = 3 * flat.reshape(3, -1).sum(axis=1)
        dose_difference = float(np.max(np.abs(amount - control_amount)))
        warmup_difference = float(np.max(np.abs(plasma[:warmup + 1] - flat_plasma[:warmup + 1])))
        if dose_difference > 1e-9 or warmup_difference > 1e-5:
            raise ValueError(f"Dose or warmup mismatch for {case}, {state}, {patient}, {seed}, {variant}")
        rows.append({
            "patient": patient, "seed": seed, "variant": variant,
            "responsive": measure(plasma, warmup), "daily_flat": measure(flat_plasma, warmup),
            "daily_dose_u": amount.tolist(), "control_daily_dose_u": control_amount.tolist(),
            "dose_match_error_u": dose_difference, "warmup_match_error_mg_dl": warmup_difference,
            "reservoir_remaining_u": float(trace[-1, 3]),
        })
    return rows, time.process_time() - started


def compute_panel(plan, stage, folder, workers):
    folder.mkdir(exist_ok=True)
    jobs = {}
    results = {case: {} for case in plan["cases"]}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for case, record in plan["cases"].items():
            designs = {key: state["design"] for key, state in record["states"].items()}
            designs["nominal"] = record["nominal"]
            for state, design in designs.items():
                path = folder / f"{case}-{state}.json"
                if path.exists():
                    saved = read(path)
                    if saved["case"] != case or saved["state"] != state or saved["stage"] != stage:
                        raise ValueError(f"Unexpected record in {path}")
                    results[case][state] = saved["rows"]
                    continue
                job = pool.submit(evaluate_state, case, state, record["instance"], design,
                                  record["panels"][stage], plan["protocol"]["variants"])
                jobs[job] = case, state, path
        for completed in as_completed(jobs):
            case, state, path = jobs[completed]
            rows, cpu = completed.result()
            write_new(path, {"case": case, "state": state, "stage": stage, "cpu_seconds": cpu, "rows": rows})
            results[case][state] = rows
            print(stage, case, state, len(rows), "paired scenarios", flush=True)
    for case, records in results.items():
        inputs = plan["cases"][case]
        expected = set(product(inputs["instance"]["patients"], inputs["panels"][stage], plan["protocol"]["variants"]))
        for state, rows in records.items():
            keys = {(r["patient"], r["seed"], r["variant"]) for r in rows}
            if keys != expected or len(rows) != len(expected):
                raise ValueError(f"Incomplete or duplicate outcomes in {stage}, {case}, {state}")
    return results


def metrics(rows, rule):
    delta = {key: statistics.mean(r["responsive"][key] - r["daily_flat"][key] for r in rows)
             for key in ("tir", "tbr70", "tbr54")}
    failures = []
    for row in rows:
        values = row["responsive"]
        if (values["tbr70"] > rule["maximum_trajectory_tbr70_pct"]
                or values["tbr54"] > rule["maximum_trajectory_tbr54_pct"]
                or values["minimum"] < rule["minimum_trajectory_glucose_mg_dl"]):
            failures.append({k: row[k] for k in ("patient", "seed", "variant", "responsive")})
    return {
        "n": len(rows), "mean_responsive_minus_flat_pp": delta,
        "low_glucose_failures": failures,
        "mean_total_delivered_u": statistics.mean(sum(r["daily_dose_u"]) for r in rows),
        "min_glucose_mg_dl": min(r["responsive"]["minimum"] for r in rows),
        "reservoir_exhausted": sum(r["reservoir_remaining_u"] <= 1e-9 for r in rows),
        "max_dose_match_error_u": max(r["dose_match_error_u"] for r in rows),
        "max_warmup_match_error_mg_dl": max(r["warmup_match_error_mg_dl"] for r in rows),
    }


def advance(summary, floor, rule):
    delta = summary["mean_responsive_minus_flat_pp"]
    return (delta["tir"] >= floor and delta["tbr70"] <= rule["tbr70_mean_change_max_pp"]
            and not summary["low_glucose_failures"])


def majority(values):
    return 2 * sum(values) > len(values)


def observe_policy(states, flags, assay):
    if assay == "none":
        return {name: majority(flags.values()) for name in states}
    if assay == "both":
        return dict(flags)
    decisions = {}
    for name, state in states.items():
        compatible = [flags[other] for other, spec in states.items() if spec[assay] == state[assay]]
        decisions[name] = majority(compatible)
    return decisions


def errors(picks, labels):
    false_advances = [state for state in labels if picks[state] and not labels[state]]
    misses = [state for state in labels if not picks[state] and labels[state]]
    return {"errors": len(false_advances) + len(misses), "false_advances": false_advances, "misses": misses}


def lock_policies(plan, planning, floor):
    rule = plan["protocol"]["advance_rule"]
    table = {}
    fixed_cost = dict.fromkeys(ASSAYS, 0)
    for case, spec in plan["cases"].items():
        flags = {state: advance(planning[case][state], floor, rule) for state in spec["states"]}
        options = {assay: observe_policy(spec["states"], flags, assay) for assay in ("none", *ASSAYS, "both")}
        losses = {assay: errors(options[assay], flags)["errors"] for assay in ASSAYS}
        for assay in ASSAYS:
            fixed_cost[assay] += losses[assay]
        best = min(ASSAYS, key=losses.__getitem__)
        table[case] = {"labels": flags, "options": options, "planning_errors": losses, "selected_assay": best}
    fixed_assay = min(ASSAYS, key=fixed_cost.__getitem__)
    decisions = {}
    for case, record in table.items():
        options = record["options"]
        decisions[case] = {
            "no_assay": options["none"], "fixed_leak": options["leak"], "fixed_delay": options["delay"],
            "selected_fixed": options[fixed_assay], "case_specific": options[record["selected_assay"]],
            "both_assays": options["both"],
        }
    return {"selected_fixed_assay": fixed_assay, "planning_errors_fixed": fixed_cost,
            "planning_by_case": table, "decisions": decisions}


def analyze(plan, locked, independent, floor):
    rule = plan["protocol"]["advance_rule"]
    by_case = {}
    for case, spec in plan["cases"].items():
        labels = {state: advance(independent[case][state], floor, rule) for state in spec["states"]}
        by_case[case] = {"independent_labels": labels, "policies": {
            name: errors(picks, labels) for name, picks in locked["decisions"][case].items()
        }}
    policies = {}
    for name in POLICIES:
        outcomes = {case: row["policies"][name] for case, row in by_case.items()}
        false_advances = [[case, state] for case, row in outcomes.items() for state in row["false_advances"]]
        misses = [[case, state] for case, row in outcomes.items() for state in row["misses"]]
        policies[name] = {"false_advances": false_advances, "misses": misses,
                          "errors": len(false_advances) + len(misses)}
    confirmed = {assay: [] for assay in ASSAYS}
    for case, row in by_case.items():
        planned = locked["planning_by_case"][case]["planning_errors"]
        for assay, other in (ASSAYS, ASSAYS[::-1]):
            if (planned[assay] < planned[other]
                    and row["policies"][f"fixed_{assay}"]["errors"] < row["policies"][f"fixed_{other}"]["errors"]):
                confirmed[assay].append(case)
    improvement = min(policies[f"fixed_{a}"]["errors"] for a in ASSAYS) - policies["case_specific"]["errors"]
    gate = plan["protocol"]["agent_gate"]
    adaptive = policies["case_specific"]
    fixed = policies["selected_fixed"]
    meets_gate = (all(len(cases) >= gate["minimum_confirmed_preferences_each_direction"] for cases in confirmed.values())
                  and improvement >= gate["minimum_errors_saved_vs_best_heldout_fixed"]
                  and len(adaptive["false_advances"]) <= len(fixed["false_advances"])
                  and len(adaptive["misses"]) <= len(fixed["misses"]))
    return {"by_case": by_case, "policies": policies, "confirmed_preferences": confirmed,
            "errors_saved_vs_best_heldout_fixed": improvement, "agent_gate": meets_gate}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "plan.json"
    if plan_path.exists():
        plan = read(plan_path)
        for file, expected in plan["files_sha256"].items():
            if sha(ROOT / file) != expected:
                raise ValueError(f"Frozen file changed: {file}")
    else:
        if any(out.iterdir()):
            raise ValueError("A new run needs an empty output directory")
        plan = load_inputs()
        write_new(plan_path, plan)
    if (out / "summary.json").exists():
        raise FileExistsError("Completed run already has a summary")

    rule = plan["protocol"]["advance_rule"]
    floor = rule["tir_gain_floor_pp"]
    floors = (floor, *plan["protocol"]["tir_floor_sensitivity_pp"])
    planning = {case: {state: metrics(rows, rule) for state, rows in records.items()}
                for case, records in compute_panel(plan, "planning", out / "planning", args.workers).items()}
    locked_path = out / "decisions-before-independent.json"
    locked = {str(f): lock_policies(plan, planning, f) for f in floors}
    if locked_path.exists():
        previous = read(locked_path)
        if previous["plan_sha256"] != sha(plan_path) or previous["locked"] != locked:
            raise ValueError("Previously locked decisions differ from planning replay")
    else:
        write_new(locked_path, {"written_utc": now(), "plan_sha256": sha(plan_path), "locked": locked})
    print("Decisions locked", sha(locked_path), flush=True)

    independent = {case: {state: metrics(rows, rule) for state, rows in records.items()}
                   for case, records in compute_panel(plan, "independent", out / "independent", args.workers).items()}
    results = {str(f): analyze(plan, locked[str(f)], independent, f) for f in floors}
    summary = {
        "plan_sha256": sha(plan_path), "decisions_sha256": sha(locked_path), "primary_floor_pp": floor,
        "planning": planning, "independent": independent, "results_by_floor": results,
    }
    write_new(out / "summary.json", summary)
    print(json.dumps({k: v for k, v in results[str(floor)].items() if k != "by_case"}), flush=True)


if __name__ == "__main__":
    main()
