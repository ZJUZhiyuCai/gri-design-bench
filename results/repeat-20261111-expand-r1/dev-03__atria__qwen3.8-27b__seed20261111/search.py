"""Reproducible search for the GRI static formulation (dev-03).

Placeholder; refined in later steps.
"""
import json
from gri_bench.api import load_instance, Experiment, save_design

def main():
    instance = load_instance()
    exp = Experiment(instance)
    design = json.load(open('/work/output/design.json'))
    print(exp.evaluate(design))

if __name__ == '__main__':
    main()
