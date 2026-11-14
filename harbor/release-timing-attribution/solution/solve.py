"""Author solution using the documented public simulator primitives."""

from collections import defaultdict
import json
from pathlib import Path
import statistics

import numpy as np
from simglucose.patient.t1dpatient import Action, T1DPatient

from gri_bench.api import Experiment, individual_design
from gri_bench.native import native_trace
from gri_bench.physiology import fast_trace, rhs


def prescribe(patient_name, parameters, patient_seed, meals, rates):
    patient = T1DPatient.withName(patient_name, seed=patient_seed, random_init_bg=False)
    initial = patient.state[3] / parameters.Vg

    def compiled(t, state, action, params, last_q, last_food):
        return rhs(state, action.CHO, action.insulin, parameters, last_q, last_food)

    patient.model = compiled
    patient.reset()
    minute = [initial]
    for index, meal in enumerate(meals):
        patient.step(Action(CHO=float(meal), insulin=float(rates[index // 3])))
        if not patient._odesolver.successful() or not np.isfinite(patient.state).all():
            raise RuntimeError(f"Replay failed at minute {index + 1}")
        minute.append(patient.state[3] / parameters.Vg)
    return np.asarray(minute)


def analyze(panel, method):
    instance = panel["instance"]
    rows = []
    differences = defaultdict(lambda: defaultdict(list))
    for patient, seed, variant, params, initial, meals in Experiment(instance, seeds=panel["seeds"]).jobs:
        individual = individual_design(panel["design"], instance["tdi"][patient])
        if method == "rk4":
            rates = fast_trace(params, initial, meals, individual)[:, 2]
            original = prescribe(patient, params, instance["patient_seed"], meals, rates)
        else:
            trace, original = native_trace(patient, meals, individual, instance["patient_seed"])
            rates = trace[:, 2]

        days = [rates[i:i + 480] for i in range(0, len(rates), 480)]
        if method == "wrong":
            level = np.mean(rates[480:])
            flat = np.r_[days[0], np.repeat(level, 960)]
        else:
            flat = np.r_[days[0], np.repeat(np.mean(days[1]), 480), np.repeat(np.mean(days[2]), 480)]
        shifted = np.r_[days[0], days[1][240:], days[1][:240], days[2][240:], days[2][:240]]
        original_metrics = None
        for arm, rate in (("responsive", rates), ("daily_flat", flat), ("daily_shift_12h", shifted)):
            plasma = original if arm == "responsive" else prescribe(patient, params, instance["patient_seed"], meals, rate)
            samples = plasma[instance["warmup_minutes"] + 3::3]
            metrics = {"tir": 100 * np.mean((samples >= 70) & (samples <= 180)),
                       "tbr70": 100 * np.mean(samples < 70), "tbr54": 100 * np.mean(samples < 54),
                       "minimum": float(plasma.min())}
            rows.append({"patient": patient, "seed": seed, "variant": variant, "arm": arm,
                         "rate_u_min": rate.tolist(), "daily_dose_u": (3 * rate.reshape(3, 480).sum(axis=1)).tolist(),
                         **metrics})
            if arm == "responsive":
                original_metrics = metrics
            else:
                for key, value in metrics.items():
                    differences[arm][key].append(original_metrics[key] - value)
    return {"rows": rows, "mean_responsive_minus_control": {
        arm: {metric: statistics.mean(values) for metric, values in metrics.items()}
        for arm, metrics in differences.items()
    }}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=Path("/app/public/panel.json"))
    parser.add_argument("--output", type=Path, default=Path("/app/output/results.json"))
    parser.add_argument("--method", choices=("native", "rk4", "wrong"), default="native")
    args = parser.parse_args()
    panel = json.loads(args.panel.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(analyze(panel, args.method), stream, allow_nan=False)
