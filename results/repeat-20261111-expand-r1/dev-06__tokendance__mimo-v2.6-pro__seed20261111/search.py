# GRI static formulation search (placeholder -> will be improved)
import json
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

instance = load_instance()
exp = Experiment(instance)
design = {"mode":"responsive","parameters":{"theta_a":0.0003,"relative_leak":1.5,
          "ec50_mg_dl":200.0,"hill_n":2.0,"tau_min":10.0,"theta_L":1.0}}
print(exp.evaluate(design))
