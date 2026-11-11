# GRI static formulation design (dev-03)

## Objective
Maximize mean post-warmup TIR (70-180 mg/dL, days 2-3) on NEW meal seeds,
subject to hard safety: TBR70 <= 4%, TBR54 <= 1%, and no full-horizon minute
with plasma glucose < 40 mg/dL. Day 1 is warmup (excluded from TIR/TBR but
included in the minimum-glucose check).

## Model
Responsive GRI: rate = theta_a * TDI * [relative_leak + Hill(filtered
interstitial glucose)], Hill = (g/ec50)^n / (1 + (g/ec50)^n), first-order
filter time constant tau_min, midpoint flux every 3 min, single finite
reservoir of theta_L * TDI shared across all 3 days.

## Initial hypothesis
- Average insulin need ~ TDI/day => theta_a*(leak+resp) ~ TDI/1440/tdi.
- Reservoir must cover ~3 days of TDI => theta_L ~ 3-4.
- Glucose-responsive term should add insulin when glucose is high.

## Search
Random search over the responsive box (log-scale for scale params) + local
Nelder-Mead refinement on a safety-penalized TIR objective. See search.py.

(To be updated with final numbers.)
