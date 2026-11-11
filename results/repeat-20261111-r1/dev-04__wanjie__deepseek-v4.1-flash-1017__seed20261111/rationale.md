# GRI static formulation — dev-04 (adult#004/005/006)

## Submitted design
`responsive`: theta_a = 1.55693e-4, relative_leak = 3.76241, ec50 = 389.663 mg/dL,
hill_n = 9.5428, tau = 4.1795 min, theta_L = 1.25 (top of the allowed load range).
All coefficients are shared by the three patients; per-patient rate is
theta_a x native TDI (U/min) and reservoir = theta_L x native TDI (U).

## What dominates this problem
1. **Insulin, not hypoglycaemia, is the binding scarcity.** With the load cap, the
   most insulin the formulation can ever deliver averages
   theta_L*TDI/4320 min = 1.25*TDI/3 days, i.e. only ~42 % of a typical full daily
   TDI over the three-day horizon. Any candidate therefore ends up glucose-limited:
   the probe runs show mean post-warmup glucose of 250-1000 mg/dL and nadirs of
   78-135 mg/dL even for aggressive shapes. Failures come from *running dry early*,
   not from overdosing.
2. **Constant delivery is hopeless.** theta_c = 2.9e-4 (i.e. exactly the maximum
   sustainable constant rate given theta_L = 1.25) gives only ~7 % mean TIR, and no
   constant rate can do better because it spreads the entire scarce reservoir over
   the whole horizon without ever suppressing a meal peak. Negligible pituitary/
   circadian term is available, so a *responsive* (glucose-dependent) shape is
   strictly better: it steers the reservoir toward excursions.
3. **theta_L should be saturated** (1.25). Every refined optimum pushed theta_L to
   its upper bound — more total insulin is always worth having here, and the
   reservoir cap makes the leak term self-limiting. Note the load consumes only
   ratio-scaled insulin, so it stays safe even where a patient's own sensitivity is
   high (nadir stayed > 78 mg/dL in every validation seed).

## Shape rationale
The optimum found is a *near-continuous high-leak* allocation with a steep Hill gate:
relative_leak = 3.76 >> 1 means the base (leak) term supplies a large share of the
dose, so effective mean rate ~ 1.56e-4*TDI*(3.76 + Hill) ~ (5.9-7.4)e-4*TDI U/min,
which drains the 1.25*TDI reservoir in roughly 1.5 days. That front-loading is
*intentional*: TIR is a time-in-range count and the post-warmup window is only
2880 min, so insulin delivered while glucose is descending through 180 mg/dL is
worth far more than the same insulin delivered after the reservoir is already
empty and glucose has diverged. The ec50 = 390 mg/dL / n = 9.5 gate reserves the
Hill term for large excursions (i.e. after day-1 warmup and after the day-2
50 %-larger dinner and the day-2 missed-lunch rebound), while the leak keeps a
steady background that prevents the between-meal climb. tau = 4.2 min keeps the
interstitial filter fast enough that the gate is not badly lagged relative to the
3-min release cadence, but still smooths the minute-scale sensor noise.

## Search procedure (search.py)
Seeded log-uniform random search (140 candidates, training seed 6111004, all three
variants) scored by mean TIR with hard-margin penalties for TBR70 > 4 %,
TBR54 > 1 %, nadir < 40; then coordinate pattern refinement in normalised
log-parameter space; then multi-start polish; then selection among finalists on
**fresh meal seeds** (6111005-6111007, 6111010, 6111020) so the choice is not
tuned to the training meals. Every reported candidate respects the instance
bounds via the public validator.

## Robustness / safety
Training seed: mean TIR 29.6 %, worst-trajectory TBR70 = 0 %, TBR54 = 0 %,
full-horizon nadir 80.8 mg/dL. Fresh-seed validation: mean TIR 26.2-26.5 %,
nadir 78-81 mg/dL, TBR70 = 0 % everywhere. Nadir margins are ~2x the 40 mg/dL
rule and TBR is identically zero, so the zero-score safety gates are not marginal
under meal-seed resampling. This is a simulation benchmark result, not a clinical
recommendation; no training-safety guarantees are assumed for held-out scenarios.
