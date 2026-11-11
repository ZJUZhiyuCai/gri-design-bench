"""Deterministic bounded differential-evolution search for the dev-02 GRI design.
Run from /work/output. Candidates are checkpointed atomically only when their
training safe-TIR improves. Final selection should also be checked on new seeds.
"""
import json
import numpy as np
from scipy.optimize import differential_evolution
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

instance = load_instance()
experiment = Experiment(instance)
# Work in scales that make the wide multiplicative bounds search efficiently.
LO = np.array([np.log(2e-5), .5124966150526034, np.log(59.26305046791457),
               np.log(.5880395112623367), np.log(.05), .4])
HI = np.array([np.log(.007), 5.518918645844859, np.log(816.1143093473472),
               np.log(24.), np.log(20.), 4.])

def unpack(z):
    z = LO + np.asarray(z) * (HI-LO)
    return np.array([np.exp(z[0]), z[1], np.exp(z[2]), np.exp(z[3]),
                     np.exp(z[4]), z[5]])

def design(z):
    return {'mode':'responsive', 'parameters':dict(zip(PARAMETERS, map(float, unpack(z))))}

history = []
best = [-1.]
def objective(z):
    d = design(z)
    m = experiment.evaluate(d)
    # Preserve all candidates for later independent-seed robustness screening.
    history.append((m['safe_tir'], m['mean_tir'], m['max_trajectory_tbr70'],
                    m['max_trajectory_tbr54'], m['minimum_glucose'], z.copy()))
    if m['safe_tir'] > best[0]:
        best[0] = m['safe_tir']
        save_design(d)
        print('checkpoint', best[0], d, flush=True)
    # A smooth-ish merit for unsafe points guides evolution toward feasibility.
    if not m['feasible']:
        return 100. + 20.*max(0.,m['max_trajectory_tbr70']-4.) + \
               100.*max(0.,m['max_trajectory_tbr54']-1.) + \
               max(0.,40.-m['minimum_glucose']) - .01*m['mean_tir']
    return -m['mean_tir']

if __name__ == '__main__':
    result = differential_evolution(objective, [(0.,1.)]*6, seed=2026111101,
                                    popsize=3, maxiter=3, polish=False,
                                    updating='immediate', workers=1)
    print('BEST', result.fun, design(result.x), 'evaluations', len(history))
    np.save('/work/output/search_history.npy',
            np.array([np.r_[h[:5],h[5]] for h in history]))
