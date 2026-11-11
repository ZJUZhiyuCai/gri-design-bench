# GRI static formulation — instance dev-05 (adolescents #004/#005/#006)

## Chosen design (responsive)
theta_a = 2.78e-4, relative_leak = 1.8583, ec50 = 252.36 mg/dL, hill_n = 1.7556,
tau = 2.804 min, theta_L = 3.218.

Pooled performance (fast RK4 reference integrator, training seed 6111005 + 7 held-out
meal seeds, 3 patients x 3 variants each): mean TIR ~85%, TBR70 = 0.0% on every
trajectory, TBR54 = 0.0%, worst full-horizon plasma glucose ~74 mg/dL (hard floor is 40,
TBR70 limit 4%, TBR54 limit 1%). Held-out seeds used only for ranking/robustness
selection, never for fitting.

## What the physics of this formulation dictates
* Rate = theta_a * TDI * (relative_leak + Hill(G)) with Hill increasing in glucose, so
  the release band is only [theta_a*TDI*leak, theta_a*TDI*(leak+1)]. This is a narrow
  (<=1.67x) modulation, and no boluses exist, so the design is essentially a
  "basal + modest glucose-dependent top-up" scheme.
* The finite reservoir (theta_L * TDI units total, at most 4320 min of release) is the
  dominant constraint. If theta_a*(leak+1) is large the whole 3-day budget is emptied
  in a few hours: every over-aggressive candidate in the broad stage produced
  TBR54 ~ 50-100% and near-zero glucose. Safety therefore requires
  4320 * theta_a * (leak + ~0.5) <~ theta_L, i.e. a mean release of order
  theta_a*TDI*(leak+0.5) ~ 0.022 U/min for these TDIs.
* relative_leak was pushed to the lower part of its bound (1.86) to maximise the
  available Hill modulation span ((leak+1)/leak = 1.54) while still providing enough
  baseline insulin; the leaked baseline is what keeps glucose down between meals.
* ec50 ~ 250 mg/dL with a shallow Hill coefficient (n ~ 1.8) gives a smooth,
  saturation-tolerant response: below ~150 mg/dL the Hill term is near zero, so the
  formulation tapers toward pure basal as glucose falls — this is what protects
  against nocturnal/post-exercise lows. A steep Hill (n > 8) with low ec50 was the
  fastest way to hypoglycaemia in the search.
* tau ~ 2.8 min keeps the interstitial filter fast enough to track post-prandial
  excursions (the 3-min midpoint flux would otherwise lag meals badly) while still
  damping minute-scale noise.
* theta_L = 3.2 leaves headroom in the reservoir so insulin is still being released
  on day 3 (candidates with theta_L <= 2.0 ran dry and ended the horizon hyperglycaemic).

## Robustness/safety margins
Candidates were re-scored on 7 unseen meal seeds. The selected point was best/near-best
on pooled TIR and kept TBR70 = 0 and minimum glucose > 72 mg/dL on every seed, patient
and challenge variant (missed lunch, 50% larger dinner included). Margin to the 40 mg/dL
zero-scoring floor is >30 mg/dL and to the 4% TBR70 limit is the entire TBR budget.
Because the verifier re-integrates with native dopri5, the design deliberately sits in
the interior of the safe region rather than on the TIR-optimal edge (slightly more
aggressive variants reached ~86% TIR but with ~72 mg/dL minima and thinner margins).
This is a simulation benchmark result, not clinical guidance.

## Integrator cross-check
Re-running the chosen design with the native simglucose dopri5 path (`native_trace`) on
the limiting trajectory (adolescent#004, large_dinner, training seed) reproduces the
fast-integrator minimum plasma glucose (74.45 mg/dL) to <1e-6 mg/dL, so the safety
margins reported here should carry over to the trusted verifier. Across 36 trajectories
(3 patients x 3 variants x 4 meal seeds) the design scored mean TIR 85.3% with
TBR70 = 0.0%, TBR54 = 0.0% and minimum glucose 74.5 mg/dL.
