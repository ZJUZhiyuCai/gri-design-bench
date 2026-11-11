# GRI static formulation design (dev-05)

## Objective
Maximize mean post-warmup TIR (70-180 mg/dL) on NEW meal seeds for the known
cohort (adolescent#004/005/006), subject to hard safety: TBR70 <= 4%,
TBR54 <= 1%, and no full-horizon minute with plasma glucose < 40 mg/dL.
Day 1 is warmup (excluded from TIR/TBR, included in minimum glucose).

## Formulation
Responsive GRI: rate = theta_a*TDI * (relative_leak + Hill(filtered ISF glucose))
U/min, with a finite reservoir of theta_L*TDI U over the 3-day horizon.
The Hill term adds insulin when interstitial glucose is high (post-meal) and
recedes to the leak floor when glucose is low, which is the natural
hyper/hypo-protective shape.

## Initial hypothesis
- theta_L = 4.0 (max reservoir): the GRI is the only insulin source, so the
  full material budget should be available.
- theta_a*relative_leak ~ basal (TDI/1440 U/min) so the leak floor covers basal.
- ec50 ~ 150 mg/dL, hill_n ~ 2, tau ~ 10 min: responsive boost above ~150.

## Search plan
Coarse grid over (theta_a, relative_leak, ec50, hill_n, tau) with theta_L=4,
then local refinement, using the fast RK4 API. Final design saved atomically.

(To be updated with results.)
