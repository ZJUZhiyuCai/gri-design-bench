"""Size, generate and commit to the sealed evaluation inputs after the pilot."""
import argparse
from collections import defaultdict
from csv import DictReader
import hashlib
import hmac
import math
from pathlib import Path
import random
import secrets
from statistics import mean, stdev
import tempfile

from simglucose.controller.basal_bolus_ctrller import CONTROL_QUEST

from gri_bench.evaluate import strict_json
from gri_bench.runner import ROOT, digest, load_case
from gri_bench.v02.matrix import CONTRACT, DEV_CASES, PRIVATE_SEALED, plan_for
from gri_bench.v02.protocol import atomic_json
from gri_bench.v02.trial import utc_now


def cohort_size(plan, records):
    config = plan["sealed_planning"]
    strong = next(m["route"] for m in plan["models"] if m["id"] == "gpt")
    gpt = defaultdict(list)
    constant = {}
    for row in records:
        if row["method"] == "agent" and row["requested_model"] == strong:
            gpt[row["case"]].append(row["score"]["safe_tir"])
        if row["method"] == "constant":
            constant[row["case"]] = row["score"]["safe_tir"]
    if set(gpt) != set(DEV_CASES) or set(constant) != set(DEV_CASES):
        raise ValueError("Missing pilot scores for sizing")
    if any(len(scores) != plan["repetitions"] for scores in gpt.values()):
        raise ValueError("Incomplete pilot repetitions")
    differences = {case: mean(gpt[case]) - constant[case] for case in DEV_CASES}
    sd = stdev(differences.values())
    estimate = math.ceil((1.96 * sd / config["target_half_width_tir_points"]) ** 2)
    multiple = config["stratification_multiple"]
    n = min(config["case_count_max"], max(config["case_count_min"], multiple * math.ceil(estimate / multiple)))
    return {
        "pilot_case_differences_tir_points": differences,
        "pilot_paired_case_sd_tir_points": sd,
        "normal_approximation_case_count": estimate,
        "chosen_case_count": n,
        "estimated_half_width_tir_points": 1.96 * sd / math.sqrt(n),
        **config,
    }


def generate(n, evaluation_seeds, entropy):
    """Draw stratified new cohorts; use the six public material envelopes in rotation."""
    rng = random.Random(int.from_bytes(entropy, "big"))
    with Path(CONTROL_QUEST).open() as stream:
        tdi = {r["Name"]: float(r["TDI"]) for r in DictReader(stream)}
    age_groups = defaultdict(list)
    for name in sorted(tdi):
        age_groups[name.split("#")[0]].append(name)
    templates = [load_case(case)[0] for case in DEV_CASES]
    legacy_sealed = strict_json(ROOT / "contract/sealed-manifest.json")["files"]
    used = {tuple(sorted(load_case(case)[0]["patients"])) for case in (*DEV_CASES, *legacy_sealed)}
    train = rng.sample(range(830_000_000, 840_000_000), 2*n)
    heldout = rng.sample(range(850_000_000, 860_000_000), evaluation_seeds*n)
    records = {}
    for i in range(n):
        template = templates[i % len(templates)]
        pool = age_groups[template["patients"][0].split("#")[0]]
        while True:
            cohort = tuple(sorted(rng.sample(pool, 3)))
            if cohort not in used:
                used.add(cohort)
                break
        case = f"v02-sealed-{i + 1:02d}"
        salt = hmac.digest(entropy, case.encode(), "sha256").hex()
        records[case] = {
            "instance": {
                **template, "id": case, "split": "sealed", "patients": list(cohort),
                "tdi": {p: tdi[p] for p in cohort}, "training_seeds": train[2*i:2*(i+1)],
            },
            "evaluation_seeds": heldout[evaluation_seeds*i:evaluation_seeds*(i+1)],
            "salt": salt,
        }
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-results", type=Path, required=True)
    args = parser.parse_args()
    pilot = plan_for("development")
    results = strict_json(args.pilot_results)
    if results["plan_sha256"] != digest(CONTRACT / "development-plan.json"):
        raise ValueError("Pilot results do not match the registered plan")
    sizing = cohort_size(pilot, results["attempts"])
    evaluation_seeds = pilot["evaluation_seeds_per_case"]
    entropy = secrets.token_bytes(32)
    cases = generate(sizing["chosen_case_count"], evaluation_seeds, entropy)
    registration = utc_now()
    manifest_path = CONTRACT / "sealed-manifest.json"
    plan_path = CONTRACT / "sealed-plan.json"
    lock_path = CONTRACT / "sealed-lock.json"
    if any(p.exists() for p in (PRIVATE_SEALED, manifest_path, plan_path, lock_path)):
        raise FileExistsError("A sealed panel has already been generated")
    PRIVATE_SEALED.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=PRIVATE_SEALED.parent) as folder:
        work = Path(folder) / "sealed"
        work.mkdir(mode=0o700)
        (work / "master.hex").write_text(entropy.hex() + "\n")
        hashes = {}
        for case, record in cases.items():
            path = work / f"{case}.json"
            atomic_json(path, record)
            hashes[case] = digest(path)
        work.rename(PRIVATE_SEALED)
    atomic_json(manifest_path, {
        "registered_utc": registration, "salted_sha256": True, "files": hashes,
        "generator_sha256": digest(Path(__file__)), "entropy_sha256": hashlib.sha256(entropy).hexdigest(),
    })
    atomic_json(plan_path, {
        **pilot, "registered_utc": registration, "split": "sealed", "cases": list(cases),
        "agent_attempts": len(cases) * pilot["repetitions"] * len(pilot["models"]),
        "baseline_attempts": len(cases) * 2, "sizing": sizing,
        "development_evidence_sha256": digest(args.pilot_results),
        "case_construction": "New stratified triplets from the 30 public virtual patients, with the six development envelopes in rotation.",
    })
    frozen = (manifest_path, plan_path, Path(__file__).resolve(), CONTRACT / "runtime-lock.json")
    atomic_json(lock_path, {
        "registered_utc": registration, "files": {str(p.relative_to(ROOT)): digest(p) for p in frozen},
    })
    plan_for("sealed")
    print("sealed panel frozen", len(cases), "cases", evaluation_seeds, "seeds per case", registration)


if __name__ == "__main__":
    main()
