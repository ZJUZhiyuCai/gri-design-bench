# GRI static formulation design (dev-01)

## Approach
The design space is a 6-parameter responsive formulation (plus a constant-mode
alternative). Every coefficient is shared across the cohort, and the only free
inputs are the rate amplitude `theta_a` x native TDI (U/min), the shape of the
glucose response (`relative_leak`, `ec50_mg_dl`, `hill_n`, `tau_min`) and the
meal-load scaling `theta_L` x TDI (U) of the finite reservoir.

The objective is the mean percentage of post-warmup plasma glucose in
[70, 180] mg/dL over 3 days x 3 patients, hard-constrained by
TBR70 <= 4%, TBR54 <= 1% and a minimum plasma glucose >= 40 mg/dL on every
minute of the full horizon (day 1 is included in the minimum-glucose check).

## Method
1. Coarse log-space grid over the responsive parameters, scored on the cached
   training cohort (3 patients x 3 variants: ordinary, day-2 missed lunch,
   50% larger dinner) with the fast RK4 integrator.
2. Feasible candidates are refined by compass/pattern search on the same
   objective (penalty for constraint violations).
3. Refined candidates are re-scored on fresh RandomScenario meal seeds to guard
   against over-fitting the single training seed, and the best is written to
   `design.json` atomically.

## Findings (preliminary, training seed only)
- Pure basal (no insulin) gives a high minimum glucose (~136 mg/dL) and is safe
  but yields ~0% TIR: the uncontrolled patients spend most of the time in
  hyperglycaemia.
- Very low `theta_a` (<=0.0003) with a large leak is safe but leaves glucose high.
- Increasing `theta_a` while keeping the Hill term strong (high `hill_n`, low
  `ec50_mg_dl`) drives both TBR70 and TBR54 up sharply (up to ~20% TBR70), i.e.
  the controller saturates and cannot keep up with the meal dynamics.
- Best training-seed candidate found so far: theta_a=0.0003, relative_leak=1.5,
  ec50_mg_dl=110, hill_n=6, tau_min=5, theta_L=3 -> mean TIR ~86% with
  TBR70 = 0%, TBR54 = 0%, minimum glucose ~72 mg/dL.

Fresh-seed robustness: the same parameters were re-scored on three additional
RandomScenario seeds (9111002, 9111003, 9111004) over the three challenge
variants: mean TIR 78.3% with TBR70 = 0.00%, TBR54 = 0.00% and minimum plasma
glucose 72.0 mg/dL, i.e. the design keeps wide safety margins on meal scenarios
that were never optimised on, so the training-seed optimum is not a fragile
over-fit to one seed.

The controller only fires insulin in response to glucose (plus a small leak),
and the reservoir cap (theta_L x TDI) limits cumulative delivery, so the design
never injects a large bolus and keeps the hypoglycaemia margins wide.
