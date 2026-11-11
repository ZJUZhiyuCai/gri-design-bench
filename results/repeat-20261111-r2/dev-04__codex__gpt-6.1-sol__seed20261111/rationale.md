# GRI static formulation for dev-04

## Submitted design
Responsive release with a single shared formulation for adult#004, adult#005 and adult#006. Parameters are theta_a=0.0004, relative_leak=0.5124966150526034, EC50=65.0 mg/dL, Hill exponent=3.0, filter time=0.05 minutes, and load=1.25 times native TDI. All parameters satisfy the supplied bounds. Release amplitude and reservoir are scaled only by the prescribed native TDI.

## Search and rationale
The finite three-day reservoir is an active constraint. Larger amplitudes exhausted the reservoir earlier and some caused hypoglycemia. Higher activation thresholds reduced TIR in the tested cohort. A low EC50 with a moderate Hill exponent gave the strongest observed balance of TIR and hypoglycemia margin. Minimum allowed relative leak and maximum reservoir load were selected; the shortest filter avoids additional delay. The formulation remains a fixed material response with no meal boluses or individual fitted coefficients.

Search used the public RK4 physiology at two substeps per minute, an amplitude/threshold sweep, a broader deterministic grid and random search, constant-rate comparators, five-seed scenario evaluation, and a local refinement. Candidates were checkpointed atomically. Selection required extra safety margin beyond the benchmark limits. All three meal variants and all three patients were included. This was a bounded heuristic search, without a claim of global optimality.

## Final checks
Final checks used four RK4 substeps per minute, the API default precision, with day one omitted from TIR/TBR but included in the glucose minimum.

* Training: 9 trajectories; mean TIR 30.069444%; maximum trajectory TBR70 0.000000%; maximum TBR54 0.000000%; full-horizon minimum 87.477660 mg/dL.
* Additional seeds reserved until after parameter selection: 20 seeds, 180 trajectories; mean TIR 28.286458%; maximum trajectory TBR70 0.000000%; maximum TBR54 0.000000%; full-horizon minimum 87.388979 mg/dL.

The additional seed check passed the benchmark safety limits: True. These observations do not guarantee safety on unseen seeds or agreement with the trusted native dopri5 verifier. Native dopri5 verification was not run within the compute budget. This submission is for the simulation benchmark, not a clinical recommendation.

## Reproduction
From an environment containing the public gri_bench package, run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py STAGE` for stages `initial`, `search`, `refine`, `validate`, `local`, then `final` in that order. The deterministic random seeds and all scenario seeds are embedded in search.py. Stage metrics are retained as JSON files, including per-trajectory final measurements. Only design.json determines the submitted formulation.
