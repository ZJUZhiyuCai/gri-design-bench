"""Audit and compare the nine v0.2 model routes on their shared case panels."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations, product
from math import isclose
from multiprocessing import get_context
from pathlib import Path
from statistics import mean, stdev
import sys

import numpy as np
from scipy.stats import kendalltau, rankdata

from gri_bench.evaluate import strict_json
from gri_bench.runner import ROOT, digest
from gri_bench.v02.matrix import CONTRACT, jobs, load_v02_case, verify_lock
from gri_bench.v02.protocol import atomic_json, excluded_model

# Keep script imports available when the maintainer runs Python in isolated mode.
if sys.flags.isolated:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_v02 import audit_attempt, csv_export, group_metrics, reverify, summarize_matrix
from run_v02_expansion import EXPERIMENT, PLAN, RUNS, SPLITS, expansion_jobs, verify_expansion

RESULTS = ROOT / "results/v0.2/expansion-2026-11-13"
# 144 equally weighted trajectories, each with 960 evaluated time points.
TIR_TICKS_PER_PERCENT = 144 * 960 / 100
ROUNDS = (1, 2, 3)


def ticks(attempt):
    score = attempt["score"]["safe_tir"] * TIR_TICKS_PER_PERCENT
    if not isclose(score, round(score), rel_tol=0, abs_tol=1e-8):
        raise ValueError("TIR falls outside the frozen evaluation grid: " + attempt["trial_id"])
    return round(score)


def ranks(totals):
    values = rankdata([-value for value in totals.values()], method="average")
    return dict(zip(totals, map(float, values), strict=True))


def ranked_groups(ranking):
    return [
        sorted(model for model, position in ranking.items() if position == rank)
        for rank in sorted(set(ranking.values()))
    ]


def check_export(data, plan_path, split, scheduled):
    if data["split"] != split or data["plan_sha256"] != digest(plan_path):
        raise ValueError("Export does not match its plan: " + split)
    records = data["attempts"]
    actual = {
        (row["trial_id"], row["case"], row["method"], row["requested_model"]) for row in records
    }
    if len(records) != len(actual) or actual != set(scheduled):
        raise ValueError("Missing, duplicated or unexpected attempts: " + split)
    for row in records:
        if split == "sealed" and ("design" in row or "rows" in row["score"]):
            raise ValueError("Sealed design or trajectory in public export")
        if row["method"] == "agent" and row["repetition"] != int(row["trial_id"].rsplit("__r", 1)[-1]):
            raise ValueError("Export repetition does not match the trial ID")
        if not row["score"]["feasible"] and row["score"]["safe_tir"] != 0:
            raise ValueError("A failed attempt received a nonzero score")
        ticks(row)
    return records


def collect(plan):
    evidence, to_verify = {}, {}
    manifest = strict_json(RUNS / "manifest.json")["provenance"]
    for split in SPLITS:
        registered = expansion_jobs(plan, split)
        folder = RUNS / split
        if {p.name for p in folder.iterdir()} != {name for name, *_ in registered}:
            raise ValueError("Run directory differs from the expansion plan: " + split)
        cases = {case: load_v02_case(case, split) for case in plan["splits"][split]["cases"]}
        rows = []
        for name, case, method, route in registered:
            path = folder / name
            instance, seeds = cases[case]
            meta = strict_json(path / "metadata.json")
            for key, value in manifest.items():
                if key != "source_commit" and meta["provenance"][key] != value:
                    raise ValueError("Trial provenance differs from the expansion manifest: " + name)
            if excluded_model(route):
                raise ValueError("Unregistered model family: " + name)
            row = audit_attempt(path, case, method, route, {"split": split}, instance, seeds, plan_path=PLAN)
            row["source_commit"] = meta["provenance"]["source_commit"]
            rows.append(row)
            if row["score"].get("trajectories"):
                to_verify.setdefault((split, route), (path, case, split))
                if row["score"]["status"] == "safety_failure":
                    to_verify.setdefault((split, "safety failure"), (path, case, split))
        evidence[split] = {"split": split, "plan_sha256": digest(PLAN), "attempts": rows}
        check_export(evidence[split], PLAN, split, registered)
    with ProcessPoolExecutor(max_workers=3, mp_context=get_context("spawn")) as pool:
        checks = list(pool.map(reverify, dict.fromkeys(to_verify.values())))
    return evidence, {
        "source_commits": sorted({row["source_commit"] for data in evidence.values() for row in data["attempts"]}),
        "plan_sha256": digest(PLAN),
        "runtime_sha256": digest(CONTRACT / "runtime-lock.json"),
        "image_id": manifest["image_id"],
        "audited_attempts": sum(len(data["attempts"]) for data in evidence.values()),
        "audited_attempts_by_split": {split: len(data["attempts"]) for split, data in evidence.items()},
        "started_utc": min(row["started_utc"] for data in evidence.values() for row in data["attempts"]),
        "finished_utc": max(row["finished_utc"] for data in evidence.values() for row in data["attempts"]),
        "audited_api_reservations": sum(row["model_calls"] for data in evidence.values() for row in data["attempts"]),
        "native_trajectories": sum(row["score"].get("trajectories", 0)
                                   for data in evidence.values() for row in data["attempts"]),
        "reverified_designs": checks,
    }


def round_analysis(records, members, model_labels, split, cases):
    """Rank the fixed-case round means and compare rank vectors with ties."""
    lookup = {(r["requested_model"], r["case"], r["repetition"]): r for r in records if r["method"] == "agent"}
    round_ranks, round_rows, round_orders = {}, [], []
    for repeat in ROUNDS:
        per_model = {model: [lookup[model, case, repeat] for case in cases] for model in members}
        totals = {model: sum(map(ticks, rows)) for model, rows in per_model.items()}
        ranking = round_ranks[repeat] = ranks(totals)
        round_orders.append(ranked_groups(ranking))
        for model in sorted(members, key=lambda model: (ranking[model], model_labels[model])):
            rows = per_model[model]
            round_rows.append({
                "split": split, "round": repeat, "model": model_labels[model], "route": model,
                "rank": ranking[model], **group_metrics(rows),
            })
    tau = []
    for a, b in combinations(ROUNDS, 2):
        value = kendalltau([round_ranks[a][m] for m in members], [round_ranks[b][m] for m in members]).statistic
        tau.append({"round_a": a, "round_b": b, "tau_b": None if np.isnan(value) else float(value)})
    pair_counts = Counter()
    for a, b in combinations(members, 2):
        order = {int(np.sign(rank[a] - rank[b])) for rank in round_ranks.values()}
        if len(order) == 1:
            category = "consistent_tie" if order == {0} else "consistent_order"
        else:
            category = "reversed" if {-1, 1} <= order else "tie_in_some_rounds"
        pair_counts[category] += 1
    return round_rows, round_ranks, {
        "rank_groups_by_round": round_orders, "kendall_tau_b": tau,
        "pair_counts": {k: pair_counts[k] for k in ("consistent_order", "consistent_tie", "reversed", "tie_in_some_rounds")},
    }


def analyze_split(pilot, extra, records):
    split, cases = pilot["split"], pilot["cases"]
    models = pilot["models"] + extra["models"]
    model_labels = {m["route"]: m["display"] for m in models}
    cohorts = {"pilot": [m["route"] for m in pilot["models"]],
               "expansion": [m["route"] for m in extra["models"]]}
    combined, case_rows, pairs = summarize_matrix({**pilot, "models": models}, records)
    per_model = defaultdict(list)
    lookup = {}
    for row in records:
        if row["method"] == "agent":
            per_model[row["requested_model"]].append(row)
            lookup[row["requested_model"], row["case"], row["repetition"]] = row
    if set(lookup) != set(product(model_labels, cases, ROUNDS)):
        raise ValueError("Combined model/case/repetition grid is incomplete")
    overall = ranks({model: sum(map(ticks, rows)) for model, rows in per_model.items()})
    rounds = []
    stability = {}
    for name, members in (("combined", list(model_labels)), *cohorts.items()):
        rows, ranking, result = round_analysis(records, members, model_labels, split, cases)
        rounds.extend({"cohort": name, **row} for row in rows)
        stability[name] = result
        if name == "combined":
            combined_round_ranks = ranking

    leave_one_out = {}
    for omitted in cases:
        leave_one_out[omitted] = ranks({
            model: sum(ticks(row) for row in rows if row["case"] != omitted)
            for model, rows in per_model.items()
        })

    model_rows = []
    baselines = []
    for item in combined:
        model = item["route_or_baseline"]
        if model not in model_labels:
            baselines.append(item)
            continue
        rows = per_model[model]
        cohort = "pilot" if model in cohorts["pilot"] else "expansion"
        statuses = Counter(row["score"]["status"] for row in rows)
        case_scores = [[lookup[model, case, i]["score"]["safe_tir"] for i in ROUNDS] for case in cases]
        model_rows.append({
            "split": split, "rank": overall[model], "cohort": cohort, **item,
            "rank_r1": combined_round_ranks[1][model],
            "rank_r2": combined_round_ranks[2][model],
            "rank_r3": combined_round_ranks[3][model],
            "leave_one_case_rank_min": min(ranking[model] for ranking in leave_one_out.values()),
            "leave_one_case_rank_max": max(ranking[model] for ranking in leave_one_out.values()),
            "within_case_sd_mean": mean(map(stdev, case_scores)),
            "submission_failures": statuses["submission_failure"],
            "safety_failures": statuses["safety_failure"],
            "infrastructure_errors": statuses["infrastructure_error"],
            "simulation_failures": statuses["simulation_failure"],
            "resource_violations": statuses["resource_violation"],
            "api_error_calls": sum(sum(row["api_errors"].values()) for row in rows),
            "response_timeouts": sum(row["api_errors"].get("response_timeout_unknown_usage", 0) for row in rows),
            "reasoning_only_http_errors": sum(row["api_errors"].get("http_error_reasoning_only_at_output_limit", 0)
                                              for row in rows),
        })
    model_rows.sort(key=lambda row: (row["rank"], row["method"]))
    return {
        "split": split, "models": model_rows, "baselines": baselines,
        "aggregate_rank_groups": ranked_groups(overall),
        "stability": stability, "rounds": rounds, "cases": case_rows,
        "paired": [{"split": split, **pair} for pair in pairs],
        "leave_one_out": [
            {"split": split, "omitted_case": case, "route": model, "model": model_labels[model], "rank": ranking[model]}
            for case, ranking in leave_one_out.items()
            for model in sorted(ranking, key=lambda model: (ranking[model], model_labels[model]))
        ],
    }


def analyze(expansion, evidence):
    reports = {}
    for split in SPLITS:
        pilot_path = CONTRACT / f"{split}-plan.json"
        pilot = strict_json(pilot_path)
        old = strict_json(ROOT / "results/v0.2" / split / "attempts.json")
        old_rows = check_export(old, pilot_path, split, jobs(pilot))
        new_rows = check_export(evidence[split], PLAN, split, expansion_jobs(expansion, split))
        reports[split] = analyze_split(pilot, expansion, old_rows + new_rows)
    return {
        "primary_split": "sealed", "model_attempts": expansion["combined_agent_attempts"],
        "new_model_attempts": expansion["new_agent_attempts"],
        "baseline_runs": sum(len(reports[s]["baselines"]) * len(expansion["splits"][s]["cases"]) for s in SPLITS),
        "comparison_scope": expansion["analysis"]["comparison_scope"],
        "round_scope": "The combined round table matches repeat indices across the two chronological batches.",
        "uncertainty": "Descriptive percentile intervals from 20,000 paired case resamples. All repeats of a sampled case stay together.",
        "splits": reports,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true", help="Audit and export completed private trials")
    parser.add_argument("--output", type=Path, default=RESULTS)
    args = parser.parse_args()
    if args.collect:
        expansion = verify_expansion()
        if args.output.exists():
            raise FileExistsError(args.output)
        evidence, audit = collect(expansion)
        summary = analyze(expansion, evidence)
        args.output.mkdir(parents=True, exist_ok=False)
        for split in SPLITS:
            atomic_json(args.output / f"{split}-attempts.json", evidence[split])
        atomic_json(args.output / "audit.json", audit)
    else:
        verify_lock(EXPERIMENT / "lock.json")
        expansion = strict_json(PLAN)
        evidence = {split: strict_json(RESULTS / f"{split}-attempts.json") for split in SPLITS}
        summary = analyze(expansion, evidence)
        args.output.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output / "summary.json", summary)
    for key, file in (("models", "leaderboard"), ("rounds", "rounds"), ("paired", "paired"),
                      ("leave_one_out", "leave-one-case-out"), ("cases", "cases")):
        rows = [{"split": split, **row} for split in SPLITS for row in summary["splits"][split][key]]
        csv_export(args.output / f"{file}.csv", rows)
    for split in SPLITS:
        report = summary["splits"][split]
        print(split, [(r["method"], round(r["mean_safe_tir"], 2), r["rank"]) for r in report["models"]], flush=True)
        print(split, report["stability"]["combined"]["kendall_tau_b"], flush=True)


if __name__ == "__main__":
    main()
