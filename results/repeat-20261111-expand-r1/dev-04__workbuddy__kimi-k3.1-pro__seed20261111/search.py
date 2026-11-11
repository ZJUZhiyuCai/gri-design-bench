"""Deterministic refinement search used for the submitted dev-04 design.

Requires PYTHONPATH=/opt/gri_bench.  The search uses only public training
scenarios and explicitly chosen, disjoint meal seeds for validation.  Candidate
writes are atomic through gri_bench.api.save_design.  Earlier broad screening
varied amplitude, EC50, Hill exponent, and filter time; this script reproduces
the final local refinement and validation selection.
"""
import json
from pathlib import Path
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

OUT = Path('/work/output')
INSTANCE = load_instance()
LEAK = INSTANCE['bounds']['relative_leak'][0]
LOAD = INSTANCE['bounds']['theta_L'][1]

# (theta_a, EC50, Hill n, tau); leak and load are fixed at their favorable
# bounds.  These points bracket the high-TIR region found by coarse screening.
CANDIDATES = [
    (0.00085, 250., 2.5, 2.), (0.00090, 270., 2.5, 2.),
    (0.00100, 300., 2.5, 2.), (0.00110, 330., 2.5, 2.),
    (0.00120, 360., 2.5, 2.), (0.00080, 230., 2.5, 0.05),
    (0.00080, 230., 2.5, 5.), (0.00080, 230., 2.5, 10.),
    (0.00080, 230., 2.0, 2.), (0.00090, 260., 3.0, 2.),
    (0.00100, 290., 3.0, 2.), (0.00110, 320., 3.0, 2.),
]

def make_design(c):
    a, ec50, hill_n, tau = c
    values = (a, LEAK, ec50, hill_n, tau, LOAD)
    return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, values))}

def compact(r):
    keys = ('mean_tir', 'max_trajectory_tbr70', 'max_trajectory_tbr54',
            'minimum_glucose', 'feasible')
    return {k: r[k] for k in keys}

def training_score(r):
    # Smooth ranking during screening; final feasibility is never inferred
    # from this score alone.
    return (r['mean_tir']
            - 30. * max(0., r['max_trajectory_tbr70'] - 3.)
            - 200. * max(0., r['max_trajectory_tbr54'] - .5)
            - 3. * max(0., 55. - r['minimum_glucose']))

def main():
    train = Experiment(INSTANCE)
    ranked = []
    for c in CANDIDATES:
        r = train.evaluate(make_design(c))
        ranked.append((training_score(r), c, compact(r)))
        print('TRAIN', c, compact(r), flush=True)
    ranked.sort(key=lambda row: row[0], reverse=True)

    # These are scenario seeds, not simulator patient random seeds.  They are
    # disjoint from the instance's training seed 6111004.
    validation = Experiment(INSTANCE, seeds=[8111004, 9111004, 10111004])
    validated = []
    for _, c, training_metrics in ranked[:5]:
        r = validation.evaluate(make_design(c))
        row = {'candidate': c, 'training': training_metrics,
               'validation': compact(r)}
        validated.append(row)
        print('VALIDATE', row, flush=True)

    # Require zero observed TBR, a >=70 mg/dL full-horizon minimum, and
    # native-threshold feasibility on every validation trajectory.  Maximize
    # fresh-scenario TIR only among those candidates.
    eligible = [row for row in validated
                if row['validation']['feasible']
                and row['validation']['max_trajectory_tbr70'] == 0.
                and row['validation']['max_trajectory_tbr54'] == 0.
                and row['validation']['minimum_glucose'] >= 70.]
    if not eligible:
        raise RuntimeError('No candidate passed the conservative safety screen')
    winner = max(eligible, key=lambda row: row['validation']['mean_tir'])
    design = make_design(winner['candidate'])
    save_design(design)
    (OUT / 'search_results_reproduced.json').write_text(
        json.dumps({'ranked_training': ranked, 'validated': validated,
                    'selected': winner}, indent=2) + '\n')
    print('SELECTED', json.dumps(design), flush=True)

if __name__ == '__main__':
    main()
