# Design rationale (draft v1)

Static glucose-responsive insulin formulation for the known dev-04 cohort
(adult#004, adult#005, adult#006), shared coefficients, evaluated with the
public simglucose 0.2.11 physiology in gri_bench.

## Mechanism
Responsive release rate = theta_a * TDI * (relative_leak + Hill(filtered
interstitial glucose, ec50, hill_n)), first-order filter with tau_min,
midpoint flux every 3 minutes, capped by a finite reservoir of
theta_L * TDI units.

## Approach
1. Probe evaluation cost and no-insulin baseline.
2. Random + local search over the 6 shape parameters, objective = mean TIR
   over the 3 cached training scenarios, with a hard feasibility penalty on
   TBR70 > 4%, TBR54 > 1%, and any minute < 40 mg/dL.
3. Cross-check on extra RandomScenario seeds for robustness to new meals.
