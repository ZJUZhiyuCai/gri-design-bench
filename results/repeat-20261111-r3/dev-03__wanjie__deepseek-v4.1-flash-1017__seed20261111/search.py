"""Reproducible search for the GRI static design (dev-03).

Strategy
--------
The three patients are children (BW 28-41 kg) whose native meals are scaled by
BW/86.07, i.e. meals are SMALL relative to their TDI.  The insulin requirement is
therefore dominated by basal delivery and the dose->glucose map is a steep cliff
(roughly 2x rate takes the cohort from hyperglycaemia to fatal hypoglycaemia).

So: (1) keep `relative_leak` non-trivial only as a floor and rely on the Hill
feedback for safety, (2) screen a large random design set on the cheap
single-variant evaluation, (3) re-score survivors on the full 3-variant cohort,
(4) validate the finalists against *fresh* meal seeds (evaluation uses unseen
seeds), and (5) prefer safety margin over raw TIR because ANY trajectory with
TBR70>4%, TBR54>1% or a minute <40 mg/dL zeroes the score.
"""
import json, sys, time, numpy as np
sys.path.insert(0, '/opt')
from gri_bench.api import load_instance, Experiment, save_design, validate_design

PARAM = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')
OUT = '/work/output/design.json'
inst = load_instance()
B = inst['bounds']
RNG = np.random.default_rng(20261111)

# ---- safe fallback so a good (feasible) design always exists on disk ----------
FALLBACK = {"mode": "responsive", "parameters": {"theta_a": 7e-05, "relative_leak": 5.4,
            "ec50_mg_dl": 140.0, "hill_n": 3.0, "tau_min": 12.0, "theta_L": 3.0}}
save_design(FALLBACK, OUT)

def mk(v):
    return {"mode": "responsive", "parameters": dict(zip(PARAM, map(float, v)))}

def score(m, tbr_cap=1.0, min_target=60.0, tbr54_cap=0.2):
    """Safety-first scalar objective: TIR minus margins violations."""
    return (m['mean_tir']
            - 4.0 * max(0.0, m['max_trajectory_tbr70'] - tbr_cap)
            - 1.0 * max(0.0, min_target - m['minimum_glucose'])
            - 100.0 * max(0.0, m['max_trajectory_tbr54'] - tbr54_cap)
            - 500.0 * (not m['feasible']))

def describe(tag, v, m):
    print(f"{tag:>22s} a={v[0]:.5f} leak={v[1]:.2f} ec50={v[2]:.0f} n={v[3]:.1f} "
          f"tau={v[4]:.2f} L={v[5]:.2f} | tir={m['mean_tir']:.1f} "
          f"tbr70={m['max_trajectory_tbr70']:.1f} tbr54={m['max_trajectory_tbr54']:.1f} "
          f"min={m['minimum_glucose']:.0f} feasible={m['feasible']}", flush=True)

t0 = time.time()
screen = Experiment(inst, seeds=inst['training_seeds'], variants=['ordinary'])   # 3 traj
full = Experiment(inst)                                                          # 9 traj

# ---------------- stage A: random screening ------------------------------------
def sample():
    return np.array([
        np.exp(RNG.uniform(np.log(1.5e-05), np.log(2.0e-03))),      # theta_a
        RNG.uniform(B['relative_leak'][0], B['relative_leak'][1]),  # relative_leak
        RNG.uniform(B['ec50_mg_dl'][0], 420.0),                     # ec50
        np.exp(RNG.uniform(np.log(B['hill_n'][0] + 0.1), np.log(B['hill_n'][1]))),
        np.exp(RNG.uniform(np.log(B['tau_min'][0]), np.log(B['tau_min'][1]))),
        RNG.uniform(2.0, B['theta_L'][1]),                          # theta_L
    ])

pool = []
# a small structured seed set (basal ~ constant, feedback off/on) plus random draws
structured = [
    [7e-05, 5.4, 140., 3., 12., 3.0],
    [3e-04, 1.5, 140., 3., 12., 3.0],
    [2.5e-04, 0.55, 160., 6., 5., 3.0],
    [4e-04, 0.55, 180., 8., 3., 3.2],
    [6e-04, 0.60, 200., 4., 8., 3.5],
    [1.2e-04, 0.80, 150., 12., 1.0, 3.0],
]
for v in structured + [sample() for _ in range(240)]:
    v = np.clip(v, [B[k][0] for k in PARAM], [B[k][1] for k in PARAM])
    m = screen.evaluate(mk(v))
    pool.append((score(m), v, m))
pool.sort(key=lambda r: -r[0])
print('--- stage A top 6 (ordinary only) ---')
for s, v, m in pool[:6]:
    describe('A', v, m)

# ---------------- stage B: full cohort/variant re-score ------------------------
seen, cand = set(), []
for s, v, m in pool:
    key = tuple(np.round(v, 9))
    if key in seen:
        continue
    seen.add(key)
    mf = full.evaluate(mk(v))
    cand.append((score(mf), v, mf))
    if len(cand) >= 22:
        break
cand.sort(key=lambda r: -r[0])
print('--- stage B top 6 (all 3 variants) ---')
for s, v, m in cand[:6]:
    describe('B', v, m)
save_design(mk(cand[0][1]), OUT)

# ---------------- stage C: local refinement around the leaders -----------------
leaders = [v for s, v, m in cand[:3]]
best = (cand[0][0], cand[0][1], cand[0][2])
scale = np.array([0.35, 0.20, 0.20, 0.30, 0.35, 0.10])
for v0 in leaders:
    for _ in range(26):
        v = np.exp(np.log(np.maximum(v0, 1e-9)) * np.exp(RNG.normal(0, 1, 6) * scale))
        v = np.clip(v, [B[k][0] for k in PARAM], [B[k][1] for k in PARAM])
        mf = full.evaluate(mk(v))
        sc = score(mf)
        if sc > best[0]:
            best = (sc, v, mf)
            save_design(mk(v), OUT)   # atomic checkpoint on every improvement
print('--- stage C best ---')
describe('C', best[1], best[2])

# ---------------- stage D: unseen-seed robustness -----------------------------
extra = Experiment(inst, seeds=[6111004, 6111005], variants=inst['variants'])  # 18 traj
finalists = [best[1]] + [v for s, v, m in cand[:4] if not np.allclose(v, best[1])]
tab = []
for v in finalists:
    tr = full.evaluate(mk(v)); te = extra.evaluate(mk(v))
    ok = tr['feasible'] and te['feasible']
    # robust score = worse of training/fresh-seed scores
    sc = min(score(tr), score(te))
    tab.append((sc, v, tr, te))
    print(f"D train tir={tr['mean_tir']:.1f} min={tr['minimum_glucose']:.0f} | "
          f"fresh tir={te['mean_tir']:.1f} tbr70={te['max_trajectory_tbr70']:.1f} "
          f"min={te['minimum_glucose']:.0f} ok={ok}", flush=True)
tab.sort(key=lambda r: -r[0])
sc, v, tr, te = tab[0]
print('--- chosen ---')
describe('FINAL(train)', v, tr)
describe('FINAL(fresh)', v, te)
save_design(mk(v), OUT)
print(json.dumps(json.load(open(OUT))))
print('cpu-ish elapsed', round(time.time() - t0, 2), 'evals', full.evaluations)
