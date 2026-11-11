# Shared responsive formulation

The submitted parameters are theta_a = 0.000257, relative_leak = 1.5, EC50 = 65 mg/dL, Hill exponent = 4, filter time constant = 0.05 min, and reservoir load theta_L = 4. All are within the instance bounds and identical across the three patients. Patient scaling uses only the benchmark's native TDI.

The response increases release at elevated glucose and reduces it near the low-glucose boundary. Minimum permitted leak provides the largest allowed modulation relative to basal release. A moderate Hill exponent performed more reliably than steep responses, which breached time-below-range limits on fresh meal scenarios. The short filter minimizes additional sensing delay. The maximum reservoir load avoids depletion over three days: even continuously saturated release consumes at most 0.000257 * 2.5 * 4320 = 2.7756 times TDI, below the 4 times TDI reservoir.

Search covered 144 combinations of amplitude, response threshold, and Hill exponent on the public training seed, followed by 20 candidate evaluations on six additional seeds and 24 local refinements on three seeds. The final three candidates were compared on 40 new deterministic seeds (7213001 through 7213040), each with all three patients and all three meal variants. Selection required worst-trajectory TBR70 <= 1%, TBR54 = 0%, and full-horizon minimum >= 65 mg/dL, tighter than the benchmark safety limits. All candidates use the same warmup and full-horizon safety definitions as the API.

The selected design achieved mean post-warmup time in [70,180] mg/dL of 89.6282% across these 360 final validation trajectories. Maximum trajectory TBR70 and TBR54 were both 0%; the lowest full-horizon minute glucose was 70.6514 mg/dL. These results use the public fast RK4 simulator. The lowest minimum occurred for adolescent#004, seed 7213031, large_dinner. The training-containing local-refinement set achieved 87.3071% mean TIR and a minimum of 70.6034 mg/dL for this design.

The new validation scenarios inform selection, so they are not an unbiased final held-out estimate. Fresh verifier scenarios can differ; finite validation does not guarantee held-out safety. The trusted verifier uses native dopri5 and may produce slightly different metrics. This formulation is a simulation benchmark submission, not a clinical recommendation.

`search.py` is self-contained and reproduces the grid, six-seed comparison, local refinement, and final 40-seed comparison in order. It atomically replaces design.json at checkpoints and saves detailed metrics. Run with PYTHONPATH=/opt. Its optional --native-check mode cross-checks the lowest-minimum final validation trajectory using the native solver. JSON metric files are supplementary audit records, not part of the submitted formulation.

Native dopri5 cross-check of the lowest-minimum final validation trajectory: {"tir": 85.83333333333333, "tbr70": 0.0, "tbr54": 0.0, "minimum": 70.65144096121516, "mean_glucose": 133.19780681921125}. This is one trajectory, not an exhaustive native validation.

Final selected-design confirmation across the original training seed plus the six earlier validation seeds (63 trajectories): {"mean_tir": 89.24603174603175, "max_trajectory_tbr70": 0.0, "max_trajectory_tbr54": 0.0, "minimum_glucose": 70.60335243176476, "trajectories": 63, "feasible": true, "safe_tir": 89.24603174603175}.
