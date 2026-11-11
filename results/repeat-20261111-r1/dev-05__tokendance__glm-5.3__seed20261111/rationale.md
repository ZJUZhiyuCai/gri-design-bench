# GRI static formulation design — dev-05 (final)

## Chosen design (responsive, shared across cohort)
`theta_a=2.8e-4, relative_leak=1.5, ec50_mg_dl=104.0, hill_n=3.36, tau_min=0.42, theta_L=2.5`

## Why this structure works
- Per 3-min step the pump delivers `theta_a*TDI*(1.5 + sigmoid(n*(log(EC50)-log(mid))))` U/min,
  where `mid` is the midpoint of a first-order filter (tau) of interstitial glucose, capped by the
  finite reservoir `theta_L*TDI`.
- Reservoir identity: over 4320 min the average rate is <= theta_L/4320 = 2.31e-4*theta_L U/min per
  unit TDI. theta_L=2.5 gives an average budget of 5.8e-4 (about 0.83 TDI/day) — enough to cover
  basal plus meal excursions without running dry, but a hard ceiling that automatically prevents
  runaway cumulative delivery.
- The leak term (theta_a*leak = 4.2e-4 U/min/TDI ~ 0.60 TDI/day) is the fasting/basal floor;
  the Hill term adds up to theta_a more at high glucose (meal response up to ~0.84 TDI/day
  instantaneous).

## Search that produced it (see search.py)
1. Multiplicative coordinate descent (factors 1.7/1.3/1.12) from 3 starts over the six shared
   parameters, scored on the 3 known patients x 3 variants x {training seed, one held-out seed}
   with feasibility-aware penalties (TBR70>2%, TBR54>0.5%, min glucose<55 mg/dL). This drove
   tau to a small value (fast response on interstitial glucose) and EC50 to ~100 mg/dL,
   lifting mean TIR from 67.4% to ~87%.
2. Seed-stress knee refinement: the neighbouring step theta_a=3.0e-4 (EC50=97) looked good on the
   training seed but produced an 18.1% TBR70 excursion for adolescent#004/large_dinner on other
   seeds — the safety cliff is steep and seed-dependent. Comparing knee candidates over 9 meal
   seeds (27 trajectories), EC50=104 at theta_a=2.8e-4 keeps TIR within 0.5 points of the
   maximum while eliminating every sub-70 excursion.

## Robustness evidence (RK4 fast simulator, 9 fresh/training seeds x 3 variants x 3 patients)
- Mean TIR: 87.3% post-warmup; per-trajectory range ~77.5-100%.
- Worst-trajectory TBR70: 0.0% (limit 4%), TBR54: 0.0% (limit 1%).
- Minimum plasma glucose over the full horizon incl. warmup: 70.6 mg/dL (limit 40).
- Worst groups are adolescent#004/005 with large_dinner; adolescent#006 is ~95-100% TIR.
- Margins are wide enough to absorb RK4 (training) vs native dopri5 (verifier) numerical
  differences and fresh meal seeds: the hypo channels sit at 0% against 4%/1% gates.

## Safety notes
- Simulation benchmark only, not a clinical recommendation.
- No per-patient coefficients, no online controller, no external boluses; all six parameters are
  shared and inside instance bounds.
