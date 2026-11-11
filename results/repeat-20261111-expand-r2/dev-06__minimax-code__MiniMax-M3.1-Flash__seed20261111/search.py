"""GRI static formulation search (initial scaffold; improved in later revisions)."""
import json
import numpy as np
from gri_bench.api import load_instance, individual_design, glucose_metrics, summarize
from gri_bench.physiology import patient_parameters, meal_schedule, fast_trace

INSTANCE = load_instance()
CACHE = "/work/cache/meals_{}_{}.npy"


def meals_for(seed, variant, days=3):
    import os
    path = CACHE.format(seed, variant)
    if os.path.exists(path):
        return np.load(path)
    m = meal_schedule(seed, days, variant)
    np.save(path, m)
    return m


def evaluate(design, seeds=(6111006,), variants=("ordinary", "missed_lunch", "large_dinner")):
    rows = []
    for name in INSTANCE["patients"]:
        p, initial = patient_parameters(name)
        for seed in seeds:
            for variant in variants:
                meals = meals_for(seed, variant)
                scale = p.BW / INSTANCE["reference_weight_kg"]
                trace = fast_trace(p, initial, meals * scale, individual_design(design, INSTANCE["tdi"][name]))
                rows.append({"patient": name, "seed": seed, "variant": variant,
                             "metrics": glucose_metrics(trace, INSTANCE["warmup_minutes"])})
    return {**summarize(rows), "rows": rows}


if __name__ == "__main__":
    design = json.load(open("/work/output/design.json"))
    m = evaluate(design)
    print(json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=2))
    for r in m["rows"]:
        print(r["patient"], r["seed"], r["variant"], {k: round(v, 2) for k, v in r["metrics"].items()})
