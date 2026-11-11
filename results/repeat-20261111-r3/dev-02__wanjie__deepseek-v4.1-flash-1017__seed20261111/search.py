"""Reproducible search for GRI static formulation design (instance dev-02).

Usage: python search.py            # re-runs staged search, prints ranking, best design
Method
------
Stage 1: constant-rate reference sweep -> establishes the useful basal band
         (theta_c*TDI ~ 0.0005*TDI U/min; 0.00055+ is hypoglycemic).
Stage 2: broad log/uniform random search over the 6 responsive parameters
         using the cached Experiment (training seed x 3 variants).
Stage 3: multiplicative hill-climb refinement of the best feasible candidates.
Stage 4: ROBUSTNESS GATE on fresh meal seeds. The training-seed optimum
         (TIR 84, min 71) failed here (TBR70 = 9.3 % on one trajectory), so
         candidates are ranked on the max-trajectory TBR gate over several
         independent seeds, never on mean TIR alone.
Stage 5: conservative candidates near the constant-basal band with a mild,
         smooth Hill gain (low sensitivity, moderate leak) -> the submitted
         design: 3 seeds, TIR 70.0, TBR70 = 0, min glucose 74.3 (fast RK4).
Every coefficient is cohort-shared; nothing is fitted per patient.
"""
import json, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

inst = load_instance(); B = inst['bounds']
LO = np.array([1e-5, B['relative_leak'][0], B['ec50_mg_dl'][0], B['hill_n'][0], B['tau_min'][0], B['theta_L'][0]])
HI = np.array([B['theta_a'][1], B['relative_leak'][1], B['ec50_mg_dl'][1], B['hill_n'][1], B['tau_min'][1], B['theta_L'][1]])
train = Experiment(inst)
robust = Experiment(inst, seeds=[6111002, 2024, 555])
def mk(p): return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, p)))}
def gate(m):  # hard safety gate: any trajectory/dose violation -> unusable
    bad = max(0., m['max_trajectory_tbr70'] - 4.) + 10 * max(0., m['max_trajectory_tbr54'] - 1.) + max(0., 40. - m['minimum_glucose'])
    return (m['mean_tir'] if bad == 0 else -1e3 - bad)

# Stage 1: constant reference band
for c in [0.0004, 0.0005, 0.00055, 0.0006]:
    m = train.evaluate({'mode': 'constant', 'parameters': {'theta_c': c, 'theta_L': 4.0}})
    print('const %.5f tir=%.1f min=%.1f gate=%.1f' % (c, m['mean_tir'], m['minimum_glucose'], gate(m)))

# Stage 2/3: random search + hill-climb on the training scenarios
rng = np.random.default_rng(1); pool = []
def push(p, m, key=None):
    pool.append((gate(m) if key is None else key, list(map(float, p)), m['mean_tir'], m['minimum_glucose'], m['max_trajectory_tbr70']))
t0 = time.time()
while time.time() - t0 < 9:
    p = [10 ** rng.uniform(-4.3, -3.0), rng.uniform(0.51, 3.0), rng.uniform(80, 400), rng.uniform(0.8, 8), 10 ** rng.uniform(-0.3, 1.3), rng.uniform(1.0, 4.0)]
    push(p, train.evaluate(mk(p)))
pool.sort(key=lambda r: -r[0])
sc = np.array([0.15, 0.4, 0.5, 0.6, 0.8, 0.3]); t0 = time.time()
while time.time() - t0 < 6:
    b = np.array(pool[rng.integers(0, min(4, len(pool)))][1])
    q = np.clip(b * (1 + sc * rng.normal(size=6)), LO, HI); q[0] = max(q[0], 1e-5)
    push(q, train.evaluate(mk(q)))

# Stage 4/5: robustness gate on fresh seeds for the leading candidates plus the
#        deliberately de-tuned, low-sensitivity family that we submit.
cands = [r[1] for r in pool[:6]] + [
    [0.00028, 1.15, 135.0, 2.5, 6.0, 3.8],
    [0.00030, 1.00, 150.0, 3.5, 8.0, 3.9],
]
final = []
for p in cands:
    m = robust.evaluate(mk(p))
    final.append((gate(m), m['mean_tir'], m['maximum_dose_violation'] if 'maximum_dose_violation' in m else 0., m['minimum_glucose'], m['max_trajectory_tbr70'], list(map(float, p))))
    print('ROBUST tir=%.1f min=%.1f t70=%.1f p=%s' % (m['mean_tir'], m['minimum_glucose'], m['max_trajectory_tbr70'], np.round(p, 6)))
final.sort(key=lambda r: -r[0])
best = final[0]
print('BEST', best)
save_design(mk(best[5]))
