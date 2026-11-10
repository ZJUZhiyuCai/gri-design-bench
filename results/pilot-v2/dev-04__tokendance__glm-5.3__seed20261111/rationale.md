# GRI dev-04 design rationale (adult#004, adult#005, adult#006)

## Constraint analysis
Basal need (u2ss*BW/6000*1440): #004 21.3, #005 28.3, #006 41.4 U/day, i.e.
64/85/124 U over 3 days. The finite reservoir caps total delivery at
theta_L*TDI <= 1.25*TDI = 42.3/85.4/76.7 U. Insulin is therefore a scarce
resource that must be *allocated in time*, not a full basal-replacement
therapy. Delivering a high baseline "leak" wastes reservoir during euglycemia
and starves the post-meal periods that dominate TIR, and risks draining the
reservoir before day 3.

## Shape choice (responsive)
rate = theta_a*TDI*(leak + sigmoid-hill(filtered interstitial G)).
- Small relative_leak (~0.5-0.7) with steep hill => quasi bang-bang: the
  controller spends almost nothing below EC50 and near-maximum above it, so
  reservoir use concentrates on hyperglycemic excursions where the marginal
  TIR value of insulin is highest, and filtered-G feedback makes the system
  self-regulate around EC50 (fire, G falls, throttle, G rises).
- EC50 ~ 200-260 mg/dL keeps steady euglycemic draw near zero (hypo-safe:
  min-glucose and TBR trips are disqualifying) while still catching meals
  through the exact 3-minute filter (tau a few minutes; subcutaneous ka
  delays dominate anyway).
- theta_a scaled so theta_a*TDI*(leak+1) is comparable to the average
  sustainable rate theta_L*TDI/4320; theta_L = 1.25 uses the full reservoir
  over the full horizon.

## Search
`search.py`: coordinate log-line search (3 sweeps x 6 parameters) on the
training seed/variants via `Experiment.evaluate` (fast RK4), scoring
mean_TIR minus margin-shaped penalties (TBR70>3, TBR54>0.8, min<45) so the
selected point keeps safety distance from the 4%/1%/40 trips. Top 8 unique
candidates re-scored on two fresh meal seeds (7717, 424243) x 3 variants;
final = 0.4*train + 0.6*validation score. This is a simulation benchmark
tuning exercise, not clinical guidance.
