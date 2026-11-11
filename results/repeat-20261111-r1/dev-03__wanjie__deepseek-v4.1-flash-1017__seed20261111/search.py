"""Reproducible search stub (updated later)."""
from gri_bench.api import load_instance, Experiment, save_design
instance = load_instance()
exp = Experiment(instance)
design = {"mode": "responsive", "parameters": {"theta_a": 0.0002, "relative_leak": 1.5,
          "ec50_mg_dl": 200.0, "hill_n": 2.0, "tau_min": 10.0, "theta_L": 1.0}}
print(exp.evaluate(design))
save_design(design)
