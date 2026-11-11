# GRI static-design rationale (instance dev-01)

## Model/constraint reading
Responsive rate: `rate = theta_a*TDI * (relative_leak + Hill(filtered plasma glucose; ec50, n))`
on a 3-min grid, with midpoint first-order filter (`tau`), and a **finite reservoir**
`theta_L*TDI` units total over the 3-day horizon. The Hill term *increases* with glucose
(low glucose -> response -> 0, leaving the constant leak as basal), so the design is a
rate-limited basal + glucose-triggered correction without boluses. The dominant physical
fact is the reservoir: with theta_L in [0.4, 4], at most ~1.33 x daily TDI can be infused
per day, so the leak/response split decides *when* insulin is spent. Spending it early
causes both day-1 hypoglycemia and late-horizon exhaustion (hyperglycemia).

## What the physiology says (diagnostics on the known cohort)
* Zero insulin: mean glucose 781 mg/dL, TIR 0% (initial plasma glucose 136.5).
* Constant `0.5 x TDI/day` (theta_c=3.47e-4): mean 266 mg/dL, TIR 6% - clearly under-dosed.
* Aggressive feedback (theta_a=1e-3, leak=0.51, ec50=200): TIR 68% but TBR70 37%, TBR54 18%
  and minimum glucose 43 mg/dL - infeasible.
So the usable window is narrow: enough total insulin to cover meals (~1 x TDI/day) while
keeping a reservoir margin and never over-delivering early.

## Search (see search.py, fully reproducible, seed 20261111)
1. **Coarse randomized search** (260 bounded candidates, log-uniform theta_a/leak/ec50/tau/theta_L)
   scored on the training seed, ordinary variant (3 trajectories). 136/260 were feasible.
2. **Multi-seed validation** of the 60 best distinct candidates on the true training scenario
   (seed 6111001, 3 variants) *and* three held-out meal seeds (111, 222, 333) x 3 variants.
   This step was decisive: the coarse leader (86.4% on one scenario) hit **14.5% TBR70** on a
   held-out seed, confirming strong seed overfit; it was rejected.
3. **Local multiplicative refinement** (45 iterations) around the validated leader on a
   two-seed set, then a final re-ranking of the finalists on train + 3 held-out seeds.
   Acceptance required *every* trajectory to satisfy TBR70 <= 3%, TBR54 <= 0.5%, min >= 48
   mg/dL - deliberately stricter than the 4% / 1% / 40 mg/dL grading thresholds, because the
   evaluation uses fresh meal seeds and a zero-tolerance safety gate.

## Selected design
```
{"mode":"responsive","parameters":{
  "theta_a":0.00026151457652741724, "relative_leak":1.9786844890348587,
  "ec50_mg_dl":125.07342795941831, "hill_n":4.343589201022472,
  "tau_min":0.7711808249252824, "theta_L":2.9329617871565086}}
```
Interpretation for a TDI of ~50-58 U: amplitude ~0.013-0.015 U/min, so the leak alone is a
steady ~37-44 U/day basal, and the Hill correction (EC50 ~125 mg/dL, sharp n~4.3) can roughly
double the rate as glucose rises, tapering toward the leak as glucose falls. A short tau
(~0.8 min) makes the filter essentially current interstitial glucose, so corrections track
meals quickly. theta_L ~2.93 keeps ~147-166 U in the reservoir - enough for basal plus meal
corrections over 3 days while retaining reserve (the chosen design never saturates it),
avoiding the "empty-tank" hyperglycemia that kills late-horizon TIR.

## Observed performance (training seed + held-out seeds 111/222/333, all 3 variants)
* Mean post-warmup TIR: **80.7%**
* Worst-trajectory TBR70: **0.0%** (threshold 4%)
* Worst-trajectory TBR54: **0.0%** (threshold 1%)
* Worst-case minimum glucose over all minutes incl. day 1: **70.4 mg/dL** (threshold 40)
Safety margins are large on all three gates, which matters because grading seeds are unseen.

## Caveats
This is a simulation benchmark, not clinical advice. The design is a single shared static
parameter set; no per-patient tuning, online control, or boluses. The material/shape envelope
(theta_a, leak, ec50, n, tau, theta_L) is a synthetic subrange of prior fitted shapes and was
not measured. Robustness was checked on four meal seeds and three challenge variants; residual
risk is that a fresh seed produces an unusually large early meal before the reservoir dynamics
settle, but the measured minimum glucose (70 mg/dL) leaves substantial headroom.
