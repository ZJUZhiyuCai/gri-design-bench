# GRI formulation for dev-03

Selected a single responsive formulation shared by child#001, child#002, and child#003:

- theta_a = 0.000398 per minute, scaled by native TDI
- relative_leak = 0.5124966150526034
- EC50 = 110 mg/dL
- Hill exponent = 2.5
- filter time constant = 0.05 minute
- reservoir load = 4 native TDI

All coefficients satisfy the instance bounds. The minimum permitted leak preserves the largest available glucose-dependent modulation relative to basal release. A moderate Hill exponent gives a smooth response, reducing delayed post-meal lows seen with steep response curves. The shortest permitted filter avoids additional sensing delay. The large reservoir avoids using exhaustion as a timing strategy. No individualized coefficients, boluses, or additional control inputs are used.

## Search and validation

`search.py` contains the deterministic search stages, candidate grids, scenario seeds, safety metrics, and atomic design checkpoints. Replay stages in order: initial, refine, robust, stress, broad, polish, validate. Each candidate starts from the native initial patient state. Search uses the public RK4 integrator at one-minute steps; final validation uses its standard four substeps per minute. The JSONL audit log records each completed evaluation. Reproduction requires the provided benchmark environment and sufficient compute beyond this task's search budget.

Initial amplitude and steepness sweeps exposed hypoglycemia in child#001. Training ordinary and missed-lunch trajectories happened to coincide, motivating fresh seeds. Broader comparison used eight initial seeds and twenty fresh seeds across all three challenge variants. Modest release reduction from a promising candidate with amplitude 0.0004 supplies additional safety margin.

For the submitted coefficients, standard-step validation on 20 seeds (the eight earlier seeds plus twelve additional independent seeds), all three patients and all three variants, yielded 180 trajectories:

| Metric | Result |
|---|---:|
| Mean post-warmup TIR 70–180 | 78.5052% |
| Maximum trajectory TBR70 | 1.6667% |
| Maximum trajectory TBR54 | 0% |
| Full-horizon minimum plasma glucose | 68.5147 mg/dL |

The minimum occurred for child#001, seed 2363590, large dinner. TIR and TBR omit day one; minima include all three days. These are sampled simulation results, not a guarantee of heldout safety or a clinical recommendation. The trusted verifier independently uses native dopri5.

Native dopri5 spot check of this lowest-glucose validation trajectory: {"tir": 68.75, "tbr70": 1.6666666666666667, "tbr54": 0.0, "minimum": 68.51473992874188, "mean_glucose": 152.79441912276403}. This checks one trajectory, not the entire validation cohort.

Exact submitted design on the twenty earlier fresh comparison seeds (180 trajectories, one-minute RK4): {"mean_tir": 79.0144675925926, "max_trajectory_tbr70": 1.7708333333333333, "max_trajectory_tbr54": 0.0, "minimum_glucose": 68.532725355565, "trajectories": 180, "feasible": true, "safe_tir": 79.0144675925926}.

Exact submitted design on the original training seed (nine trajectories, standard four-substep RK4): {"mean_tir": 75.65972222222223, "max_trajectory_tbr70": 0.0, "max_trajectory_tbr54": 0.0, "minimum_glucose": 71.30094150063415, "trajectories": 9, "feasible": true, "safe_tir": 75.65972222222223}.
