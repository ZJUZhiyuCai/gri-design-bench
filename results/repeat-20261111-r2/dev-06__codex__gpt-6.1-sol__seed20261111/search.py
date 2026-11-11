"""Reproduce the public-physiology search for dev-06.

Usage: python search.py all     # entire search and validation (may be slow)
       python search.py final   # evaluate the submitted design on 170 seeds
       python search.py native  # native solver on the worst observed scenario
No private seeds, patient-specific coefficients, or simulator modifications.
All candidate decisions use independent simulations from native initial states.
"""
import argparse
import json
import os
from pathlib import Path
import numpy as np
from gri_bench.api import (load_instance, Experiment, PARAMETERS, individual_design,
                           glucose_metrics, summarize, save_design)
from gri_bench.physiology import fast_trace

OUT = Path('/work/output')
LEAK = 0.5124966150526034
TRAIN_PLUS = list(range(6111006, 6111012))
BROAD_SEEDS = [6111006] + list(range(710001, 710025))
FINALIST_SEEDS = TRAIN_PLUS + list(range(710001, 710025)) + list(range(810001, 810041))
VALIDATION_SEEDS = list(range(910001, 910101))

def design(a, e=180, n=4, t=2, l=LEAK, L=4):
    return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, [a,l,e,n,t,L]))}

def evaluate(exp, d, steps=1):
    rows = []
    for name, seed, variant, p, initial, meals in exp.jobs:
        trace = fast_trace(p, initial, meals,
                           individual_design(d, exp.instance['tdi'][name]), substeps=steps)
        rows.append(dict(patient=name, seed=seed, variant=variant,
                         metrics=glucose_metrics(trace, exp.instance['warmup_minutes'])))
    return dict(**summarize(rows), rows=rows)

def record(stage, records):
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = OUT / (stage + '.json.tmp')
    temporary.write_text(json.dumps(records, indent=2, allow_nan=False) + '\n')
    os.replace(temporary, OUT / (stage + '.json'))

def sweep(stage, ins, candidates, seeds=None):
    exp = Experiment(ins, seeds=seeds)
    records = []
    for d in candidates:
        m = evaluate(exp, d)
        records.append(dict(design=d, metrics=m))
        print(stage, d['parameters'], {k:v for k,v in m.items() if k != 'rows'}, flush=True)
    record(stage, records)
    good = [r for r in records if r['metrics']['feasible']]
    return max(good, key=lambda r:r['metrics']['mean_tir']) if good else None

def submitted_design():
    # Finalists selected a=0.000340, EC50=140. Reserve 0.000003 in
    # amplitude because a single unseen unsafe trajectory zeros the score.
    return design(0.000337, 140)

def run(stage):
    ins = load_instance()
    if stage == 'screen':
        return sweep(stage, ins, [design(a) for a in [.00025,.00035,.00045,.00055,.00065,.00075]])
    if stage == 'shape':
        return sweep(stage, ins, [design(a,e) for e in [80,105,130,155,180,220,280]
                                  for a in [.00030,.00035,.00040,.000425,.00045]])
    if stage == 'robust':
        pairs = [(150,[.00034,.00036]),(170,[.00038,.00040]),(185,[.00041,.00043]),
                 (200,[.00044,.00046]),(220,[.00048,.00050]),(250,[.00052,.00054])]
        return sweep(stage, ins, [design(a,e) for e, aa in pairs for a in aa], TRAIN_PLUS)
    if stage == 'broad':
        pairs = [(100,.00026),(115,.00029),(130,.00031),(140,.00033),
                 (150,.00034),(160,.00036),(170,.00037)]
        return sweep(stage, ins, [design(a,e) for e,a in pairs], BROAD_SEEDS)
    if stage == 'finalists':
        pairs = [(130,.00032),(140,.00034),(150,.00035),(160,.00037)]
        return sweep(stage, ins, [design(a,e) for e,a in pairs], FINALIST_SEEDS)
    if stage == 'validation':
        return sweep(stage, ins, [design(.00034,140)], VALIDATION_SEEDS)
    d = submitted_design()
    save_design(d)
    if stage == 'final':
        return sweep('final_validation', ins, [d], FINALIST_SEEDS + VALIDATION_SEEDS)
    if stage == 'fine':
        exp = Experiment(ins, seeds=[6111006,6111007,910055,910074,910028])
        m = evaluate(exp, d, steps=4)
        record('fine_validation', [dict(design=d, metrics=m)])
        print({k:v for k,v in m.items() if k != 'rows'}, flush=True)
        return m
    if stage == 'native':
        from gri_bench.native import native_trace
        exp = Experiment(ins, seeds=[910055], variants=['large_dinner'])
        job = next(j for j in exp.jobs if j[0] == 'child#005')
        name, seed, variant, p, initial, meals = job
        trace, minute = native_trace(name, meals, individual_design(d, ins['tdi'][name]), ins['patient_seed'])
        m = glucose_metrics(trace, ins['warmup_minutes'], minute)
        record('native_validation', [dict(patient=name,seed=seed,variant=variant,metrics=m)])
        print(m, flush=True)
        return m
    raise ValueError(stage)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', nargs='?', default='all', choices=[
        'all','screen','shape','robust','broad','finalists','validation','final','fine','native'])
    stage = parser.parse_args().stage
    if stage == 'all':
        for phase in ['screen','shape','robust','broad','finalists','validation','final','fine','native']:
            run(phase)
    else:
        run(stage)

if __name__ == '__main__':
    main()
