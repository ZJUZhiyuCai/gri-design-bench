"""Frozen, equal-CPU baseline recipes. Invoked inside the isolated task container."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from scipy.optimize import differential_evolution
from scipy.stats import qmc
from gri_bench.api import PARAMETERS, Experiment, load_instance, save_design


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=['constant_grid', 'sobol', 'differential_evolution'], required=True)
    parser.add_argument('--seed', type=int, default=20261111)
    parser.add_argument('--seconds', type=float, default=28.)
    args = parser.parse_args()
    instance = load_instance(); out = Path('/work/output'); out.mkdir(exist_ok=True)
    # process_time includes this interpreter's imports and setup. The outer
    # runner independently enforces aggregate cgroup CPU for all processes.
    deadline = args.seconds
    (out/'search.py').write_text(Path(__file__).read_text())
    (out/'rationale.md').write_text(f'Frozen {args.method} baseline, seed {args.seed}. Reproduce: python search.py --method {args.method} --seed {args.seed} --seconds {args.seconds}. Robust training targets: TBR70<=3%, TBR54<=0.5%, minimum>=45 mg/dL. Select feasible best TIR; fixed tie order. Native heldout verification determines the actual score.\n')
    zero = {'mode': 'constant', 'parameters': {'theta_c': 0., 'theta_L': instance['bounds']['theta_L'][1]}}
    save_design(zero)
    experiment = Experiment(instance)
    best_key = (-1, -1e100); history = []

    def candidate(design):
        nonlocal best_key
        if time.process_time() >= deadline:
            raise TimeoutError('Search CPU allocation reached')
        try:
            m = experiment.evaluate(design)
            violation = (max(0., m['max_trajectory_tbr70']-3.) +
                         4*max(0., m['max_trajectory_tbr54']-.5) +
                         max(0., 45.-m['minimum_glucose'])/5)
            loss = -m['mean_tir'] if violation == 0 else 1000.+100.*violation-m['mean_tir']
            key = (int(violation == 0), -loss)
            history.append({'candidate': design, 'loss': loss, 'mean_tir': m['mean_tir'],
                            'training_feasible': m['feasible'], 'robust_violation': violation})
            if key > best_key:
                best_key = key; save_design(design)
                (out/'training.json').write_text(json.dumps({k:v for k,v in m.items() if k != 'rows'}))
        except (ValueError, FloatingPointError):
            loss = 1e9
        return loss

    bounds = instance['bounds']
    low = np.array([max(bounds[k][0], 1e-6) for k in PARAMETERS])
    high = np.array([bounds[k][1] for k in PARAMETERS])
    def unpack(unit):
        values = np.clip(np.exp(np.log(low)+np.asarray(unit)*np.log(high/low)), low, high)
        return {'mode':'responsive', 'parameters':dict(zip(PARAMETERS, map(float, values)))}
    try:
        candidate(zero)
        if args.method == 'constant_grid':
            # Log grid resolves physiologically plausible rates without silently
            # narrowing the registered dose range. Refine deterministically.
            for count in [128, 256, 512, 1024, 2048]:
                for theta in np.geomspace(1e-6, instance['constant_theta_c_bounds'][1], count):
                    candidate({'mode':'constant', 'parameters':{'theta_c':float(theta), 'theta_L':bounds['theta_L'][1]}})
        elif args.method == 'sobol':
            samples = qmc.Sobol(6, scramble=True, seed=args.seed).random_base2(16)
            for unit in samples:
                candidate(unpack(unit))
        else:
            # Seeded differential evolution over all six dimensions, logarithmic
            # scaling, no local-gradient assumptions about threshold metrics.
            differential_evolution(lambda unit: candidate(unpack(unit)), [(0,1)]*6,
                                   seed=args.seed, popsize=8, maxiter=100000,
                                   tol=0, atol=0, polish=False, updating='immediate',
                                   init='sobol', workers=1)
    except TimeoutError:
        pass
    (out/'search_log.json').write_text(json.dumps({'method':args.method, 'seed':args.seed,
                'evaluations':experiment.evaluations, 'process_cpu_seconds':time.process_time(), 'history':history}))
    print(json.dumps({'method':args.method,'evaluations':experiment.evaluations,
                     'process_cpu_seconds':time.process_time(),'best_key':best_key}), flush=True)


if __name__ == '__main__':
    main()
