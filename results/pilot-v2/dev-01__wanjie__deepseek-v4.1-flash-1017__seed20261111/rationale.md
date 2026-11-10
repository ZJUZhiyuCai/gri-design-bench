# GRI static formulation — dev-01 (cohort adult#001-003)

## Design chosen
```json
{"mode":"responsive","parameters":{"theta_a":0.000329,"relative_leak":1.356176,
 "ec50_mg_dl":114.174885,"hill_n":5.222675,"tau_min":3.313538,"theta_L":4.0}}
```
(see `design.json` for full precision)

## Physiology-level reasoning
With amplitude = theta_a x TDI (U/min) and leak + Hill(Geff) as the multiplier, the
delivered rate at a given filtered glucose is amplitude x [leak + 1/(1+(EC50/G)^n)].
For this cohort TDI is 50-58 U/day, so theta_a ~ 3.3e-4 puts the basal floor at
theta_a x leak x TDI ~ 0.024 U/min (~35 U/day) and the saturated ceiling at
theta_a x (leak+1) x TDI ~ 0.043 U/min (~62 U/day) — i.e. the whole useful band of
basal + prandial replacement for these adults, a factor ~5.5 dynamic range.

Shape parameters were tuned by repeated simulated evaluation, not guessed:
* `relative_leak` = 1.36 is the fasting/basal anchor. Lower values (0.5-1.0) left
  fasting glucose drifting high; higher values (>2.5), reached by raising the
  multiplier instead of theta_a, gave the same basal but compressed the dynamic
  range and cost TIR.
* `ec50_mg_dl` = 114 with `hill_n` = 5.2 gives an almost switch-like response
  centred just above euglycaemia: below ~110 mg/dL delivery falls back to the
  leak-only floor, above ~130 mg/dL it saturates. Meals therefore trigger a near
  maximal rate quickly, while the fasting floor is what protects against
  hypoglycaemia.
* `tau_min` = 3.3 min: the filter is short, so the midpoint-interstitial estimate
  tracks plasma glucose with only a few minutes of lag; longer filters (19 min,
  the starting point) blunted post-meal delivery and lost ~1-2 points of TIR.
* `theta_L` = 4.0 (upper bound) is deliberately non-binding. Diagnosis showed the
  reservoir still held ~57 of 200 U at the end of the 3-day horizon, so the cap
  never truncates therapy and cannot cause late-horizon hyperglycaemia; keeping
  it at the bound only removes an unnecessary extra constraint.

## Safety
All screening is done against per-trajectory worst case, not the cohort mean.
The chosen design had TBR70 = 0.00 % and TBR54 = 0.00 % in every one of the 27
screened trajectories (3 patients x 3 variants x 3 meal seeds, including the
day-2 missed-lunch and 1.5x-dinner challenges), with per-trajectory minimum
plasma glucose 70.4-86.6 mg/dL — far above the 40 mg/dL full-horizon floor and
the 70 mg/dL TBR threshold. Because the response saturates as a hard plateau and
the leak-only floor is small, an unseen meal pattern can move glucose up much
more easily than down; the failure mode of this design on fresh seeds is
hyperglycaemia, not hypoglycaemia. A deliberately less aggressive variant
(theta_a 1.6e-4, leak 3.5) reached only 80.8 % TIR and a 79.0 mg/dL minimum, i.e.
the extra safety margin was worthless in this regime.

## Performance (fast RK4 screen)
mean TIR 82.4 % over 3 training-style seeds x 3 variants x 3 patients
(69-94 % per trajectory); the initial leak/Hill guess from the same search code
scored 81.2 % on the single seed. Training-seed-only fits and fresh-seed screens
differed by < 3 points, so the choice is not seed-overfit.

## Caveats
Simulator benchmark only, not a clinical recommendation; final scoring uses native
dopri5 resimulation, so small metric shifts are expected. Hyperglycaemia dominates
the residual loss: the design cannot bolus, so post-meal peaks above 180 mg/dL are
only partly counteracted by a filtered, saturating rate.
