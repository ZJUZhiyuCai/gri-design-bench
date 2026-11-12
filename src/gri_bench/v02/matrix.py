"""Run the registered development or sealed matrix and grade completed attempts."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from multiprocessing import get_context
from pathlib import Path
import platform
import re
import subprocess
from threading import BoundedSemaphore

from gri_bench.evaluate import strict_json
from gri_bench.runner import ROOT, digest, load_case, verify_runtime_lock

from .protocol import POLICY_FILE, atomic_json, excluded_model
from .search import training_seeds
from .trial import grade_trial, route_label, run_trial, utc_now

CONTRACT = ROOT / "contract/v0.2"
DEV_CASES = tuple(f"dev-{i:02d}" for i in range(1, 7))
DEV_EVALUATION = ROOT / "instances/v0.2/development-evaluation.json"
PRIVATE_SEALED = ROOT / "private/v02/sealed"
CONTEXT = "colima-etbench"
IMAGE = "gri-bench:0.2.0"


def load_v02_case(case, split):
    if split == "development":
        if case not in DEV_CASES:
            raise ValueError("Unknown public development case")
        instance, _ = load_case(case)
        instance["training_seeds"] = training_seeds(instance)
        seeds = strict_json(DEV_EVALUATION)["cases"][case]
    else:
        manifest = strict_json(CONTRACT / "sealed-manifest.json")
        if case not in manifest["files"]:
            raise ValueError("Case is absent from the v0.2 commitments")
        path = PRIVATE_SEALED / f"{case}.json"
        if digest(path) != manifest["files"][case]:
            raise ValueError("Sealed case commitment mismatch")
        record = strict_json(path)
        instance, seeds = record["instance"], record["evaluation_seeds"]
    if instance["id"] != case or instance["split"] != split:
        raise ValueError("Case identity mismatch")
    if len(seeds) != len(set(seeds)) or set(seeds) & set(instance["training_seeds"]):
        raise ValueError("Evaluation seeds must be distinct and held out from training")
    return instance, seeds


def verify_lock(path):
    lock = strict_json(path)
    for name, expected in lock["files"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Frozen v0.2 file changed: " + name)
    return lock


def plan_for(split):
    verify_runtime_lock()
    verify_lock(CONTRACT / "runtime-lock.json")
    if split == "sealed":
        verify_lock(CONTRACT / "sealed-lock.json")
    plan = strict_json(CONTRACT / f"{split}-plan.json")
    if plan["split"] != split:
        raise ValueError("Plan split mismatch")
    routes = [m["route"] for m in plan["models"]]
    if len(routes) != len(set(routes)) or any(route_label(r) is None or excluded_model(r) for r in routes):
        raise ValueError("Plan contains a duplicate, invalid or excluded model route")
    ids = [m["id"] for m in plan["models"]]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z0-9-]+", s) for s in ids):
        raise ValueError("Invalid model IDs")
    cases = plan["cases"]
    if not cases or len(cases) != len(set(cases)):
        raise ValueError("Invalid case IDs")
    for case in cases:
        _, seeds = load_v02_case(case, split)
        if len(seeds) != plan["evaluation_seeds_per_case"]:
            raise ValueError("Evaluation panel differs from the plan")
    if len(jobs(plan)) != plan["agent_attempts"] + plan["baseline_attempts"]:
        raise ValueError("Matrix size differs from the plan")
    return plan


def jobs(plan):
    models = plan["models"]
    result = []
    for repeat in range(1, plan["repetitions"] + 1):
        for i, case in enumerate(plan["cases"]):
            shift = (i + repeat - 1) % len(models)
            for model in models[shift:] + models[:shift]:
                result.append((f"{case}__{model['id']}__r{repeat}", case, "agent", model["route"]))
    for case in plan["cases"]:
        for mode in ("constant", "responsive"):
            result.append((f"{case}__baseline-{mode}", case, mode, None))
    return result


def image_id(context, image):
    return subprocess.check_output(
        ["docker", "--context", context, "image", "inspect", image, "--format", "{{.Id}}"],
        text=True, timeout=30,
    ).strip()


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def matrix(plan, context, image):
    split = plan["split"]
    expected_image = strict_json(CONTRACT / "runtime-lock.json")["image_id"]
    local_image = image_id(context, image)
    if local_image != expected_image:
        raise ValueError("Trial image differs from the registered image")
    folder = ROOT / "private/v02/runs" / split
    folder.mkdir(parents=True, exist_ok=True)
    provenance = {
        "plan_sha256": digest(CONTRACT / f"{split}-plan.json"),
        "runtime_sha256": digest(CONTRACT / "runtime-lock.json"),
        "source_commit": git_head(), "image_id": local_image, "docker_context": context,
        "host": platform.platform(),
    }
    manifest = folder / "manifest.json"
    if manifest.exists():
        previous = strict_json(manifest)["provenance"]
        if any(previous[k] != v for k, v in provenance.items() if k != "source_commit"):
            raise ValueError("Run provenance differs from the previous execution")
    else:
        atomic_json(manifest, {"provenance": provenance, "started_utc": utc_now()})
    config = strict_json(POLICY_FILE)["execution"]
    gate = BoundedSemaphore(config["concurrent_active_sandboxes"])
    # Validate interrupted attempts before starting new calls.
    pending, grading = [], []
    for name, case, method, model in jobs(plan):
        output = folder / name
        instance, seeds = load_v02_case(case, split)
        if not output.exists():
            pending.append((output, instance, seeds, method, model))
        else:
            meta = strict_json(output / "metadata.json")
            if meta["status"] == "running" or meta["provenance"]["plan_sha256"] != provenance["plan_sha256"]:
                raise ValueError("Interrupted or mismatched attempt: " + name)
            if not (output / "score.json").exists():
                grading.append((output, instance, seeds))

    def run(item):
        output, instance, seeds, method, model = item
        meta = run_trial(output, instance, method, model, context, local_image, provenance, gate)
        print("trial", output.name, meta["status"], meta.get("stop_reason"),
              round(meta["timing"]["total_seconds"], 1), flush=True)
        return output, instance, seeds

    with ProcessPoolExecutor(max_workers=config["concurrent_native_graders"], mp_context=get_context("spawn")) as graders:
        results = {graders.submit(grade_trial, *item): item[0].name for item in grading}
        with ThreadPoolExecutor(max_workers=config["concurrent_trials"]) as trials:
            for completed in as_completed([trials.submit(run, item) for item in pending]):
                item = completed.result()
                results[graders.submit(grade_trial, *item)] = item[0].name
        for completed in as_completed(results):
            score = completed.result()
            print("score", results[completed], score["status"], round(score["safe_tir"], 3), flush=True)
    print("matrix complete", split, len(jobs(plan)), utc_now(), flush=True)


@contextmanager
def unique_run(split):
    lock = ROOT / "private/v02/runs" / f".{split}.active"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.mkdir(exist_ok=False)
    try:
        yield
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "sealed"), default="development")
    parser.add_argument("--context", default=CONTEXT)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--case", choices=DEV_CASES, help="Run a single public case outside the registered matrix")
    parser.add_argument("--model", help="Use this route in a single public case")
    parser.add_argument("--output", type=Path, help="New output directory for a single public case")
    args = parser.parse_args()
    if args.case:
        if args.split != "development" or args.output is None:
            parser.error("A single public case requires --output and the development split")
        plan_for("development")
        instance, seeds = load_v02_case(args.case, "development")
        method = "agent" if args.model else "responsive"
        local_image = image_id(args.context, args.image)
        run_trial(args.output, instance, method, args.model, args.context, local_image,
                  {"source_commit": git_head(), "image_id": local_image, "profile": "local-reproduction"})
        print({k: v for k, v in grade_trial(args.output, instance, seeds).items() if k != "rows"})
    elif args.output or args.model:
        parser.error("--output and --model require --case")
    else:
        with unique_run(args.split):
            matrix(plan_for(args.split), args.context, args.image)


if __name__ == "__main__":
    main()
