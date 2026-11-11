"""Reproducible search for the GRI static design (instance dev-01).

Everything is shared: an amplitude per unit native TDI, a relative leak, and a Hill
response on the filtered interstitial glucose.  The finite reservoir
(theta_L * TDI) never refills, so the design must spread its insulin over the whole
three days instead of exhausting the reservoir early.  Search: log-uniform random
search over a physiologically motivated sub-box, then shrinking-neighbourhood local
search, then a fresh-seed robustness re-check; the best safe candidate is saved.
"""
import json, time, numpy as np
from gri_bench.api import load_instance, Experiment, save_design, validate_design

inst = load_instance(); B = inst['bounds']
RNG = np.random.default_rng(20260101)
TIME_BUDGET = 18.0

# log/lin search ranges (always inside instance bounds)
R = {'theta_a': 'log', 'relative_leak': 'log', 'ec50_mg_dl': 'log',
     'hill_n': 'log', 'tau_min': 'log', 'theta_L': 'lin'}
LO = {'theta_a': 3e-5, 'relative_leak': 0.5125, 'ec50_mg_dl': 80., 'hill_n': 1.0,
      'tau_min': 1.0, 'theta_L': 1.0}
HI = {'theta_a': 1.5e-3, 'relative_leak': 5.5, 'ec50_mg_dl': 500., 'hill_n': 16.,
      'tau_min': 20., 'theta_L': 4.0}
KEYS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')

def params(u):
    p = {}
    for k, x in zip(KEYS, u):
        if R[k] == 'log':
            p[k] = float(np.exp(np.log(LO[k]) + x*(np.log(HI[k])-np.log(LO[k]))))
        else:
            p[k] = float(LO[k] + x*(HI[k]-LO[k]))
        lo, hi = B[k]
        p[k] = float(min(hi, max(lo, p[k])))          # guard against fp overshoot
    return p

def design_of(u):
    return {'mode': 'responsive', 'parameters': params(u)}

def score(m):
    t70, t54, gmin, tir = (m['max_trajectory_tbr70'], m['max_trajectory_tbr54'],
                           m['minimum_glucose'], m['mean_tir'])
    viol = max(0., t70-3.5) + 2.*max(0., t54-0.7) + 0.5*max(0., 46. - gmin)
    return tir - 500.*viol

t0 = time.process_time(); ex = Experiment(inst); tab = []
def offer(u, ex=ex, tab=tab):
    u = np.clip(np.asarray(u, float), 0, 1)
    s = score(ex.evaluate(design_of(u)))
    tab.append((s, u)); return s

# stage 1: random search
for _ in range(160):
    if time.process_time()-t0 > 0.55*TIME_BUDGET: break
    offer(RNG.random(6))
tab.sort(key=lambda z: -z[0]); bs, bu = tab[0]
print('stage1', round(bs, 2), {k: round(v, 4) for k, v in params(bu).items()})

# stage 2: shrinking neighbourhood, keep best
for sig in (0.25, 0.15, 0.09, 0.05, 0.03, 0.015):
    for _ in range(12):
        if time.process_time()-t0 > 0.85*TIME_BUDGET: break
        s = offer(bu + RNG.normal(0, sig, 6))
        if s > bs:
            bs, bu = s, np.clip(bu + RNG.normal(0, sig, 6), 0, 1)
            bu = tab[-1][1]
tab.sort(key=lambda z: -z[0]); bs, bu = tab[0]
print('stage2', round(bs, 2), {k: round(v, 4) for k, v in params(bu).items()})

# stage 3: fresh meal seeds -> prefer designs that stay safe off-training
extra = Experiment(inst, seeds=[6111001, 7770001, 424242], variants=inst['variants'])
seen, cands = set(), []
for s, u in tab:
    key = tuple(np.round(u, 8))
    if key in seen: continue
    seen.add(key); cands.append(u)
    if len(cands) >= 8: break
rob = []
for u in cands:
    if time.process_time()-t0 > 0.95*TIME_BUDGET: break
    rob.append((score(extra.evaluate(design_of(u))), u))
rob.sort(key=lambda z: -z[0])
print('robust', [(round(s, 2), {k: round(v, 5) for k, v in params(u).items()}) for s, u in rob[:3]])
final = design_of(rob[0][1]) if rob and rob[0][0] >= bs - 1.0 else design_of(bu)
validate_design(final, inst)
m = ex.evaluate(final)
print('FINAL', json.dumps(final))
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'rows'})
for r in m['rows']:
    print(' ', r['patient'], r['variant'], {k: round(v, 1) for k, v in r['metrics'].items()})
save_design(final)
print('cpu', round(time.process_time()-t0, 2))
