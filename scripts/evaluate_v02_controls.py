"""Native verification of fixed calibration controls on the public v0.2 panel."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

from calibrate_v02 import CASES, write
from check_v02_scenarios import SAMPLE
from gri_bench.api import validate_design
from gri_bench.evaluate import strict_json
from gri_bench.native import verify_design
from gri_bench.v02.matrix import load_v02_case
from gri_bench.v02.search import zero_design


def candidate_records(case, instance, path, phase):
    if phase == "initial":
        yield "zero", zero_design(instance)
        yield "old_prompt_example", SAMPLE
        checkpoints = (("constant", 30), ("responsive", 30), ("responsive", 300))
    else:
        checkpoints = (("responsive", 3000),)
    for mode, budget in checkpoints:
        row = strict_json(path / f"{case}-{mode}-{budget}.json")
        yield f"{mode}_{budget}", row["design"]


def evaluate_case(case, cpu, phase):
    instance, seeds = load_v02_case(case, "development")
    result = []
    for name, design in candidate_records(case, instance, cpu, phase):
        row = {"case": case, "control": name, "design": design}
        try:
            validate_design(design, instance)
        except ValueError:
            row["score"] = {"format_valid": False, "feasible": False, "safe_tir": 0.0}
        else:
            row["score"] = {k: v for k, v in verify_design(instance, design, seeds).items() if k != "rows"}
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", type=Path, required=True)
    parser.add_argument("--phase", choices=("initial", "long"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=get_context("spawn")) as pool:
        futures = {pool.submit(evaluate_case, case, args.cpu, args.phase): case for case in CASES}
        for future in as_completed(futures):
            case = futures[future]
            results = future.result()
            write(args.output / f"{case}.json", results)
            print(case, [(r["control"], round(r["score"]["safe_tir"], 2)) for r in results], flush=True)


if __name__ == "__main__":
    main()
