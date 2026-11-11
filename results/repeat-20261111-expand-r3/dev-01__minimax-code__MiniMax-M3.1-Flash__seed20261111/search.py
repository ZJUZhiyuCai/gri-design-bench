"""Initial placeholder search script (to be replaced)."""
import json
from gri_bench.api import load_instance, Experiment

instance = load_instance()
experiment = Experiment(instance)
design = json.load(open('/work/output/design.json'))
print(experiment.evaluate(design))
