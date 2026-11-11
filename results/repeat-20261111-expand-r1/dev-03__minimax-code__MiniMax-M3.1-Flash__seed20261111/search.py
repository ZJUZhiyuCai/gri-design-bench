"""Placeholder search script (initial checkpoint)."""
import json
from gri_bench.api import load_instance, Experiment, save_design

inst = load_instance()
design = json.load(open('/work/output/design.json'))
exp = Experiment(inst)
print(exp.evaluate(design))
save_design(design)
