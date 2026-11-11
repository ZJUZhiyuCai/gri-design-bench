# Shared GRI formulation

The submitted design uses one shared glucose responsive release law for child#001, child#002, and child#003. Parameters are theta_a=0.00041241787179004043, relative_leak=0.74751339155797325, EC50=219.39925888027622 mg/dL, Hill n=1.8078446058457818, filter tau=2 minutes, and theta_L=4. Amplitude and reservoir scale only with the supplied native TDI. No patient-specific fitted coefficients, meal boluses, or external insulin are used.

The moderate Hill slope and short filter delay balance glucose-dependent release with stable basal coverage. The largest permitted reservoir avoids premature exhaustion. All parameters satisfy the instance bounds. The minimum permitted leakage was considered, but allowing a higher leak and a smoother response improved the observed balance across patients.

Search used deterministic differential evolution with 180 candidate evaluations on the nine training trajectories, followed by validation of twelve candidates against six additional meal seeds. A further 32 candidates explored neighboring release curves and reduced amplitudes for a steeper alternative on three seeds. Four finalists were evaluated against twelve further seeds. Selection penalized TBR70 beyond 1% and minimum glucose below 60 mg/dL, stricter than the benchmark exclusion thresholds. Designs were checkpointed atomically. Selection involved validation data; none of these seeds are claimed to be the evaluator's heldout scenarios.

For the final selected formulation, aggregate public RK4 results across 19 distinct seeds, three patients, and all three variants (171 trajectories) are:

- Mean post-warmup TIR70–180: 75.16265%.
- Maximum trajectory TBR70: 0.00000%.
- Maximum trajectory TBR54: 0.00000%.
- Minimum full-horizon glucose, including day one: 70.22724 mg/dL.
- Feasible under public fast-simulator checks: True.

On the twelve later seeds alone, mean TIR was 74.92959% with zero TBR70 and TBR54 and a minimum of 70.22724 mg/dL. Full per-trajectory public metrics are retained in selected_metrics.json. Time-in-range and time-below-range omit day one; the minimum includes the entire three days.

Reproduction: run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py train`, then the same command with `validate`, `refine`, `finalcheck`, and `finish`, in that order. The deterministic seeds, candidate generation, objective penalties, and selection rules are in search.py. These stages may require more CPU than one remaining task budget because imports recur. The reference simulator was not modified.

All reported values use the public fast RK4 simulator with default four substeps per minute, and its three-minute TIR/TBR sampling. The independent verifier uses native dopri5 and fresh meal seeds. Training and validation safety do not establish heldout safety, and native integration can differ. This is a simulation benchmark design, not a clinical recommendation.
