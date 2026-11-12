"""Assemble the public calibration evidence from completed CPU and scenario studies."""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
from statistics import mean

from gri_bench.evaluate import strict_json
from gri_bench.runner import ROOT, digest
from gri_bench.v02.protocol import atomic_json


def legacy_failures():
    plan = strict_json(ROOT / "experiments/expansion-2026-11-11/plan.json")
    groups = defaultdict(Counter)
    selected = plan["prior_comparable_round_tags"] + plan["tags"]
    paths = sorted(p for tag in selected for p in (ROOT / "results" / tag).glob("*/result.json"))
    if len(paths) != 324:
        raise ValueError("Expected 324 legacy attempts")
    for path in paths:
        data = strict_json(path)
        key = (data["split"], data["requested_model"])
        status = data["score"]
        g = groups[key]
        g["attempts"] += 1
        if status.get("format_valid"):
            g["valid_designs"] += 1
            g["safety_failed"] += not status.get("feasible")
        else:
            g["submission_or_infrastructure_failure"] += 1
            files = data.get("files") or {}
            if files.get("design.json") != "ok":
                g["design_missing_or_invalid"] += 1
            elif any(files.get(n) != "ok" for n in ("search.py", "rationale.md")):
                g["design_present_auxiliary_missing_or_invalid"] += 1
            else:
                g["complete_files_other_failure"] += 1
            g["reached_two_api_errors"] += len(data.get("api_errors") or []) >= 2
            g["charged_full_completion_budget"] += (data.get("charged_completion_tokens") or 0) >= 18_000
            g["runner_shell_exhausted"] += bool(data.get("budget_exhausted"))
            g["recorded_elapsed_at_least_360"] += (data.get("wall_seconds") or 0) >= 360
    return {
        "source_commit": "31b8731f927691ccb4ed46064d3974dd5bf55373",
        "attempts": len(paths), "round_tags": selected,
        "note": "The file categories are mutually exclusive. Budget and API flags can overlap. The legacy wall time includes cleanup and does not identify the exact cutoff cause.",
        "groups": [{"split": split, "model": model, **counts} for (split, model), counts in sorted(groups.items())],
    }


def safety(m):
    return m["tbr70"] <= 4 and m["tbr54"] <= 1 and m["minimum"] >= 40


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.calibration
    cpu = sorted((base / "cpu").glob("dev-*.json"))
    scenario_paths = sorted(p for phase in ("initial", "long") for p in
                            (base / f"scenarios-{phase}").glob("dev-*.json"))
    native_paths = sorted(p for phase in ("initial", "long") for p in
                          (base / f"native-{phase}").glob("dev-*.json"))
    if (len(cpu), len(scenario_paths), len(native_paths)) != (24, 12, 12):
        raise ValueError("Calibration requires six complete cases at every checkpoint")
    checks = [strict_json(p) for p in cpu]
    scenario = [r for p in scenario_paths for r in strict_json(p)]
    native = [r for p in native_paths for r in strict_json(p)]
    native_by_control = {(r["case"], r["control"]): r["score"] for r in native}
    rows = []
    for checkpoint in checks:
        case = checkpoint["case"]
        mode = checkpoint["mode"]
        budget = checkpoint["cpu_budget_seconds"]
        score = native_by_control[(case, f"{mode}_{budget}")]
        rows.append({
            "case": case, "mode": mode, "budget_cpu_seconds": budget,
            "completed_candidates": checkpoint["completed_candidates"],
            "training_mean_tir": checkpoint["training"]["mean_tir"],
            "native_eval_safe_tir": score["safe_tir"], "native_eval_feasible": score["feasible"],
        })
    native_checks = [check for r in scenario if r["format_valid"] for check in r["native_checks"]]
    summary = {
        "legacy_failures": legacy_failures(),
        "scenario_designs": len(scenario),
        "fast_scenarios_evaluated": sum(r.get("fast_panel", {}).get("trajectories", 0) for r in scenario),
        "native_check_trajectories": len(native_checks),
        "fast_native_safety_differences": sum(safety(c["fast"]) != safety(c["native"]) for c in native_checks),
        "max_absolute_metric_difference": {
            key: max(abs(c["fast"][key] - c["native"][key]) for c in native_checks)
            for key in ("tir", "tbr70", "tbr54", "minimum")
        },
        "native_control_trajectories": sum(r["score"].get("trajectories", 0) for r in native),
        "native_control_means": {
            k: {"mean_safe_tir": mean(r["score"]["safe_tir"] for r in native if r["control"] == k),
                "safety_passes": sum(r["score"]["feasible"] for r in native if r["control"] == k)}
            for k in sorted({r["control"] for r in native})
        },
        "private_source_sha256": {p.relative_to(base).as_posix(): digest(p)
                                  for p in cpu + scenario_paths + native_paths},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "cpu-curve.csv").open("w", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    atomic_json(args.output / "checkpoints.json", {"protocol": strict_json(base / "cpu/protocol.json"), "checkpoints": checks})
    atomic_json(args.output / "native-controls.json", native)
    atomic_json(args.output / "scenarios.json", [
        {k: v for k, v in r.items() if k != "native_checks"} for r in scenario
    ])
    atomic_json(args.output / "summary.json", summary)
    print({k: v for k, v in summary.items() if k not in ("legacy_failures", "private_source_sha256")})


if __name__ == "__main__":
    main()
