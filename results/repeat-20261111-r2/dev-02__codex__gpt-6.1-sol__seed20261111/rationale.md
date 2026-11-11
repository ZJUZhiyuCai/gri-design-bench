# Shared glucose-responsive formulation

The submitted design is responsive, with theta_a = 0.00036, relative_leak = 0.5124966150526034, EC50 = 95.0 mg/dL, Hill exponent = 24.0, filter time constant = 0.05 minutes, and theta_L = 4.0. All coefficients are shared across adolescent#001, adolescent#002, and adolescent#003. Only the specified native TDI scales release amplitude and reservoir load.

## Design reasoning

The minimum permitted relative leakage preserves the largest available fractional reduction of release at low glucose. A steep Hill response near 95 mg/dL reduces release when interstitial glucose falls. The shortest permitted filter avoids adding delay to the physiological insulin and interstitial-glucose delays. The amplitude was reduced substantially from the strongest training candidates after new meal scenarios revealed hypoglycemia. The final local selection required zero observed TBR70 and a full-horizon minimum of at least 73 mg/dL on six search-validation seeds.

The normalized release lies between approximately 0.000184499 and 0.000544499 TDI per minute. Even continuous maximum release over 4320 minutes uses less than 2.36 TDI, below the reservoir load of 4 TDI. Thus the design does not depend on reservoir depletion to prevent hypoglycemia. Every parameter is within the instance bounds. No individualized fitting, additional insulin, meal boluses, or custom controller is used.

## Reproducible search

Run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py` in the provided benchmark environment. The script contains the complete deterministic sequence: initial amplitude/threshold sweep, shape grid, fresh-seed rejection, a lower-amplitude robust grid, local margin selection, twelve-seed comparison, fine integration checks, one native solver comparison, and a final twenty-seed check. It logs candidates and metrics and checkpoints designs atomically with the public save_design API. The script uses the public physiology without modifying it. Screening uses one-minute RK4; final fine validation uses four RK4 substeps per minute.

The training seed was 6111002. Search validation used seeds 802101–802106. The three local finalists were compared on 913201–913212. The final chosen design was then checked on 1244001–1244020, without further parameter changes. All checks included all three patients and ordinary, missed-lunch, and large-dinner variants. Each trajectory starts from the same native initial state. Days 2–3 contribute to TIR/TBR, and the full three-day horizon contributes to minimum glucose.

## Observed validation

| Check | Trajectories | Mean TIR (%) | Maximum TBR70 (%) | Maximum TBR54 (%) | Full-horizon minimum (mg/dL) |
|---|---:|---:|---:|---:|---:|
| Training plus first 18 new seeds, quarter-minute RK4 | 171 | 76.8360 | 0.0000 | 0.0000 | 73.314906 |
| Final 20 new seeds, one-minute RK4 | 180 | 75.1470 | 0.0000 | 0.0000 | 73.324014 |

There were 351 checked trajectories in total, including 342 using nontraining meal seeds. All observed trajectories met the benchmark safety thresholds. The lowest-glucose trajectory in fine validation (adolescent#002, seed 913207, large_dinner) was also run with native simglucose dopri5. Native minimum glucose was 73.314905575 mg/dL versus 73.314905574 mg/dL with quarter-minute RK4; native TBR70 and TBR54 were both zero. Only this selected trajectory received native-solver validation locally.

These finite checks provide evidence of a safety margin; they do not establish safety on every possible fresh meal scenario. The trusted verifier independently simulates the submitted JSON. This formulation is for the simulation benchmark and is not a clinical recommendation.
