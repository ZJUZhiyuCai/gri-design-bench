"""Reproducible search for the GRI static formulation (initial version).

Objective: maximize mean post-warmup TIR (plasma glucose in [70,180] mg/dL)
subject to hard safety gates: per-trajectory TBR70 <= 4%, TBR54 <= 1%,
and minimum plasma glucose over the full 3-day horizon >= 40 mg/dL.
"""
import json, itertools, numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

INSTANCE = load_instance()
BOUNDS = INSTANCE['bounds']

def evaluate(design, seeds=None):
    exp = Experiment(INSTANCE, seeds=seeds)
    return exp.evaluate(design)

def score(design, seeds=None):
    m = evaluate(design, seeds)
    return m['safe_tir'], m

if __name__ == '__main__':
    print(json.dumps(evaluate(json.loads(open('/work/output/design.json').read()))['mean_tir']))
