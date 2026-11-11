# Shared glucose-responsive formulation

The release curve uses the minimum permitted leak, Hill coefficient 4, and a two-minute filter. All coefficients are shared across the three known children; only native TDI scales amplitude and reservoir. The four-TDI reservoir avoids premature exhaustion.

A deterministic grid screened 110 candidates on the provided meal seed. Five distinct curve shapes were then tested, with amplitude reductions when needed, on the training seed and five additional meal seeds, each with all three meal variants. Screening required worst-trajectory TBR70 at most 1.5%, no TBR54, and full-horizon glucose at least 58 mg/dL. These margins are stricter than benchmark limits. Selection maximized mean TIR among candidates meeting these margins.

The selected design was checked again with quarter-minute RK4 on these 54 trajectories. Results: {"mean_tir": 57.45563271604939, "max_trajectory_tbr70": 1.1458333333333333, "max_trajectory_tbr54": 0.0, "minimum_glucose": 69.77989566323068, "trajectories": 54, "feasible": true, "safe_tir": 57.45563271604939}

These are numerical simulation results. New meal seeds and the native dopri5 verifier can differ; finite validation does not establish heldout safety. This is not a clinical recommendation. Reproduce with OPENBLAS_NUM_THREADS=1 PYTHONPATH=/opt python /work/output/search.py.

A separate one-minute RK4 check used 20 further seeds (91000–91019), all variants, for 180 additional trajectories: {"mean_tir": 57.06307870370371, "max_trajectory_tbr70": 2.5, "max_trajectory_tbr54": 0.0, "minimum_glucose": 68.8754466757951, "trajectories": 180, "feasible": true, "safe_tir": 57.06307870370371}. See holdout.py and additional_validation.json.
