# Shared static GRI formulation

Selected responsive formulation:

| Parameter | Value |
|---|---:|
| theta_a | 0.000345 |
| relative_leak | 0.5124966150526034 |
| ec50_mg_dl | 145 |
| hill_n | 4 |
| tau_min | 2 |
| theta_L | 4 |

Every coefficient is shared by child#004, child#005, and child#006. The benchmark scales amplitude and reservoir by native TDI. There are no fitted individual coefficients, meal boluses, external insulin, or custom online controls. All values meet the instance bounds. The reservoir is finite; its generous allowed load avoids depletion late in the three-day simulation.

## Reasoning and selection

The cohort has different insulin requirements even after TDI scaling. Child#005 limited dose escalation through low glucose, while the other two children retained substantial hyperglycemia. Training TIR alone selected doses with inadequate safety margins on fresh meal scenarios.

Minimum allowed leak and maximum Hill exponent give stronger modulation between low and high glucose within the material envelope. A two-minute filter minimizes added response delay. Screening EC50 and amplitude together identified the region near EC50 145 mg/dL as a favorable cohort compromise. This is a bounded numerical search, not proof of a global optimum.

Search stages used one-minute RK4: a 117-point training grid, an eight-candidate frontier comparison over 11 fresh seeds and all patients/challenges, then additional dose/shape checks over 60 seeds for the limiting child. The final local amplitude refinement required worst sampled TBR70 <= 3%, TBR54 = 0%, and full-horizon minimum >= 68 mg/dL. The largest amplitude meeting these stricter selection margins was 0.000345. The next tested amplitude, 0.0003475, had worst sampled TBR70 3.02% and minimum 67.71 mg/dL.

## Measured checks

All TIR/TBR figures omit day one. Minimum glucose includes day one and uses minute-level minima.

| Scenario set and integration | Trajectories | Mean TIR (%) | Worst TBR70 (%) | Worst TBR54 (%) | Minimum glucose (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Training seed, all cohort/challenges; 0.25-minute RK4 | 9 | 61.5741 | 0 | 0 | 73.6018 |
| 60 search/stress seeds, all cohort/challenges; 0.25-minute RK4 | 540 | 58.4477 | 2.7083 | 0 | 68.1818 |
| 100 additional seeds excluded from selection, all cohort/challenges; 1-minute RK4 | 900 | 58.9716 | 3.2292 | 0 | 67.4984 |

The worst TBR70 trajectory from the 60-seed set (child#005, seed 1482495401, large dinner) was also simulated with native simglucose dopri5. Its TBR70 was 2.7083%, TBR54 0%, and minimum 68.18177 mg/dL, closely matching quarter-minute RK4. The worst independent trajectory (child#005, seed 1859077791, large dinner) was rechecked with quarter-minute RK4: TBR70 3.2292%, TBR54 0%, minimum 67.49878 mg/dL.

All sampled trajectories passed the benchmark gates. The 60-seed set helped select the dose and is not independent validation; the subsequent 100-seed set was evaluated only after fixing the final dose. Neither sampled set guarantees safety or performance on the verifier's unseen meal seeds. Native integration was checked on one limiting stress trajectory, not on every trajectory. This is a simulation benchmark formulation, not a clinical recommendation.

## Reproduction

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python /work/output/search.py` with the supplied instance and installed benchmark. The script contains the fixed search grids, deterministic seed generation, safety-margin selection, fine-integration checks, and atomic design checkpoints. It writes audit metrics alongside the submitted design. It never modifies simulator source. Native seeds and parameters are used exactly as specified by the instance.
