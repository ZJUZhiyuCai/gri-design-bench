"""Schedule the supplemental v0.2 trials using the registered runner and verifier."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import get_context
import platform
import subprocess
from threading import BoundedSemaphore

from gri_bench.evaluate import strict_json
from gri_bench.runner import ROOT, digest
from gri_bench.v02.matrix import (
    CONTEXT, CONTRACT, IMAGE, git_head, image_id, jobs, load_v02_case, plan_for, unique_run, verify_lock,
)
from gri_bench.v02.protocol import POLICY_FILE, atomic_json, excluded_model
from gri_bench.v02.trial import grade_trial, run_trial, utc_now

EXPERIMENT = ROOT / "experiments/v0.2-expansion-2026-11-13"
PLAN = EXPERIMENT / "plan.json"
RUNS = ROOT / "private/v02/expansion-2026-11-13/runs"
SPLITS = ("development", "sealed")


def expansion_jobs(plan, split):
    source = plan["splits"][split]
    subset = {"models": plan["models"], "cases": source["cases"], "repetitions": plan["repetitions"]}
    return [job for job in jobs(subset) if job[2] == "agent"]


def verify_expansion():
    verify_lock(EXPERIMENT / "lock.json")
    plan = strict_json(PLAN)
    legacy_three = strict_json(ROOT / "experiments/repeats-2026-11-11/plan.json")["models"]
    legacy_six = strict_json(ROOT / "experiments/expansion-2026-11-11/plan.json")["models"]
    pilot_routes = {m["route"] for m in strict_json(CONTRACT / "development-plan.json")["models"]}
    routes = [m["route"] for m in plan["models"]]
    ids = {m["id"] for m in plan["models"]}
    if (len(routes) != 6 or len(ids) != 6 or set(routes) != (set(legacy_three + legacy_six) - pilot_routes)
            or any(excluded_model(route) for route in routes)):
        raise ValueError("The expansion must use the six remaining v0.1.1 routes")
    for split in SPLITS:
        pilot = plan_for(split)
        source = plan["splits"][split]
        if (source["cases"] != pilot["cases"] or plan["repetitions"] != pilot["repetitions"]
                or source["evaluation_seeds_per_case"] != pilot["evaluation_seeds_per_case"]):
            raise ValueError("Expansion panel or repetitions differ from v0.2: " + split)
        registered_jobs = expansion_jobs(plan, split)
        if len({j[0] for j in registered_jobs}) != len(registered_jobs) or len(registered_jobs) != 108:
            raise ValueError("Invalid expansion schedule: " + split)
    if sum(len(expansion_jobs(plan, split)) for split in SPLITS) != plan["new_agent_attempts"]:
        raise ValueError("Expansion count differs from the registered plan")
    return plan


def run_matrix(plan):
    source = git_head()
    # The plan and runner have to be in the source revision before any trial.
    files = strict_json(EXPERIMENT / "lock.json")["files"]
    committed = subprocess.check_output(
        ["git", "diff", "--name-only", source, "--", *files, str(EXPERIMENT / "lock.json")],
        cwd=ROOT, text=True, timeout=30,
    )
    if committed:
        raise ValueError("Commit the frozen expansion first")
    relative_lock = (EXPERIMENT / "lock.json").relative_to(ROOT).as_posix()
    subprocess.run(["git", "cat-file", "-e", f"{source}:{relative_lock}"], cwd=ROOT, check=True, timeout=30)
    expected_image = strict_json(CONTRACT / "runtime-lock.json")["image_id"]
    local_image = image_id(CONTEXT, IMAGE)
    if local_image != expected_image:
        raise ValueError("Trial image differs from the registered image")
    RUNS.mkdir(parents=True, exist_ok=True)
    provenance = {
        "plan_sha256": digest(PLAN), "runtime_sha256": digest(CONTRACT / "runtime-lock.json"),
        "source_commit": source, "image_id": local_image, "docker_context": CONTEXT,
        "host": platform.platform(),
    }
    manifest = RUNS / "manifest.json"
    if manifest.exists():
        previous = strict_json(manifest)["provenance"]
        if any(previous[k] != value for k, value in provenance.items() if k != "source_commit"):
            raise ValueError("Existing run uses a different runtime or plan")
    else:
        atomic_json(manifest, {"provenance": provenance, "started_utc": utc_now()})

    pending, grading = [], []
    for split in SPLITS:
        folder = RUNS / split
        folder.mkdir(exist_ok=True)
        expected = expansion_jobs(plan, split)
        if {p.name for p in folder.iterdir()} - {row[0] for row in expected}:
            raise ValueError("Unexpected trial files in " + split)
        for name, case, method, model in expected:
            output = folder / name
            instance, seeds = load_v02_case(case, split)
            if not output.exists():
                pending.append((output, instance, seeds, method, model))
                continue
            meta = strict_json(output / "metadata.json")
            if (meta["status"] == "running" or meta["provenance"]["plan_sha256"] != provenance["plan_sha256"]
                    or meta["provenance"]["runtime_sha256"] != provenance["runtime_sha256"]):
                raise ValueError("Interrupted or mismatched attempt: " + name)
            if not (output / "score.json").exists():
                grading.append((output, instance, seeds))

    config = strict_json(POLICY_FILE)["execution"]
    gate = BoundedSemaphore(config["concurrent_active_sandboxes"])

    def attempt(item):
        output, instance, seeds, method, model = item
        meta = run_trial(output, instance, method, model, CONTEXT, local_image, provenance, gate)
        print("trial", output.name, meta["status"], meta.get("stop_reason"),
              round(meta["timing"]["total_seconds"], 1), flush=True)
        return output, instance, seeds

    with ProcessPoolExecutor(max_workers=config["concurrent_native_graders"], mp_context=get_context("spawn")) as graders:
        results = {graders.submit(grade_trial, *item): item[0].name for item in grading}
        with ThreadPoolExecutor(max_workers=config["concurrent_trials"]) as trials:
            for completed in as_completed([trials.submit(attempt, item) for item in pending]):
                item = completed.result()
                results[graders.submit(grade_trial, *item)] = item[0].name
        for completed in as_completed(results):
            score = completed.result()
            print("score", results[completed], score["status"], round(score["safe_tir"], 3), flush=True)
    print("expansion complete", plan["new_agent_attempts"], utc_now(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check frozen inputs and print planned counts")
    args = parser.parse_args()
    plan = verify_expansion()
    if args.verify:
        for split in SPLITS:
            print(split, len(expansion_jobs(plan, split)))
        return
    with unique_run("development"), unique_run("sealed"):
        run_matrix(plan)


if __name__ == "__main__":
    main()
