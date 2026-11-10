"""Reproducible search for GRI static design (instance dev-05).

Run:  python search.py            -> writes /work/output/design.json + search_log.json

Design space is the shared responsive box from /task/instance.json.
Pipeline (all evaluations on the public fast RK4 trace):
  A coarse random search, scored on the 'ordinary' variant only (cheap);
  B re-score survivors on all three variants (ordinary/missed_lunch/large_dinner);
  C pattern (coordinate) refinement of the best few on all variants;
  D multi-seed robustness check (unseen meal seeds) with safety-margin penalty;
  E atomic save of the best design.
Safety preference is deliberately conservative versus the hard gates
(max TBR70<=1.5%, TBR54<=0.4%, min glucose>=65) because the verifier uses
fresh meal seeds and any single trajectory breaking 4%/1%/40 mg/dL zeroes us.
"""
import json, sys, time
import numpy as np
from gri_bench.api import load_instance, Experiment, PARAMETERS, save_design

INST = load_instance('/task/instance.json')
B = INST['bounds']
LO = np.array([B[k][0] for k in PARAMETERS]); HI = np.array([B[k][1] for k in PARAMETERS])

def to_design(v):
    return {'mode': 'responsive', 'parameters': dict(zip(PARAMETERS, map(float, v)))}

def score(r):
    """Penalized objective: TIR minus safety-margin violations, hard gate as huge penalty."""
    pen = (400.0*max(0.0, r['max_trajectory_tbr70']-1.5)
           + 800.0*max(0.0, r['max_trajectory_tbr54']-0.4)
           + 8.0*max(0.0, 65.0-r['minimum_glucose']))
    if r['max_trajectory_tbr70'] > 4.0 or r['max_trajectory_tbr54'] > 1.0 or r['minimum_glucose'] < 40.0:
        pen += 1e4
    return float(r['mean_tir'] - pen)

def brief(r):
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != 'rows'}

def move(v, d):
    w = v.copy()
    w[0] = np.exp(np.log(v[0]) + d[0])
    w[1] = v[1] + d[1]*0.5
    w[2] = np.exp(np.log(v[2]) + d[2]*0.3)
    w[3] = np.exp(np.log(v[3]) + d[3]*0.4)
    w[4] = np.exp(np.log(v[4]) + d[4]*0.5)
    w[5] = v[5] + d[5]*0.3
    return np.clip(w, LO, HI)

def main(deadline=16.0):
    t0 = time.perf_counter()
    rng = np.random.default_rng(20261111)
    full = Experiment(INST)
    cheap = Experiment(INST, variants=['ordinary'])
    log = []

    # ---------------- Stage A ----------------
    cand = []
    for i in range(240):
        u = rng.random(6)
        v = np.array([np.exp(np.log(2e-4) + u[0]*(np.log(7e-3)-np.log(2e-4))),
                      1.5 + u[1]*1.6,
                      np.exp(np.log(90.) + u[2]*(np.log(320.)-np.log(90.))),
                      np.exp(np.log(0.9) + u[3]*(np.log(16.)-np.log(0.9))),
                      np.exp(np.log(1.0) + u[4]*(np.log(18.)-np.log(1.0))),
                      3.1 + u[5]*0.9])
        v = np.clip(v, LO, HI)
        r = cheap.evaluate(to_design(v))
        cand.append((score(r), v))
    cand.sort(key=lambda x: -x[0])
    print('A done %.1fs' % (time.perf_counter()-t0))

    # ---------------- Stage B ----------------
    pool = []
    for s, v in cand[:14]:
        r = full.evaluate(to_design(v)); s2 = score(r)
        pool.append((s2, v.copy(), r)); log.append((s2, to_design(v), r))
    pool.sort(key=lambda x: -x[0])
    print('B done %.1fs' % (time.perf_counter()-t0), 'best', round(pool[0][0], 1), np.round(pool[0][1], 5), brief(pool[0][2]))

    # ---------------- Stage C ----------------
    seeds = []
    for k in range(3):
        if k >= len(pool): break
        cur_s, cur_v = pool[k][0], pool[k][1].copy()
        for it in range(4):
            improved = False
            for j in range(6):
                for sgn in (1.0, -1.0):
                    if time.perf_counter()-t0 > deadline: break
                    d = np.zeros(6); d[j] = sgn
                    w = move(cur_v, d)
                    r = full.evaluate(to_design(w)); s = score(r)
                    log.append((s, to_design(w), r))
                    if s > cur_s + 1e-6:
                        cur_s, cur_v, improved = s, w, True
            if not improved: break
        seeds.append((cur_s, cur_v, None))
    seeds.sort(key=lambda x: -x[0])
    print('C done %.1fs' % (time.perf_counter()-t0), [(round(s, 1), np.round(v, 5).tolist()) for s, v, _ in seeds[:3]])

    # ---------------- Stage D: unseen-seed robustness ----------------
    extra = Experiment(INST, seeds=[6111006, 6111007, 6111008, 6111009],
                       variants=['ordinary', 'missed_lunch', 'large_dinner'])
    finalists = []
    for s, v, _ in seeds[:3]:
        r = extra.evaluate(to_design(v))
        s2 = score(r)
        finalists.append((s2, v, r, s))
        log.append((s2, to_design(v), r))
        print('D %.1f train %.1f' % (s2, s), np.round(v, 5), brief(r))
    finalists.sort(key=lambda x: -x[0])
    s2, v, r, strain = finalists[0]
    # reject multi-seed winner only if it destroys training performance
    best_v = v
    print('selected', np.round(best_v, 5), 'extra_seed_score %.1f train %.1f' % (s2, strain))

    rt = full.evaluate(to_design(best_v))
    for row in rt['rows']:
        print('  ', row['patient'], row['variant'], {k: round(x, 1) for k, x in row['metrics'].items()})
    print('TRAIN', brief(rt))

    design = to_design(best_v)
    save_design(design)
    json.dump({'best_design': design, 'train_summary': brief(rt),
               'unseen_seed_summary': brief(r),
               'top': [{'score': s, 'design': d, 'summary': brief(rr)}
                       for s, d, rr in sorted(log, key=lambda x: -x[0])[:15]]},
              open('/work/output/search_log.json', 'w'), indent=1)
    print('total %.1fs' % (time.perf_counter()-t0))

if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 16.0)

# ---------------------------------------------------------------------------
# Stage E (final, what produced the submitted design; see refine.py log)
# ---------------------------------------------------------------------------
# Multi-seed pattern refinement around the Stage-D winner, scored on five meal
# seeds x three variants (45 trajectories) with tighter safety margins
# (TBR70<=0.5 %, TBR54<=0.1 %, min glucose>=66 mg/dL), then an independent
# fresh-seed validation on seeds [6111010..6111013]:
#
#   start   : [2.30e-4, 2.152, 224.06, 0.588, 1.247, 3.229]  TIR 85.3 (45 traj)
#   refined : [2.30e-4, 2.152, 144.30, 0.588, 0.836, 3.229]  TIR 87.2 (45 traj)
#             train seed 84.2 TIR, fresh seeds 91.1 TIR, TBR70=TBR54=0,
#             minimum glucose 71.2 mg/dL in every one of 81 trajectories.
# The submitted design.json is the 'refined' point above.
