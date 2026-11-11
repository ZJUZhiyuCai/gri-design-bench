"""Reproducible parameter search for the GRI static formulation (dev-04).

Two stages, both driven through the public fast-RK4 API:
  stage 1 - seeded log-uniform random search on the training scenario set;
  stage 2 - coordinate/pattern refinement of the best candidates plus
            multi-seed validation (fresh meal seeds) to avoid overfitting.
Objective  = mean post-warmup TIR with hard-margin penalties for the
             TBR70 / TBR54 / nadir<40 safety rules.
"""
import json, os, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

INST = load_instance()
B = INST['bounds']
LO = np.array([B[k][0] for k in PARAMETERS]); HI = np.array([B[k][1] for k in PARAMETERS])
LOG = np.array([True, False, True, True, True, False])   # search in log space?

def design(x):
    p = {k: float(np.clip(v, LO[i], HI[i])) for i, (k, v) in enumerate(zip(PARAMETERS, np.maximum(x, LOW)))}
    return {'mode': 'responsive', 'parameters': p}

def score(m):
    pen = (10*max(0.0, m['max_trajectory_tbr70'] - 4.0)
           + 30*max(0.0, m['max_trajectory_tbr54'] - 1.0)
           + 10*max(0.0, 40.0 - m['minimum_glucose']))
    return m['mean_tir'] - pen

def sample(rng):
    u = rng.random(len(PARAMETERS))
    lo = np.log(LO) if True else LO
    v = np.exp(np.log(LO) + u*(np.log(HI) - np.log(LO)))
    v[1] = LO[1] + u[1]*(HI[1]-LO[1])          # relative_leak: linear
    v[5] = LO[5] + u[5]*(HI[5]-LO[5])          # theta_L: linear
    v[0] = np.exp(np.log(1e-4) + u[0]*(np.log(HI[0]) - np.log(1e-4)))
    return v

def main():
    t0 = time.time()
    ex = Experiment(INST)
    rng = np.random.default_rng(20261111)
    results = []
    N = int(os.environ.get('N1', 140))
    for _ in range(N):
        x = sample(rng); d = design(x); m = ex.evaluate(d)
        results.append((score(m), x.tolist(), m['mean_tir']))
    results.sort(key=lambda r: -r[0])
    print('stage1 %.1fs  best=' % (time.time()-t0), [(round(s,2), round(t,1)) for s, _, t in results[:6]])
    print('bounds-ok', all(LO[i] <= v <= HI[i] for _, v, _ in results for i, v in enumerate(v)))
    for s, v, t in results[:4]:
        print(json.dumps({k: round(x, 6) for k, x in zip(PARAMETERS, v)}))
    np.save('/tmp/stage1.npy', np.array([r[1] for r in results]))
    with open('/tmp/stage1.json', 'w') as f:
        json.dump([{'score': s, 'x': v, 'tir': t} for s, v, t in results[:10]], f)
    print('cpu', round(time.process_time(), 2))

def _unused():
    main()

# ---------------- stage 2: pattern refinement + fresh-seed validation ---------
LOW = np.maximum(LO, 1e-5)   # theta_a has a zero lower bound; use a positive floor

def to_u(v):
    u = np.empty(6)
    for i in range(6):
        if i in (1, 5):
            u[i] = (v[i]-LO[i])/(HI[i]-LO[i])
        else:
            u[i] = (np.log(max(v[i], LOW[i]))-np.log(LOW[i]))/(np.log(HI[i])-np.log(LOW[i]))
    return np.clip(u, 0., 1.)

def to_v(u):
    u = np.clip(u, 0., 1.); v = np.empty(6)
    for i in range(6):
        v[i] = LO[i] + u[i]*(HI[i]-LO[i]) if i in (1, 5) else np.exp(np.log(LOW[i]) + u[i]*(np.log(HI[i])-np.log(LOW[i])))
    return v

def refine(ex, u0, sweeps=3, step=0.25, sc=score):
    u = to_u(np.asarray(u0)); best = sc(ex.evaluate(design(to_v(u))))
    for _ in range(sweeps):
        improved = False
        for i in range(6):
            for sgn in (1., -1.):
                uu = u.copy(); uu[i] = np.clip(u[i]+sgn*step, 0., 1.)
                s = sc(ex.evaluate(design(to_v(uu))))
                if s > best + 1e-9:
                    best, u, improved = s, uu, True
        if not improved:
            step *= 0.5
    return best, u

def stage2(nstart=3):
    ex = Experiment(INST)
    top = json.load(open('/tmp/stage1.json'))[:nstart]
    cands = []
    for rec in top:
        s, u = refine(ex, rec['x'])
        cands.append((s, to_v(u).tolist()))
        print('refined', round(s, 2), json.dumps({k: round(x, 6) for k, x in zip(PARAMETERS, cands[-1][1])}))
    # fresh-seed validation of the refined leaders + the raw stage-1 leader
    held = Experiment(INST, seeds=[6111005, 6111006])
    ranked = []
    for s, v in cands + [(0., top[0]['x'])]:
        m = held.evaluate(design(np.asarray(v)))
        ranked.append((score(m), v, m))
        print('holdout score=%.2f tir=%.1f tbr70=%.2f tbr54=%.2f min=%.1f' % (score(m), m['mean_tir'], m['max_trajectory_tbr70'], m['max_trajectory_tbr54'], m['minimum_glucose']))
    ranked.sort(key=lambda r: -r[0])
    best_v = ranked[0][1]
    tr = ex.evaluate(design(np.asarray(best_v)))
    print('chosen train tir=%.2f feas=%s' % (tr['mean_tir'], tr['feasible']))
    return best_v

if __name__ == '__main__' and not os.environ.get('STAGE2'):
    main()
elif __name__ == '__main__':
    v = stage2(int(os.environ.get('NSTART', 3)))
    d = design(np.asarray(v))
    save_design(d)
    print('SAVED', json.dumps(d))
    json.dump({'design': d, 'x': v}, open('/tmp/stage2.json', 'w'))
    print('cpu', round(time.process_time(), 2))

# ---------------- stage 3: multi-start polish + fresh-seed final selection ---------
def stage3():
    """Reuses the saved design as one start, polishes neighbours, and picks the
    finalist by fresh-seed TIR subject to feasibility with a nadir buffer."""
    ex = Experiment(INST)
    base = json.load(open('/work/output/design.json'))['parameters']
    x0 = np.array([base[k] for k in PARAMETERS])
    rng = np.random.default_rng(7)
    starts = [x0] + [to_v(np.clip(to_u(x0)+rng.normal(0, 0.45, 6), 0, 1)) for _ in range(3)]
    cands = sorted(((lambda s, u: (s, to_v(u)))(*refine(ex, x, sweeps=1, step=0.3)) for x in starts),
                   key=lambda c: -c[0])
    held = Experiment(INST, seeds=[6111010, 6111020])
    best = None
    for _, v in cands[:2] + [(0., x0)]:
        m = held.evaluate(design(v))
        key = (m['feasible'] and m['minimum_glucose'] > 65, m['mean_tir'])
        print('holdout tir=%.1f min=%.1f ok=%s' % (m['mean_tir'], m['minimum_glucose'], key[0]))
        if best is None or key > best[0]:
            best = (key, v)
    save_design(design(best[1]))
    return design(best[1])
