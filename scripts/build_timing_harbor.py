"""Build the public-input timing task and its independently computed verifier reference."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from simglucose.patient.t1dpatient import Action, T1DPatient

from gri_bench.api import Experiment, individual_design, validate_design
from gri_bench.native import native_trace


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "harbor/release-timing-attribution"
IMAGE = "python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36"
SIMULATOR_FILES = ("__init__.py", "api.py", "physiology.py", "release.py", "native.py")
UPSTREAM = "0c224bf9349047c82ff8ff5fae62e12dca8e89ad"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False)
        stream.write("\n")


def public_panel(meal_seeds=(981032001, 981032002)):
    instance_path = ROOT / "instances/dev/dev-06.json"
    reference_path = ROOT / "results/v0.2/calibration/robust-reference.json"
    instance = json.loads(instance_path.read_text())
    design = next(row["design"] for row in json.loads(reference_path.read_text())["cases"] if row["case"] == "dev-06")
    validate_design(design, instance)
    panel = {"instance": instance, "design": design, "seeds": list(meal_seeds)}
    return panel, {str(path.relative_to(ROOT)): sha(path) for path in (instance_path, reference_path)}


def original_replay(patient, vg, patient_seed, meals, rates):
    subject = T1DPatient.withName(patient, seed=patient_seed, random_init_bg=False)
    plasma = [subject.state[3] / vg]
    for minute, meal in enumerate(meals):
        subject.step(Action(CHO=float(meal), insulin=float(rates[minute // 3])))
        if not subject._odesolver.successful() or not np.isfinite(subject.state).all():
            raise RuntimeError(f"Original RHS replay failed at minute {minute + 1}")
        plasma.append(subject.state[3] / vg)
    return np.asarray(plasma)


def reference_rows(panel):
    instance = panel["instance"]
    rows = []
    for patient, seed, variant, params, _, meals in Experiment(instance, seeds=panel["seeds"]).jobs:
        design = individual_design(panel["design"], instance["tdi"][patient])
        trace, native = native_trace(patient, meals, design, instance["patient_seed"], original_rhs=True)
        days = trace[:, 2].reshape(3, 480)
        flat = days.copy()
        flat[1:] = np.mean(days[1:], axis=1, keepdims=True)
        shift = days.copy()
        shift[1:] = np.roll(days[1:], 240, axis=1)
        for arm, rates in (("responsive", days), ("daily_flat", flat), ("daily_shift_12h", shift)):
            plasma = native if arm == "responsive" else original_replay(
                patient, params.Vg, instance["patient_seed"], meals, rates.ravel()
            )
            end = plasma[1443::3]
            assert len(end) == 960 and np.allclose(plasma[:1441], native[:1441], rtol=0, atol=1e-6)
            assert np.allclose(rates.sum(axis=1), days.sum(axis=1), rtol=0, atol=1e-9)
            rows.append({"patient": patient, "seed": seed, "variant": variant, "arm": arm,
                         "rate_u_min": rates.ravel().tolist(), "daily_dose_u": (3 * rates.sum(axis=1)).tolist(),
                         "tir": float(100 * np.count_nonzero((end >= 70) & (end <= 180)) / len(end)),
                         "tbr70": float(100 * np.count_nonzero(end < 70) / len(end)),
                         "tbr54": float(100 * np.count_nonzero(end < 54) / len(end)),
                         "minimum": float(plasma.min())})
        print("reference", patient, seed, variant, flush=True)
    return rows


def dockerfiles(out, agent_base, verifier_base):
    for name in SIMULATOR_FILES:
        shutil.copyfile(ROOT / "src/gri_bench" / name, out / "environment/simulator" / name)
    shutil.copyfile(ROOT / "requirements-lock.txt", out / "environment/requirements-lock.txt")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / name, out / "environment" / name)
    (out / "environment/Dockerfile").write_text(f"""ARG BASE_IMAGE={agent_base}
FROM ${{BASE_IMAGE}}
ENV MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/gri-numba
USER root
COPY requirements-lock.txt /opt/requirements-lock.txt
RUN python -I -c 'import importlib.metadata as m; import pathlib; assert all(m.version(n) == v for n, v in (line.split("==", 1) for line in pathlib.Path("/opt/requirements-lock.txt").read_text().splitlines()))' \\
    || (pip install --no-cache-dir setuptools==80.10.2 wheel==0.48.0 && pip install --no-cache-dir --no-build-isolation -r /opt/requirements-lock.txt)
COPY simulator /opt/gri_bench
RUN printf '/opt\\n' > /usr/local/lib/python3.12/site-packages/gri_bench.pth && mkdir -p /app/output
COPY LICENSE THIRD_PARTY_NOTICES.md /opt/licenses/
COPY public /app/public
WORKDIR /app
""")
    (out / "tests/Dockerfile").write_text(f"""ARG BASE_IMAGE={verifier_base}
FROM ${{BASE_IMAGE}}
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
COPY requirements-lock.txt /opt/verifier-requirements.txt
RUN python -I -c 'import importlib.metadata as m; import pathlib; assert all(m.version(n) == v for n, v in (line.split("==", 1) for line in pathlib.Path("/opt/verifier-requirements.txt").read_text().splitlines()))' \\
    || pip install --no-cache-dir -r /opt/verifier-requirements.txt
COPY . /tests/
RUN mkdir -p /app/output /logs/verifier
WORKDIR /tests
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agent-base", default=IMAGE)
    parser.add_argument("--verifier-base", default=IMAGE)
    parser.add_argument("--meal-seeds", nargs=2, type=int, default=(981032001, 981032002),
                        metavar=("SEED1", "SEED2"), help="Two distinct public meal seeds for the task panel.")
    parser.add_argument("--reuse-reference", type=Path, help="Reuse a previously built, provenance-checked reference.")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:@-]+", image)
           for image in (args.agent_base, args.verifier_base)):
        parser.error("Invalid base image reference")
    if len(set(args.meal_seeds)) != 2 or any(not 0 <= seed < 2**32 for seed in args.meal_seeds):
        parser.error("Meal seeds must be distinct unsigned 32-bit integers")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(TEMPLATE, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    public = out / "environment/public"
    public.mkdir(parents=True)
    (out / "environment/simulator").mkdir()
    shutil.move(out / "results.schema.json", public / "results.schema.json")
    panel, input_hashes = public_panel(args.meal_seeds)
    save(public / "panel.json", panel)
    dockerfiles(out, args.agent_base, args.verifier_base)
    for path in (out / "solution/solve.sh", out / "tests/test.sh"):
        path.chmod(0o755)
    provenance = out / "authoring/provenance"
    provenance.mkdir(parents=True)
    shutil.copyfile(__file__, provenance / "build_timing_harbor.py")
    ref_path = out / "tests/reference.json"
    if args.reuse_reference:
        original = args.reuse_reference.resolve()
        previous = json.loads((original / "authoring/provenance/sources.json").read_text())
        previous_reference = original / "tests/reference.json"
        ref = json.loads(previous_reference.read_text())
        if (previous["input_sha256"] != input_hashes or ref["panel"] != panel
                or previous.get("reference_sha256", sha(previous_reference)) != sha(previous_reference)):
            raise ValueError("Previous reference does not match the declared panel and inputs")
        for name in SIMULATOR_FILES:
            if sha(original / "environment/simulator" / name) != sha(out / "environment/simulator" / name):
                raise ValueError(f"Previous reference uses a different simulator file: {name}")
        shutil.copyfile(previous_reference, ref_path)
        source = original / "authoring/provenance/reference_generator.py"
        if not source.exists():
            source = original / "authoring/provenance/build_timing_harbor.py"
        shutil.copyfile(source, provenance / "reference_generator.py")
        generator_hash = sha(provenance / "reference_generator.py")
        if previous["reference_generator_sha256"] != generator_hash:
            raise ValueError("Previous reference generator hash changed")
    else:
        save(ref_path, {"panel": panel, "rows": reference_rows(panel)})
        generator_hash = sha(Path(__file__))

    save(provenance / "sources.json", {
        "source_git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "upstream_rubric_commit": UPSTREAM, "input_sha256": input_hashes,
        "public_panel_sha256": sha(public / "panel.json"),
        "simulator_sha256": {name: sha(out / "environment/simulator" / name) for name in SIMULATOR_FILES},
        "reference_method": "Native dopri5 with upstream simglucose 0.2.11 T1DPatient.model; generated without the author solution.",
        "fixed_design_source": "Public v0.2 high-budget responsive development reference, dev-06.",
        "reference_generator_sha256": generator_hash, "reference_sha256": sha(ref_path),
        "agent_base_image": args.agent_base, "verifier_base_image": args.verifier_base,
    })
    print(out, flush=True)


if __name__ == "__main__":
    main()
