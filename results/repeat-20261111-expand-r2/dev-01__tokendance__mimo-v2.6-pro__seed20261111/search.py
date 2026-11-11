#!/usr/bin/env python3
"""Initial baseline search (placeholder) - will be replaced."""
from gri_bench.api import load_instance, Experiment, save_design
import json

def main():
    instance = load_instance()
    experiment = Experiment(instance)
    design = {"mode": "constant", "parameters": {"theta_c": 0.0002, "theta_L": 1.0}}
    print(experiment.evaluate(design))
    save_design(design)

if __name__ == "__main__":
    main()
