# GRI static formulation -- design rationale (instance dev-03)

## Chosen design (responsive, shared across the cohort)
```json
{"mode":"responsive","parameters":{"theta_a":0.00017,"relative_leak":1.8208,
 "ec50_mg_dl":100.0,"hill_n":18.28731,"tau_min":9.83632,"theta_L":4.0}}
```

## Physiology facts that drove the search
* Initial states are the patients' own steady state at basal `u2ss` (basal 0.0048-0.0066 U/min;
  basal/TDI = 0.00030-0.00038), with initial plasma glucose 134-143 mg/dL.
* Sustained insulin even 30% above basal (constant `theta_c=0.0005`, ~1.3x basal) drove
  TBR70 to 40% and TBR54 to 21% (min 49 mg/dL). The model has no glucagon
  counter-regulation, so the *fasting/floor rate* is the binding safety constraint, not the
  meal response. `relative_leak` therefore carries most of the risk: the floor rate is
  `theta_a * relative_leak`, and the design keeps it at ~0.9x of the basal-equivalent.
* The modest Hill term (`ec50=100 mg/dL`, `hill_n=18.3`, `tau=9.8 min`) is a near-switch that
  adds insulin only once filtered interstitial glucose is clearly above the fasting set point;
  it raises the rate to roughly 2x basal postprandially without ever lowering it below the
  floor. `theta_L=4.0` (upper bound) keeps the finite reservoir non-binding so the shape,
  not the load budget, sets delivery; the design uses far less than the 4x TDI load.

## Search method (see search.py, all stages reproducible from this file)
1. `STAGE=probe`: patient baseline facts and per-evaluation cost (~0.08 s).
2. `STAGE=search`: 70 Latin-hypercube-style random responsive designs in a physiologically
   plausible box (theta_a 8e-5..4.5e-4, leak 0.51..4, ec50 90..450, n 1..20, tau 0.3..20,
   theta_L=4) scored by `mean_tir - 8*max(0,TBR70) - 30*TBR54 - 4*max(0,82-minG)`, followed by
   multi-start coordinate refinement of the top 5.
3. `STAGE=validate`: re-evaluated short-listed shapes on the training seed plus three fresh
   `RandomScenario` seeds (20250101, 424242, 777001) and all three variants.

## Why the final point
The single-seed optimum (theta_a 1.8e-4, leak 2.24, ec50 206, n 6.7, tau 16.7) scored 74.8%
TIR on the training seed but reached **8.0% TBR70** on fresh meal seeds -- a clear overfit that
would score zero. The retained design sacrifices ~1 point of seed-mean TIR relative to the best
tested shape while giving, across 12 evaluated trajectories: mean TIR ~79.6%, worst-trajectory
TIR ~62%, **max TBR70 = 0%, max TBR54 = 0%, minimum plasma glucose ~76.6 mg/dL** (full horizon,
including day 1). That leaves ~37 mg/dL of headroom above the 40 mg/dL hard floor and zero
observed time under 70 mg/dL, versus caps of 4% and 1%, which is the intended robustness margin
for unseen meal seeds. Near neighbours were monotone and safe (`theta_a` 1.6e-4..1.7e-4,
ec50 100-130, n 12-18 all gave TBR70 = 0 and min G 76-86), so the choice sits on a broad
safe plateau rather than a knife edge.

*This is a simulation benchmark result, not a clinical recommendation.*
