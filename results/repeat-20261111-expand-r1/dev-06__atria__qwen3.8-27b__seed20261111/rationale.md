# GRI static formulation design rationale (dev-06)

## Objective
Maximize mean post-warmup TIR (70-180 mg/dL) on NEW meal scenarios for patients
child#004, child#005, child#006, subject to hard safety: TBR70 <= 4%, TBR54 <= 1%,
and no full-horizon minute below 40 mg/dL. Day 1 excluded from TIR/TBR but included
in minimum glucose.

## Design choice
Responsive mode: rate = theta_a * TDI * (relative_leak + Hill(filtered interstitial
glucose)), load = theta_L * TDI, finite reservoir.

Initial candidate (to be refined by search.py):
- theta_a = 0.0002 (moderate amplitude)
- relative_leak = 1.5 (baseline leak keeps reservoir from emptying)
- ec50 = 200 mg/dL, hill_n = 2.0 (saturating response above ~200)
- tau = 10 min (smooths interstitial glucose)
- theta_L = 1.0 (full TDI reservoir)

## Search
Grid over the 6 responsive parameters, then local refinement, scored by mean TIR
with hard safety penalties. All coefficients shared across the cohort.

## Status
Initial checkpoint; refined by search.py runs.
