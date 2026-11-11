# GRI static formulation design (dev-01) - initial placeholder

Target: maximize mean post-warmup TIR (plasma glucose in [70,180] mg/dL) for
adult#001..003 on 3-day native RandomScenario meals (variants: ordinary,
missed_lunch, large_dinner), subject to hard safety constraints
(TBR70 <= 4%, TBR54 <= 1%, full-horizon minimum glucose >= 40 mg/dL).

Design space (instance bounds):
- responsive: theta_a in [0, 0.007] (U/min per TDI), relative_leak in
  [0.5125, 5.5189], ec50_mg_dl in [59.26, 816.11], hill_n in [0.588, 24],
  tau_min in [0.05, 20], theta_L in [0.4, 4.0] (U per TDI over the horizon).
- constant: theta_c in [0, 0.007], theta_L in [0.4, 4.0].

Initial guess: responsive, moderate amplitude, Hill centred at 150 mg/dL,
finite material load theta_L = 2 (material is capped, so total delivered
insulin over the 3-day horizon is finite).

Search: local/derivative-free optimisation of the shared coefficients with
the public fast RK4 simulator (gri_bench.api.Experiment), scoring mean TIR
subject to feasibility on all patients x variants, with extra random meal
seeds used as held-out robustness checks. This file is a placeholder and is
updated as the search proceeds.
