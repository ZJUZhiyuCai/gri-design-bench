# Initial search script (to be improved)
import json
from gri_bench.api import load_instance, Experiment, save_design

instance = load_instance()
exp = Experiment(instance)
design = json.load(open("/work/output/design.json"))
print(exp.evaluate(design))
