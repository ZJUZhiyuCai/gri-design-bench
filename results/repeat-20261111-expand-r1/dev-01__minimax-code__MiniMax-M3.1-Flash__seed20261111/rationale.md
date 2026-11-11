# GRI static formulation — initial rationale

## Problem
Choose ONE shared static formulation (no per-patient coefficients, no online
controller) for the known cohort `adult#001..#003` that maximises the mean
post-warmup percentage of plasma glucose in [70, 180] mg/dL over NEW meal
scenarios (ordinary / missed lunch on day 2 / 50 % larger dinner on day 2).

Hard gates (any violation ⇒ score 0 for the whole design):
* per-trajectory TBR70 <= 4 %,
* per-trajectory TBR54 <= 1 %,
* minimum plasma glucose over the FULL 3-day horizon (day 1 included) >= 40 mg/dL.

## Formulation family
`mode = responsive`: insulin rate r(t) = A · [leak + Hill(G_filt; EC50, n)] with
A = theta_a · TDI (U/min), a first-order filter of the interstitial (CGM) signal
with time constant `tau_min`, mid-point flux evaluation every 3 minutes and a
finite reservoir of total load `theta_L · TDI` (U).
`mode = constant`: r(t) = theta_c · TDI (U/min) from the same finite reservoir.

## Initial design
theta_a = 2e-4, leak = 1.5, EC50 = 200, n = 2, tau = 10, theta_L = 1.0.
This is feasible but clearly under-insulinated (mean glucose ~350 mg/dL),
so it is only a starting checkpoint; the search script is being refined to
explore the amplitude/reservoir/shape space and to enforce the safety gates.
