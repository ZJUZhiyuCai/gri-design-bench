# Shared responsive formulation for dev-06

The submitted design uses theta_a = 0.00032, relative_leak = 0.5124966150526034, EC50 = 130 mg/dL, Hill exponent = 4, filter time constant = 2 minutes, and theta_L = 4. Every coefficient is shared by child#004, child#005, and child#006; amplitude and reservoir scale only with the instance's native TDI. No external insulin, meal boluses, patient-specific fitted coefficients, or custom controller are used.

## Design reasoning

Child#005 limits permissible insulin exposure. Initial higher-amplitude formulations produced prolonged hypoglycemia despite strong glucose control in the other two patients. Minimum permitted leakage and maximum Hill slope preserve more separation between low- and high-glucose release. EC50 and amplitude were jointly tuned to raise glucose responsiveness while limiting post-meal and overnight lows. The shortest allowed filter reduces additional feedback delay; a tested 20-minute filter increased hypoglycemia. Maximum reservoir avoids premature depletion: even the theoretical maximum rate over 4320 minutes consumes only 2.091 TDI, below the 4 TDI load. All submitted values satisfy the instance bounds.

## Search and reproducibility

`search.py` is self-contained and uses only the public API and physiology. Run with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`. It reproduces the initial amplitude sweep, EC50/amplitude grid, local refinement, screening on four additional seeds, broader testing on sixteen seeds, and selection among three nearby candidates on thirty-two further seeds. Coarse search uses RK4 with one-minute steps. Final validation uses the API default four RK4 substeps per minute. Checkpoints use atomic replacement through save_design. Search logs and numerical validation artifacts are retained alongside the submission.

Selection requires zero TBR54 and a margin below the TBR70 limit; the last comparison requires TBR70 <= 3% and full-horizon minimum >= 60 mg/dL. The final candidate outperformed the more conservative EC50=140, amplitude=0.00033 candidate in the final comparison. The nearby EC50=125 candidate had slightly lower TIR and higher worst-case TBR70. Seeds used here were chosen explicitly and are not claimed to be the verifier's seeds.

## Measured results

All runs cover three days. TIR and TBR exclude day one, while minimum glucose includes every minute of all three days. Each seed includes all three patients and all three scenario variants: ordinary, day-two missed lunch, and day-two enlarged dinner.

| Validation | Trajectories | Mean TIR (%) | Worst TBR70 (%) | Worst TBR54 (%) | Minimum (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Original training seed, quarter-minute RK4 | 9 | 62.141 | 0.0000 | 0 | 72.6726 |
| Seeds 6111006–6111054, quarter-minute RK4 | 441 | 58.580 | 2.8125 | 0 | 67.8382 |
| Further seeds 6111055–6111134, one-minute RK4 | 720 | 58.500 | 2.6042 | 0 | 68.3341 |

Across the 128 additional seeds, excluding the original training seed, mean TIR was 58.502% over 1152 trajectories, with every measured trajectory passing the stated safety criteria. These additional seeds were used for design assessment and are not a sealed holdout.

Native simglucose dopri5 was also run on the most limiting measured trajectory: child#005, seed 6111007, large dinner. Native TIR was 82.0833%, TBR70 was 2.8125%, TBR54 was zero, and minimum plasma glucose was 67.83817 mg/dL. The corresponding quarter-minute RK4 minimum was 67.83816 mg/dL, with identical TIR/TBR counts. This single native comparison supports numerical agreement on the limiting observed case; native checks were not run on every trajectory.

Fresh meal seeds can produce outcomes outside this observed envelope. Neither training feasibility nor these additional scenario tests guarantee safety on the verifier's undisclosed scenarios. The design prioritizes observed safety margin because any safety failure makes the benchmark score zero. This is a simulation benchmark formulation, not a clinical recommendation.
