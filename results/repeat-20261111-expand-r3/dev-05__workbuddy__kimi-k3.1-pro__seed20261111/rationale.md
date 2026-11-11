# Responsive GRI formulation

## Selected design

The design uses one shared responsive coefficient set for the entire cohort. The release rate is `theta_a * native_TDI * (relative_leak + Hill(filtered_glucose))`, with a four-TDI finite reservoir (`theta_L = 4`). The Hill midpoint is 122.32 mg/dL and its exponent is 2.47. A short 1.33-minute interstitial-glucose filter avoids adding substantial lag. The maximum reservoir was retained so that the formulation is not prematurely supply-limited during the three-day simulation.

## Search and safety screening

`search.py` records the deterministic Sobol/global sampling and local perturbation procedure. Coarse probes covered amplitude, Hill location, exponent, filtering, leak, and reservoir size. Unsafe candidates were penalized; only feasible candidates were eligible to become the saved design. I then compared the best training candidates on newly generated `RandomScenario` meals rather than assuming that training feasibility implies held-out feasibility.

The selected candidate had training mean TIR **84.16%**, maximum trajectory TBR70 **0%**, maximum trajectory TBR54 **0%**, and minimum glucose **70.80 mg/dL**. Across 14 additional validation seeds (all three patients and all three variants for each seed, 126 trajectories), its mean TIR was approximately **88.00%**; every trajectory had TBR70 = TBR54 = **0%**, and the lowest observed full-horizon glucose was **71.17 mg/dL**. A more aggressive nearby amplitude reached slightly higher TIR on some seeds but exceeded the 4% TBR70 limit on a fresh scenario and was rejected. A higher-leak candidate with 84.78% training TIR also failed fresh-seed TBR70 screening and was rejected.

These figures are diagnostics from the public fast RK4 implementation, not a guarantee for unseen meals. The zero-score safety constraints were therefore treated as constraints during selection, not merely as an average penalty. This is a simulation benchmark design, not a clinical recommendation.

## Native-integrator confirmation

I also ran the public trusted-style `native_trace`/`verify_design` path (simglucose dopri5) on the training seed and fresh seed 161803. Training native mean TIR was **84.1551%**, and fresh-seed mean TIR was **88.0787%**. Both runs were feasible: every trajectory had TBR70 = TBR54 = **0%**. Minimum glucose was **70.798 mg/dL** in training and **71.489 mg/dL** on the fresh seed. Thus the fast-integrator selection was not relying on an RK4/native discrepancy in these checks.
