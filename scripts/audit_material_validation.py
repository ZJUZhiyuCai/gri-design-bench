"""Recompute the material-state labels and assay decisions from saved observations."""

import argparse
import hashlib
from itertools import product
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_observations(out, plan, summary):
    protocol = plan["protocol"]
    rule = protocol["advance_rule"]
    floors = [int(key) for key in summary["results_by_floor"]]
    totals = {}
    truth = {}
    max_dose_error = 0.0
    max_warmup_error = 0.0
    seed_history = set()
    for stage in ("planning", "independent"):
        truth[stage] = {floor: {} for floor in floors}
        totals[stage] = 0
        expected_files = set()
        for case, spec in plan["cases"].items():
            seeds = spec["panels"][stage]
            require(len(set(seeds)) == len(seeds) and not seed_history.intersection(seeds),
                    f"Duplicate seeds in {stage}, {case}")
            seed_history.update(seeds)
            patient_ids = spec["instance"]["patients"]
            expected = set(product(patient_ids, seeds, protocol["variants"]))
            states = (*spec["states"], "nominal")
            for state in states:
                path = out / stage / f"{case}-{state}.json"
                expected_files.add(path)
                saved = load(path)
                require((saved["case"], saved["state"], saved["stage"]) == (case, state, stage), str(path))
                rows = saved["rows"]
                keys = [(row["patient"], row["seed"], row["variant"]) for row in rows]
                require(set(keys) == expected and len(keys) == len(expected), f"Wrong scenario coverage in {path}")
                totals[stage] += len(rows)
                delta = {key: math.fsum(row["responsive"][key] - row["daily_flat"][key] for row in rows) / len(rows)
                         for key in ("tir", "tbr70", "tbr54")}
                fail_count = 0
                for row in rows:
                    dose = row["daily_dose_u"]
                    flat_dose = row["control_daily_dose_u"]
                    require(len(dose) == len(flat_dose) == 3, f"Invalid daily amount length in {path}")
                    dose_error = max(abs(a - b) for a, b in zip(dose, flat_dose))
                    require(dose_error <= 1e-9 and dose_error == row["dose_match_error_u"], str(path))
                    max_dose_error = max(max_dose_error, dose_error)
                    warmup_error = row["warmup_match_error_mg_dl"]
                    require(0 <= warmup_error <= 1e-5, str(path))
                    max_warmup_error = max(max_warmup_error, warmup_error)
                    responsive = row["responsive"]
                    fail_count += (responsive["tbr70"] > rule["maximum_trajectory_tbr70_pct"]
                                   or responsive["tbr54"] > rule["maximum_trajectory_tbr54_pct"]
                                   or responsive["minimum"] < rule["minimum_trajectory_glucose_mg_dl"])
                saved = summary[stage][case][state]
                require(saved["n"] == len(rows) and len(saved["low_glucose_failures"]) == fail_count, str(path))
                for metric, value in delta.items():
                    require(math.isclose(saved["mean_responsive_minus_flat_pp"][metric], value, abs_tol=1e-12),
                            f"{path}: {metric}")
                if state != "nominal":
                    for floor in floors:
                        truth[stage][floor].setdefault(case, {})[state] = (
                            delta["tir"] >= floor and delta["tbr70"] <= rule["tbr70_mean_change_max_pp"] and fail_count == 0
                        )
        require(set((out / stage).glob("*.json")) == expected_files, f"Unexpected {stage} records")
    return truth, totals, max_dose_error, max_warmup_error


def check_decisions(plan, lock, summary, truth):
    for floor, planning in truth["planning"].items():
        stage = lock[str(floor)]
        labels = truth["independent"][floor]
        results = summary["results_by_floor"][str(floor)]
        choices = {}
        counts = {}
        for case, flags in planning.items():
            spec = plan["cases"][case]["states"]
            observed = {}
            counts[case] = {}
            for assay in ("leak", "delay"):
                observed[assay] = {}
                for state, value in spec.items():
                    group = [flags[name] for name, row in spec.items() if row[assay] == value[assay]]
                    observed[assay][state] = group.count(True) > group.count(False)
                counts[case][assay] = sum(observed[assay][state] != flags[state] for state in flags)
            choices[case] = observed
            require(stage["planning_by_case"][case]["labels"] == flags, f"Planning labels {case}")
            require(results["by_case"][case]["independent_labels"] == labels[case], f"Independent labels {case}")
        selected_fixed = min(("leak", "delay"), key=lambda a: sum(row[a] for row in counts.values()))
        require(stage["selected_fixed_assay"] == selected_fixed, f"Fixed assay at {floor}")
        confirmed = {"leak": [], "delay": []}
        aggregate = {name: {"false_advances": [], "misses": []} for name in results["policies"]}
        for case, flags in planning.items():
            selected_case = min(("leak", "delay"), key=counts[case].__getitem__)
            expected = {
                "no_assay": dict.fromkeys(flags, list(flags.values()).count(True) > len(flags) / 2),
                "fixed_leak": choices[case]["leak"], "fixed_delay": choices[case]["delay"],
                "selected_fixed": choices[case][selected_fixed], "case_specific": choices[case][selected_case],
                "both_assays": flags,
            }
            require(stage["decisions"][case] == expected, f"Locked decisions {case} at {floor}")
            case_errors = {}
            for policy, decisions in expected.items():
                false_advances = [name for name in flags if decisions[name] and not labels[case][name]]
                misses = [name for name in flags if labels[case][name] and not decisions[name]]
                case_errors[policy] = len(false_advances) + len(misses)
                require(results["by_case"][case]["policies"][policy] == {
                    "errors": case_errors[policy], "false_advances": false_advances, "misses": misses,
                }, f"Case errors {case}, {policy}")
                aggregate[policy]["false_advances"].extend([case, state] for state in false_advances)
                aggregate[policy]["misses"].extend([case, state] for state in misses)
            for assay, other in (("leak", "delay"), ("delay", "leak")):
                if counts[case][assay] < counts[case][other] and case_errors[f"fixed_{assay}"] < case_errors[f"fixed_{other}"]:
                    confirmed[assay].append(case)
        for row in aggregate.values():
            row["errors"] = len(row["false_advances"]) + len(row["misses"])
        require(aggregate == results["policies"], f"Aggregate errors at {floor}")
        require(confirmed == results["confirmed_preferences"], f"Preference directions at {floor}")
        saved_errors = min(aggregate["fixed_leak"]["errors"], aggregate["fixed_delay"]["errors"]) - aggregate["case_specific"]["errors"]
        rule = plan["protocol"]["agent_gate"]
        gate = (min(map(len, confirmed.values())) >= rule["minimum_confirmed_preferences_each_direction"]
                and saved_errors >= rule["minimum_errors_saved_vs_best_heldout_fixed"]
                and all(len(aggregate["case_specific"][field]) <= len(aggregate["selected_fixed"][field])
                        for field in ("false_advances", "misses")))
        require(results["agent_gate"] == gate and results["errors_saved_vs_best_heldout_fixed"] == saved_errors,
                f"Agent gate at {floor}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    out = args.output
    plan_path = out / "plan.json"
    lock_path = out / "decisions-before-independent.json"
    plan, record, summary = map(load, (plan_path, lock_path, out / "summary.json"))
    require(summary["plan_sha256"] == record["plan_sha256"] == digest(plan_path), "Plan hash mismatch")
    require(summary["decisions_sha256"] == digest(lock_path), "Decision hash mismatch")
    require(all(path.stat().st_mtime_ns > lock_path.stat().st_mtime_ns
                for path in (out / "independent").glob("*.json")), "Independent output predates locked decisions")
    for name, sha in plan["files_sha256"].items():
        require(digest(ROOT / name) == sha, f"Frozen input changed: {name}")
    truth, totals, dose, warmup = check_observations(out, plan, summary)
    check_decisions(plan, record["locked"], summary, truth)
    result = {"paired_scenarios_by_stage": totals, "paired_scenarios": sum(totals.values()),
              "max_recomputed_daily_dose_difference_u": dose, "max_warmup_difference_mg_dl": warmup,
              "decisions_and_gate_recomputed": True,
              "scope": "Recompute from saved endpoints and doses; not an independent physiology model."}
    with (out / "audit.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(result)


if __name__ == "__main__":
    main()
