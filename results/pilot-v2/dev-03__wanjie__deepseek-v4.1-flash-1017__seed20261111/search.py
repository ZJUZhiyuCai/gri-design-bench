"""Reproducible search for the GRI static formulation (dev-03, children 001-003).

Model facts that drive the design:
  * rate = theta_a*TDI*(relative_leak + Hill(filtered glucose)) with the Hill term
    -> 1 when plasma glucose is well ABOVE ec50 (proper glucose-responsive direction)
    -> 0 when glucose is well below ec50;
  * total insulin over the 3 days is bounded by the finite reservoir theta_L*TDI
    (no refill), so theta_L must be large enough for the cohort's daily need
    (17.5 U/day here) or glucose runs away after the reservoir empties;
  * scoring: mean TIR minus hard hypo penalties (margins kept, since unseen meal
    seeds must also satisfy TBR70<=4%, TBR54<=1%, min glucose>=40).

Pipeline: coarse amplitude x relative_leak grid at theta_L=4 -> shape (ec50, hill_n)
refinement -> filter time-constant refinement -> final ranking and validation of
the leaders on two extra meal seeds (fresh RandomScenario draws).
"""
import json, time, numpy as np
from gri_bench.api import load_instance, Experiment, save_design, PARAMETERS

T0 = time.time()
inst = load_instance()
exp = Experiment(inst)                                  # training seed 6111003 x 3 variants
exp2 = Experiment(inst, seeds=[6111004, 6111005])       # robustness check only
CACHE = {}

def design(a, leak, ec50, n, tau, L):
    v = [float(x) for x in (a, leak, ec50, n, tau, L)]
    return {"mode": "responsive", "parameters": dict(zip(PARAMETERS, v))}

def score(m):
    return (m['mean_tir'] - 8*max(0., m['max_trajectory_tbr70'] - 1.0)
            - 60*max(0., m['max_trajectory_tbr54'] - 0.1)
            - 2*max(0., 65. - m['minimum_glucose']))

LOG = []
def trial(a, leak, ec50, n, tau, L):
    d = design(a, leak, ec50, n, tau, L)
    key = json.dumps(d, sort_keys=True)
    if key not in CACHE:
        CACHE[key] = exp.evaluate(d)
    m = CACHE[key]
    s = score(m)
    LOG.append(((a, leak, ec50, n, tau, L), s, m['mean_tir'], m['max_trajectory_tbr70'],
                m['max_trajectory_tbr54'], m['minimum_glucose']))
    return s

def top(k):
    return [r[0] for r in sorted(LOG, key=lambda r: -r[1])[:k]]

# Phase 1: coarse amplitude x leak (theta_L=4 keeps the reservoir non-limiting)
for a in [0.00040, 0.00055, 0.00070, 0.00090]:
    for leak in [0.5125, 0.65, 0.85, 1.10]:
        trial(a, leak, 200., 3.0, 10., 4.0)
# Phase 2: glucose-response shape at the best basal settings
for (a, leak, _, _, _, _) in top(3):
    for ec50 in [140., 200., 280.]:
        for n in [2.0, 4.0]:
            trial(a, leak, ec50, n, 10., 4.0)
# Phase 3: filter time constant and reservoir size
for (a, leak, ec50, n, _, _) in top(3):
    for tau in [4., 10., 20.]:
        trial(a, leak, ec50, n, tau, 4.0)
for (a, leak, ec50, n, tau, _) in top(2):
    for L in [3.0, 3.6]:
        trial(a, leak, ec50, n, tau, L)

# Phase 4: validate leaders on unseen meal seeds before choosing
final = None
for params in top(4):
    d = design(*params)
    m2 = exp2.evaluate(d)
    rob = score(m2)
    print(f"cand {params} train={score(CACHE[json.dumps(d, sort_keys=True)]):.2f} "
          f"fresh={rob:.2f} tir2={m2['mean_tir']:.1f} t70_2={m2['max_trajectory_tbr70']:.2f} "
          f"t54_2={m2['max_trajectory_tbr54']:.2f} min2={m2['minimum_glucose']:.1f}", flush=True)
    if final is None or rob > final[0]:
        final = (rob, d, m2)
save_design(final[1])
print("chosen", final[1])
print("train", {k: v for k, v in exp.evaluate(final[1]).items() if k != 'rows'})
print("fresh", {k: v for k, v in final[2].items() if k != 'rows'})
print("evals", len(CACHE), "cpu", round(time.time() - T0, 1))
