"""Audit v0.2 trial evidence and export publication-safe per-attempt and paired results."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import combinations
from multiprocessing import get_context
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from gri_bench.api import summarize, validate_design
from gri_bench.evaluate import strict_json
from gri_bench.native import verify_design
from gri_bench.runner import ROOT, digest
from gri_bench.v02.matrix import CONTRACT, jobs, load_v02_case, plan_for
from gri_bench.v02.protocol import POLICY_FILE, atomic_json, loads_strict
from gri_bench.v02.trial import utc_now


def check_ledger(path, meta, limits):
    calls = meta["calls"]
    ledger = meta.get("token_accounting", [])
    if len(calls) != len(ledger) or len(calls) > limits["max_calls"]:
        raise ValueError(f"Call count mismatch: {path.name}")
    remaining = limits["completion_total"]
    for index, (call, entry) in enumerate(zip(calls, ledger, strict=True)):
        cap = min(limits["completion_per_call"], remaining)
        charge = entry["charged_completion_tokens"]
        if not (index == call["index"] == entry["call"] and
                entry["remaining_before"] == remaining and entry["requested_max_tokens"] == cap and
                0 <= charge <= cap):
            raise ValueError(f"Reservation mismatch: {path.name}")
        if "response_sha256" in call:
            raw = path / f"response-{index:02d}.bin"
            if digest(raw) != call["response_sha256"]:
                raise ValueError(f"Response hash mismatch: {path.name}")
        if entry["basis"] == "provider_usage":
            if loads_strict(raw.read_bytes())["usage"]["completion_tokens"] != charge:
                raise ValueError(f"Reported usage mismatch: {path.name}")
        elif charge != cap:
            raise ValueError(f"Unknown or failed usage must retain the allowance: {path.name}")
        remaining -= charge
        if entry["remaining_after"] != remaining:
            raise ValueError(f"Remaining allowance mismatch: {path.name}")
    if meta.get("charged_completion_tokens", 0) != limits["completion_total"] - remaining:
        raise ValueError(f"Charged completion total mismatch: {path.name}")
    if sum("error" in c for c in calls) > limits["api_errors"]:
        raise ValueError(f"API stop policy mismatch: {path.name}")


def failing(m):
    return m["tbr70"] > 4 or m["tbr54"] > 1 or m["minimum"] < 40


def audit_attempt(path, case, method, model, plan, instance, seeds):
    meta = strict_json(path / "metadata.json")
    score = strict_json(path / "score.json")
    if (meta["trial_id"], meta["case"], meta["split"], meta["method"], meta["requested_model"]) != (
            path.name, case, plan["split"], method, model):
        raise ValueError("Unexpected trial identity: " + path.name)
    provenance = meta["provenance"]
    if provenance["plan_sha256"] != digest(CONTRACT / f"{plan['split']}-plan.json"):
        raise ValueError("Unregistered trial plan: " + path.name)
    if provenance["runtime_sha256"] != digest(CONTRACT / "runtime-lock.json"):
        raise ValueError("Unregistered runtime: " + path.name)
    limits = strict_json(POLICY_FILE)["budget"]
    check_ledger(path, meta, limits)
    receipt_times = [receipt["at_seconds"] for receipt in meta["submissions"]]
    if sorted(receipt_times) != receipt_times or any(not 0 <= t < limits["agent_wall_seconds"] for t in receipt_times):
        raise ValueError("Invalid submission time: " + path.name)
    if bool(receipt_times) != score["format_valid"]:
        raise ValueError("Unexpected score format status: " + path.name)
    design_path = path / "design.json"
    if receipt_times:
        if digest(design_path) != meta["submissions"][-1]["design_sha256"]:
            raise ValueError("Invalid final design receipt: " + path.name)
        validate_design(strict_json(design_path), instance)
    if meta["resource_violations"] and (score["safe_tir"] or score["status"] != "resource_violation"):
        raise ValueError("Resource violation was not applied: " + path.name)
    if "rows" in score:
        rows = score["rows"]
        observed = {(r["patient"], r["seed"], r["variant"]) for r in rows}
        expected = {(p, s, v) for p in instance["patients"] for s in seeds for v in instance["variants"]}
        if observed != expected or len(rows) != len(expected):
            raise ValueError("Wrong verifier panel: " + path.name)
        computed = summarize(rows)
        if any(score[k] != v for k, v in computed.items()):
            raise ValueError("Native trajectory aggregate mismatch: " + path.name)
        if score["failed_trajectories"] != sum(failing(r["metrics"]) for r in rows):
            raise ValueError("Safety failure count mismatch: " + path.name)
    elif score["safe_tir"] or score["feasible"]:
        raise ValueError("Missing verifier trajectories: " + path.name)
    exposed_score = {k: v for k, v in score.items() if k not in ("rows", "reason")}
    evidence = {
        "metadata_sha256": digest(path / "metadata.json"),
        "score_sha256": digest(path / "score.json"),
        "design_sha256": digest(design_path) if receipt_times else None,
        "transcript_sha256": digest(path / "transcript.json") if (path / "transcript.json").exists() else None,
    }
    result = {
        "trial_id": path.name, "case": case, "method": method, "requested_model": model,
        "repetition": int(path.name.rsplit("__r", 1)[-1]) if model else None,
        "started_utc": meta["started_utc"], "finished_utc": meta["finished_utc"],
        "score": exposed_score, "timing": meta["timing"], "cpu_seconds": meta.get("cpu_seconds"),
        "accepted_submissions": len(receipt_times), "stop_reason": meta.get("stop_reason"),
        "resource_violations": meta["resource_violations"],
        "auxiliary_files": meta.get("auxiliary_files"),
        "model_calls": len(meta["calls"]),
        "returned_models": sorted({c["returned_model"] for c in meta["calls"] if c.get("returned_model")}),
        "api_errors": dict(Counter(c["error"] for c in meta["calls"] if "error" in c)),
        "finish_reasons": dict(Counter(c["finish_reason"] for c in meta["calls"] if c.get("finish_reason"))),
        "corrective_turns": sum(c.get("correction_sent", False) for c in meta["calls"]),
        "charged_completion_tokens": meta.get("charged_completion_tokens", 0),
        "token_accounting": meta.get("token_accounting", []),
        "evidence": evidence,
    }
    if plan["split"] == "development" and receipt_times:
        result["design"] = strict_json(design_path)
    return result


def csv_export(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def group_metrics(rows):
    scores = [r["score"] for r in rows]
    good = [s["safe_tir"] for s in scores if s["feasible"]]
    valid = sum(s["format_valid"] for s in scores)
    return {
        "attempts": len(scores), "valid": valid, "safety_passes": len(good),
        "mean_safe_tir": mean(s["safe_tir"] for s in scores),
        "mean_feasible_tir": mean(good) if good else None,
        "scored_trajectories": sum(s.get("trajectories", 0) for s in scores),
    }


def summarize_matrix(plan, records):
    cases = plan["cases"]
    labels = {m["route"]: m["display"] for m in plan["models"]}
    labels |= {"constant": "Constant baseline", "responsive": "Responsive baseline"}
    by_method = defaultdict(list)
    by_case = defaultdict(list)
    for row in records:
        key = row["requested_model"] or row["method"]
        by_method[key].append(row)
        by_case[(key, row["case"])].append(row)
    case_metrics = {(key, case): group_metrics(by_case[(key, case)]) for key in labels for case in cases}
    case_rows = [{"method": labels[key], "case": case, **case_metrics[(key, case)]}
                 for key in labels for case in cases]
    matrix = {key: np.array([case_metrics[(key, case)]["mean_safe_tir"] for case in cases]) for key in labels}
    rank = sorted(by_method, key=lambda key: (-mean(matrix[key]), labels[key]))
    leaderboard = []
    for key in rank:
        rows = by_method[key]
        per_round = [mean(r["score"]["safe_tir"] for r in rows if r["repetition"] == i)
                     for i in range(1, plan["repetitions"] + 1)] if key in labels and key not in ("constant", "responsive") else []
        leaderboard.append({
            "method": labels[key], "route_or_baseline": key, **group_metrics(rows),
            "delta_vs_constant": float(mean(matrix[key] - matrix["constant"])),
            "round_mean_sd": stdev(per_round) if len(per_round) > 1 else None,
            "round_min_mean": min(per_round) if per_round else None,
            "round_max_mean": max(per_round) if per_round else None,
        })
    samples = np.random.default_rng(20261113).integers(0, len(cases), size=(20_000, len(cases)))
    pairs = []
    for a, b in combinations(rank, 2):
        delta = matrix[a] - matrix[b]
        lo, hi = np.quantile(delta[samples].mean(axis=1), [0.025, 0.975])
        pairs.append({
            "method_a": labels[a], "method_b": labels[b], "cases": len(cases),
            "mean_delta_tir_points": float(mean(delta)), "bootstrap_95_low": float(lo),
            "bootstrap_95_high": float(hi), "cases_a_higher": int((delta > 0).sum()),
            "cases_tied": int((delta == 0).sum()), "cases_b_higher": int((delta < 0).sum()),
        })
    return leaderboard, case_rows, pairs


def reverify(task):
    path, case, split = task
    instance, seeds = load_v02_case(case, split)
    design = strict_json(path / "design.json")
    recalculated = verify_design(instance, design, seeds)
    recorded = strict_json(path / "score.json")
    if any(recorded[k] != v for k, v in recalculated.items()):
        raise ValueError("Native re-verification mismatch: " + path.name)
    return {"trial_id": path.name, "trajectories": recalculated["trajectories"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "sealed"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reverify", action="store_true")
    args = parser.parse_args()
    plan = plan_for(args.split)
    directory = ROOT / "private/v02/runs" / args.split
    expected = jobs(plan)
    if {p.name for p in directory.iterdir() if p.is_dir()} != {r[0] for r in expected}:
        raise ValueError("Run directory differs from the registered matrix")
    records = []
    for name, case, method, route in expected:
        instance, seeds = load_v02_case(case, args.split)
        records.append(audit_attempt(directory / name, case, method, route, plan, instance, seeds))
    checked = []
    if args.reverify:
        chosen = {}
        for row in records:
            if row["score"].get("trajectories"):
                key = row["requested_model"] or row["method"]
                chosen.setdefault(key, (directory / row["trial_id"], row["case"], args.split))
                if not row["score"]["feasible"]:
                    chosen.setdefault("safety failure", (directory / row["trial_id"], row["case"], args.split))
        with ProcessPoolExecutor(max_workers=3, mp_context=get_context("spawn")) as pool:
            checked = list(pool.map(reverify, dict.fromkeys(chosen.values())))
    leaderboard, case_rows, pairs = summarize_matrix(plan, records)
    args.output.mkdir(parents=True, exist_ok=False)
    atomic_json(args.output / "attempts.json", {
        "split": args.split, "plan_sha256": digest(CONTRACT / f"{args.split}-plan.json"),
        "attempts": records,
    })
    atomic_json(args.output / "summary.json", {
        "split": args.split, "created_utc": utc_now(), "cases": len(plan["cases"]),
        "seed_count": plan["evaluation_seeds_per_case"], "leaderboard": leaderboard,
        "status_counts": dict(Counter(row["score"]["status"] for row in records)),
        "agent_attempts": plan["agent_attempts"], "baseline_attempts": plan["baseline_attempts"],
        "audited_api_reservations": sum(r["model_calls"] for r in records), "reverified_designs": checked,
        "uncertainty": "Percentile bootstrap of paired case means. The 20,000 resamples retain every repetition of each sampled case.",
    })
    csv_export(args.output / "leaderboard.csv", leaderboard)
    csv_export(args.output / "cases.csv", case_rows)
    csv_export(args.output / "paired.csv", pairs)
    print(args.split, [(r["method"], r["valid"], r["safety_passes"], round(r["mean_safe_tir"], 2))
                       for r in leaderboard], flush=True)


if __name__ == "__main__":
    main()
