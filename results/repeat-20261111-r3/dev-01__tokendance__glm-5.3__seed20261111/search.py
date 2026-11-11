#!/usr/bin/env python3
"""Reproducible search for GRI static formulation (instance dev-01).

Staged pattern search over the responsive vector with the fast RK4 evaluator,
checkpointing the best design atomically after every accepted improvement.
Usage: python search.py [--cap 13.0] (CPU seconds for search inside process)
"""
import argparse, json, os, tempfile, time
import numpy as np

T0 = time.process_time()
from gri_bench.physiology import patient_parameters, meal_schedule, fast_trace

ap = argparse.ArgumentParser()
ap.add_argument('--cap', type=float, default=13.0)
ap.add_argument('--out', default='/work/output/design.json')
A = ap.parse_args()
inst = json.load(open('/task/instance.json'))
KEYS = ['theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L']
LO = np.array([inst['bounds'][k][0] for k in KEYS]); HI = np.array([inst['bounds'][k][1] for k in KEYS])
SEEDS = [6111001, 777, 31337]
VARS = ['ordinary', 'missed_lunch', 'large_dinner']
WARM = inst['warmup_minutes'] // 3
REF = inst['reference_weight_kg']; TDI = inst['tdi']

def atomic(design):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(A.out), suffix='.tmp')
    with os.fdopen(fd, 'w') as f: json.dump(design, f)
    os.replace(tmp, A.out)

sched = {(s, v): meal_schedule(s, 3, v) for s in SEEDS for v in VARS}
PAT = [(n, *patient_parameters(n)) for n in inst['patients']]

def vec(p):
    return np.array([p['theta_a']*TDI[n], p['relative_leak'], p['ec50_mg_dl'],
                     p['hill_n'], p['tau_min'], p['theta_L']*TDI[n]])

def metrics(tr):
    bg = tr[WARM:, 0]
    return (100*np.mean((bg >= 70) & (bg <= 180)), 100*np.mean(bg < 70),
            100*np.mean(bg < 54), float(tr[:, 4].min()))

def evaluate(prm, seeds, sub=4):
    tirs, b70, b54, gmin = [], 0., 0., 1e9
    for n, p, init in PAT:
        d = [prm['theta_a']*TDI[n], prm['relative_leak'], prm['ec50_mg_dl'], prm['hill_n'], prm['tau_min'], prm['theta_L']*TDI[n]]
        for s in seeds:
            for v in VARS:
                tr = fast_trace(p, init, sched[(s, v)]*p.BW/REF, d, substeps=sub)
                t, x, y, g = metrics(tr)
                tirs.append(t); b70 = max(b70, x); b54 = max(b54, y); gmin = min(gmin, g)
    mt = float(np.mean(tirs))
    pen = 300*max(0., b70-3.0) + 500*max(0., b54-0.7) + 15*max(0., 46.0-gmin)
    return {'score': mt-pen, 'mean_tir': mt, 'tbr70': b70, 'tbr54': b54, 'min': gmin}

def save(prm, m):
    atomic({'mode': 'responsive', 'parameters': {k: float(np.clip(prm[k], LO[i], HI[i])) for i, k in enumerate(KEYS)}})
    return m

budget = A.cap
x = {'theta_a': 3.5e-4, 'relative_leak': 1.2, 'ec50_mg_dl': 140., 'hill_n': 4., 'tau_min': 12., 'theta_L': 3.0}
best = evaluate(x, [SEEDS[0]], sub=2); save(x, best)
print('x0', {k: round(v, 5) for k, v in x.items()}, {k: round(v, 2) for k, v in best.items()}, 'cpu', round(time.process_time()-T0, 2), flush=True)
rng = np.random.default_rng(7)
step = np.array([.3, .3, .25, .4, .4, .2])
while time.process_time()-T0 < budget*0.72:
    improved = False
    for i, k in enumerate(KEYS):
        cands = []
        for sg in (1., -1.):
            y = dict(x); y[k] = float(np.clip(x[k]*(1+sg*step[i]), LO[i], HI[i]))
            if y[k] != x[k]: cands.append(y)
        scored = [(evaluate(y, [SEEDS[0]], sub=2), y) for y in cands]
        for m, y in scored:
            if m['score'] > best['score']+1e-9 and not improved:
                x, best, improved = y, m, True; save(y, m)
        if improved or time.process_time()-T0 > budget*0.72: break
    if not improved:
        step *= .55
        if step.max() < .03: break
# full validation of current best
full = evaluate(x, SEEDS, sub=4)
print('full(seed0 cand)', {k: round(v, 2) for k, v in full.items()}, 'cpu', round(time.process_time()-T0, 2), flush=True)
cands = [x]
for _ in range(6):
    y = {k: float(np.clip(x[k]*np.exp(rng.normal(0, .18)), LO[i], HI[i])) for i, k in enumerate(KEYS)}
    cands.append(y)
bestf, bx = full, x
for y in cands:
    if time.process_time()-T0 > budget: break
    m = evaluate(y, SEEDS, sub=4)
    print('  cand', {k: round(v, 5) for k, v in y.items()}, {k: round(v, 2) for k, v in m.items()}, flush=True)
    if m['score'] > bestf['score']: bestf, bx = m, y
save(bx, bestf)
print('FINAL', {k: round(v, 5) for k, v in bx.items()}, {k: round(v, 2) for k, v in bestf.items()}, 'cpu', round(time.process_time()-T0, 2), flush=True)
