# Shared GRI formulation for dev-04

The submitted formulation is responsive, with theta_a = 0.0001843645900067221, relative_leak = 2.792767199907936, EC50 = 219.3869310384716 mg/dL, Hill exponent = 24, filter time = 5 minutes, and theta_L = 1.25. All coefficients are shared across adult#004, adult#005 and adult#006 and satisfy the instance bounds. The maximum permitted finite load is used. Release amplitude and reservoir scale only with native TDI.

The normalized baseline release is approximately 0.000515 TDI/min and the saturated rate approximately 0.000699 TDI/min. The steep response increases release during high glucose while limiting additional release at lower glucose. Reservoir exhaustion imposes a substantial efficacy limit: higher early rates can increase early time in range but leave prolonged later hyperglycemia. The search compared constant release and responsive shapes and selected a moderate rate with a substantial observed safety margin.

## Search and validation

`search.py` contains the complete deterministic search: 120 broad proposals with RNG seed 44204, four-seed validation of the top training candidates, 60 local proposals with RNG seed 44205, four-seed comparison of the top refined candidates, and ten additional independent seeds for the final candidate. Proposals failing the specified training margins were filtered; validation selection required zero observed TBR70 and full-horizon minimum at least 72 mg/dL. Initial search checkpoints are atomic, as is the final selection. No patient-specific fitted coefficients or external boluses are used.

All tests include ordinary meals, day-2 missed lunch, and day-2 larger dinner for all three patients. Metrics omit the first day for TIR/TBR and include the entire horizon for the glucose minimum.

| Scenario set | Trajectories | Mean TIR (%) | Worst TBR70 (%) | Worst TBR54 (%) | Minimum glucose (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Training seed 6111004 | 9 | 30.2083 | 0 | 0 | 90.3319 |
| Four selection seeds | 36 | 28.0613 | 0 | 0 | 89.1135 |
| Ten independent final-check seeds | 90 | 27.7315 | 0 | 0 | 87.6458 |

Selection seeds: 827531, 193749, 508213, 978041. Independent final-check seeds: 613501, 762947, 119083, 420173, 882761, 210359, 355901, 901277, 658219, 741031. These are public local experiments, not the verifier's hidden seeds. Training feasibility was not treated as held-out safety: some training-feasible candidates failed validation and were rejected. The results above use the supplied fast RK4 integrator. Fresh-seed results provide empirical support, not a guarantee of safety on every new scenario or proof of global optimality.


## Extended independent checks and native integration

Twenty further independent seeds, defined by `1000003 + 7919*i` for i=0,...,19, produced 180 trajectories with mean TIR 28.3345%, zero TBR70 and TBR54 in every trajectory, and full-horizon minimum 86.9268 mg/dL. Pooling these with the first ten final-check seeds gives **270 independent final-check trajectories, mean TIR 28.1335%, worst TBR70 = 0%, worst TBR54 = 0%, and minimum glucose 86.9268 mg/dL**. These 30 seeds were not used to adjust the final design.

Native simglucose dopri5 integration was also run for all three patients on ordinary meals with seed 420173. All three passed: mean TIR 20.1736%, worst TBR70 = 0%, worst TBR54 = 0%, and minimum glucose 87.6458 mg/dL. This three-trajectory subset has a different meal mix from the aggregate checks and is not an estimate of their aggregate TIR. For adult#005, the lowest-glucose patient on this native subset, the native minimum was 87.6458233016 versus fast-RK4 87.6458233592 mg/dL, and both returned TIR 24.375%. Native validation covers this stated subset; the trusted verifier evaluates its own fresh seeds independently.

The complete reproducible sequence, including these final assessments, is in `search.py`. It requires the provided `gri_bench` installation and instance. Run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`. Search results and supplementary metric files are retained for audit. Safety on unseen seeds remains empirical, despite the observed margins.
