# GRI static formulation design (dev-03)

Initial placeholder: responsive mode with shared coefficients, amplitude scaled by native
TDI, glucose-filtered Hill response plus a constant leak, and a finite reservoir cap
(theta_L * TDI units) over the 3-day horizon.

Search plan: (1) characterise the three children's native parameters and initial states,
(2) evaluate candidate formulations with gri_bench.api.Experiment on the training seed and
held-out meal seeds for all three scenario variants, (3) maximise mean post-warmup TIR subject
to per-trajectory TBR70 <= 4%, TBR54 <= 1% and full-horizon minimum glucose >= 40 mg/dL
(with safety margin because the trusted verifier uses the native dopri5 integrator).

Simulation benchmark only; not a clinical recommendation.
