# Shared responsive GRI formulation

The submitted design uses the minimum permitted relative leak, a smooth Hill response, and the maximum permitted reservoir. The exact shared parameters are in design.json. The amplitude is scaled only by each child's supplied native TDI; no patient-specific fitted coefficient or meal bolus is used.

The final amplitude is 0.00032462740402 TDI/min, relative leak 0.512496615053, EC50 74.845159 mg/dL, Hill exponent 6.3927453, filter time constant 2.7536362 minutes, and load 4 TDI. The minimum leak provides the greatest allowed response contrast. The response remains high during hyperglycemia and falls as glucose decreases. Search jointly adjusted threshold, slope, amplitude, and filtering to balance meal coverage against delayed insulin action. A large reservoir avoids depletion during this three-day experiment. Even the theoretical maximum three-day release is only 2.12111 TDI, below the 4 TDI load.

## Search and reproducibility

Run `OPENBLAS_NUM_THREADS=1 python /work/output/search.py`, then the same script with `--refine`, then with `--finalize`. Fixed seeds, population sizes, iterations, and candidate selection rules are embedded in the code. The initial differential evolution explored 468 candidates on the public training scenarios. Twenty-two candidates were checked on five additional meal seeds. A 120-candidate refinement used three of those additional seeds. The final three candidates were compared on 20 further, reproducibly sampled meal seeds, each with all three variants and all three patients (180 trajectories per candidate). These final scenarios were independent of the optimization scenarios, but their results were used for the final candidate selection.

Search used the public RK4 physiology with one-minute steps. Final comparisons used its default four substeps per minute. Each evaluation starts from the native initial state. Time-in-range and time-below-range exclude day one, while the minimum includes the full horizon. Objectives penalized low minima and excess trajectory TBR; final eligibility additionally required minimum >=60 mg/dL and TBR70 <=1%, stricter than benchmark limits.

## Observed validation results

For the selected formulation over the 180 final comparison trajectories:

- Mean post-warmup TIR70–180: 81.1505%.
- Worst trajectory TBR70: 0.0000%.
- Worst trajectory TBR54: 0.0000%.
- Full-horizon minimum glucose: 70.4176 mg/dL.

On the original nine training trajectories, the selected formulation produced mean TIR 79.2477%, maximum TBR70 0.0000%, maximum TBR54 0.0000%, and minimum glucose 71.5695 mg/dL.

All reported results use the public fast integrator, not the trusted native dopri5 verifier. Numerical agreement and safety on new held-out meals are not guaranteed. The strict observed safety margin supports this choice but does not prove held-out safety or global optimality. Full scenario rows and exact comparison seeds are archived in final_validation.json. This formulation is solely for the stated simulation benchmark, not clinical use.
