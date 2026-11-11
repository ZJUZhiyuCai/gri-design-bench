"""Reproducible discrete, multi-seed search for the dev-06 GRI formulation.

The saved design is the robust-objective winner.  The verifier never runs this
file; run from the supplied benchmark environment to reproduce the search.
"""
import json, os
from gri_bench.api import load_instance, Experiment

instance = load_instance()
experiment = Experiment(instance, seeds=[6111006,6111007,6111008,6111009])
leak = instance['bounds']['relative_leak'][0]

def design(a, ec50, tau=5.0):
    return {'mode':'responsive', 'parameters': {
        'theta_a':a, 'relative_leak':leak, 'ec50_mg_dl':ec50,
        'hill_n':4.0, 'tau_min':tau, 'theta_L':2.0}}

# Coarse screening established this local family.  This final grid is deliberately
# small enough to reproduce with the benchmark's fast RK4 implementation.
candidates = [design(a,c,t) for a,c,t in [
    (.00031,140,5),(.00032,140,5),(.00032,150,5),
    (.00033,150,5),(.00033,160,5),(.00034,160,5),
    (.00034,170,5),(.00032,140,2),(.00032,140,10)]]

ranked = []
for candidate in candidates:
    m = experiment.evaluate(candidate)
    # Zero-TBR54 and full-horizon minimum >=55 are held as explicit robustness
    # margins.  A 2% TBR70 cap is stricter than the benchmark's 4% cap.
    robust = m['safe_tir'] if (m['max_trajectory_tbr70'] <= 2.0 and
             m['max_trajectory_tbr54'] == 0.0 and
             m['minimum_glucose'] >= 55.0) else 0.0
    ranked.append((robust, m['mean_tir'], candidate, m))
    print(candidate, m)

winner = max(ranked, key=lambda r:(r[0],r[1]))[2]
path = '/work/output/design.json'
with open(path+'.tmp','w') as f: json.dump(winner,f)
os.replace(path+'.tmp',path)
print('winner:', winner)
