# GRI static formulation design — dev-05 (initial draft)

Cohort: adolescent#004/005/006 (TDI 35.25 / 34.00 / 49.58 U/day).

Formulation: responsive rate `rate(t) = theta_a * TDI * (relative_leak + Hill(Gf))`,
Hill(Gf) = Gf^n/(Gf^n + EC50^n) acting on the first-order filtered interstitial
glucose Gf (tau = tau_min), flux applied at 3-min midpoints, reservoir capped at
theta_L * TDI. Baseline (leak) term guarantees a floor of delivery; the Hill term
adds meal-driven insulin. theta_L sized so a post-meal surge is not truncated by
the reservoir, while the low-glucose fold-back (Hill -> 0 as Gf -> 0) plus small
theta_a*TDI leak keeps TBR54/TBR70 and the min-glucose floor safe.

Initial parameter guess is refined by the grid+local search in search.py, which
scores candidate designs by mean post-warmup TIR on the 3 training variants with
hard penalties for TBR70 > 4%, TBR54 > 1%, or any minute < 40 mg/dL.

This is a simulation benchmark design, not a clinical recommendation.
