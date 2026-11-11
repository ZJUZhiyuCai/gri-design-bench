# Shared responsive formulation

The submitted coefficients are shared across adult#001, adult#002, and adult#003. Native TDI provides the only patient scaling. Parameters: {"theta_a": 0.00048, "relative_leak": 0.5124966150526034, "ec50_mg_dl": 70.0, "hill_n": 4.0, "tau_min": 0.05, "theta_L": 4.0}.

The search screened amplitude, EC50, and Hill exponent on the public training scenarios using one-minute RK4 steps, then compared candidates on three additional meal seeds. Four conservative candidates were compared on eight further seeds. The final selection maximizes mean TIR on those eight seeds among candidates with zero observed TBR70 and full-horizon minimum at least 71 mg/dL. This is a finite heuristic search, not a proof of optimality.

The leak is at its permitted minimum to preserve glucose-dependent dose reduction. A low EC50 and moderate Hill slope support sustained delivery while retaining some reduction near low glucose. The minimum filter time avoids added sensing delay. The reservoir load is 4 times native TDI. Even the theoretical maximum release over 4320 minutes is only 3.136313 times TDI, so the reservoir cannot exhaust during the horizon.

Final validation uses the standard four RK4 substeps per minute on all 12 tested seeds and all three variants: 108 patient/scenario trajectories. Training summary: {"mean_tir": 88.07870370370371, "max_trajectory_tbr70": 0.0, "max_trajectory_tbr54": 0.0, "minimum_glucose": 71.42452176557539, "trajectories": 9, "feasible": true, "safe_tir": 88.07870370370371}. Additional-seed summary (99 trajectories): {"mean_tir": 78.74684343434343, "max_trajectory_tbr70": 0.0, "max_trajectory_tbr54": 0.0, "minimum_glucose": 71.32563101399369, "trajectories": 99, "feasible": true, "safe_tir": 78.74684343434343}. Metrics omit day one for TIR/TBR, but retain its minute minima. Detailed per-trajectory evidence is in validation.json.

Fresh seeds used for selection are validation evidence, not sealed heldout safety guarantees. The hidden evaluator uses native dopri5, and arbitrary unseen meals may differ. This is solely a simulation benchmark design, not a clinical recommendation.

Reproduce the search by running search.py with stages coarse, refine, local, validate, fresh_search, final_search, stress, finish, in that order. Each stage appends history.jsonl; start in a clean output directory for a fresh run. finish atomically saves the selected design. The exact grid and seed lists are embedded in the code.

Native dopri5 check of the trajectory with the lowest RK4 full-horizon glucose: {"patient": "adult#001", "seed": 7320101, "variant": "large_dinner", "metrics": {"tir": 59.583333333333336, "tbr70": 0.0, "tbr54": 0.0, "minimum": 71.32563102593541, "mean_glucose": 159.6385678539161}}. This checks one trajectory, not the entire native ensemble. Reproduce with the native stage after finish.
