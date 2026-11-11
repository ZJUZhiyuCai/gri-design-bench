# Shared responsive formulation

The submitted design uses theta_a = 0.0002465625, relative_leak = 1.5, EC50 = 60 mg/dL, Hill exponent = 12, filter time constant = 0.05 minutes, and load = 4 times native TDI. All coefficients are shared across the three known patients and satisfy the instance bounds.

The minimum permitted leak provides the largest available relative modulation of insulin delivery. The low response threshold supports glucose control through most of the target range while reducing delivery as glucose approaches the hypoglycemic range. The short filter time avoids adding response delay. The reservoir cannot exhaust in three days: even continuously saturated release uses at most 0.0002465625 × 2.5 × 4320 = 2.662875 times TDI, below the load of 4 times TDI.

## Search and selection

The reproducible search uses deterministic differential evolution over amplitude, EC50 and Hill exponent on five meal seeds, each with ordinary, missed-lunch and large-dinner variants for every patient. A subsequent boundary scan explores lower EC50 values on three of those seeds. Screening uses the public physiology with one-minute RK4 steps, followed by quarter-minute RK4 validation. The final comparison uses 32 additional meal seeds (288 patient/scenario trajectories). These additional seeds inform final selection and are not an untouched test set.

Among the final candidates, the selected formulation achieved 89.2596209491% mean post-warmup TIR, maximum trajectory TBR70 = 0%, maximum trajectory TBR54 = 0%, and minimum full-horizon glucose = 70.0158732682 mg/dL. Another candidate achieved 89.3464% TIR but had maximum TBR70 = 1.5625%; the final selection rule favors the stronger observed safety margin when mean TIR differs by at most 0.2 percentage points.

The native simglucose dopri5 integrator was also run for the selected formulation's trajectory with the lowest observed full-horizon glucose: adolescent#004, seed 81001, large dinner. It returned minimum glucose 70.0158732710 mg/dL, TBR70 = TBR54 = 0%, and TIR = 76.4583333%, agreeing closely with the fine RK4 simulation. Native integration was checked on this one trajectory only.

These results establish feasibility on the sampled scenarios, not guaranteed feasibility on unseen meals. In particular, the minimum is close to 70 mg/dL even though it remains substantially above the full-horizon disqualification threshold of 40 mg/dL. No claim is made about independent verifier outcomes or clinical suitability.

## Reproduction

Run `OPENBLAS_NUM_THREADS=1 PYTHONPATH=/opt python /work/output/search.py --stage all` in the benchmark environment. Individual stages are also available: `search`, `stress`, `boundary`, `final`, and `native`. Search and validation reports are retained alongside the required artifacts. Design and report checkpoints use atomic file replacement. No simulator source was modified.
