# Shared glucose-responsive formulation

The final design uses one common parameter set for adult#001–003, with amplitude and reservoir scaled only by native TDI. The reservoir is set to the maximum permitted 4×TDI to avoid premature exhaustion. The low permitted leak limits glucose-independent delivery, while the Hill response increases delivery at higher glucose. Filtering is set to its minimum permitted time because additional delay compounds subcutaneous insulin action delay.

Search used a deterministic amplitude/EC50 sweep followed by response-steepness refinement, screening with RK4 at one-minute steps. Candidate ranking penalized any TBR70 above 1%, any TBR54, and minimum glucose below 60 mg/dL. The three highest-ranked training designs were compared on two separate fresh meal seeds (772031 and 924107), including ordinary, missed-lunch, and large-dinner variants for every patient. Selection used the fresh-seed ranking. This small sample does not guarantee safety on the verifier's unseen seeds.

The selected candidate was then checked with the public reference fast integrator at four RK4 substeps per minute on all three seeds (27 trajectories). Reported TIR/TBR omit day one; minimum glucose covers all three days. The independent verifier uses native dopri5, so these are numerical validation estimates, not verifier results.

Final parameters:
```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.00063,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 155.0,
    "hill_n": 3.0,
    "tau_min": 0.05,
    "theta_L": 4.0
  }
}
```

Validation aggregate:
```json
{
  "mean_tir": 70.9645061728395,
  "max_trajectory_tbr70": 0.0,
  "max_trajectory_tbr54": 0.0,
  "minimum_glucose": 72.9055401474828,
  "trajectories": 27,
  "feasible": true,
  "safe_tir": 70.9645061728395
}
```

Full per-trajectory evidence is in validation.json. Reproduce with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py coarse`, followed by `OPENBLAS_NUM_THREADS=1 python /work/output/search.py refine`. The additional JSON files are audit evidence; only design.json specifies the formulation. This is a simulation benchmark, not a clinical recommendation.

Additional stress validation used eight further fresh meal seeds [18, 19, 77, 13579, 24680, 98765, 202603, 202611] and all three variants and patients (72 trajectories), using four RK4 substeps per minute. Aggregate results:
```json
{
  "mean_tir": 65.55121527777777,
  "max_trajectory_tbr70": 0.0,
  "max_trajectory_tbr54": 0.0,
  "minimum_glucose": 71.36590456601547,
  "trajectories": 72,
  "feasible": true,
  "safe_tir": 65.55121527777777
}
```
These scenarios were checked after selection. They remain a finite sample and do not establish unseen-scenario or native-integrator safety. Reproduce this additional stage with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py stress`. Full rows are in stress_validation.json.

A final local amplitude/shape refinement compared seven candidates over the combined 11 available seeds (99 trajectories). Selection maximized TIR with penalties for any observed TBR70 and minimum glucose below 68 mg/dL. These seeds now serve as optimization data, not an unbiased test set. The final selected design was reevaluated at four RK4 substeps per minute; final metrics supersede earlier candidate metrics above:
```json
{
  "mean_tir": 68.93202861952862,
  "max_trajectory_tbr70": 0.0,
  "max_trajectory_tbr54": 0.0,
  "minimum_glucose": 70.07378946490608,
  "trajectories": 99,
  "feasible": true,
  "safe_tir": 68.93202861952862
}
```
Reproduce with the additional `polish` stage. The final per-trajectory outcomes and exact seeds are in final_validation.json. Safety on new meals and native dopri5 is not guaranteed.
