# GRI static formulation design (dev-06)

## Objective
Maximize mean post-warmup TIR (70-180 mg/dL) over 3 days on new meal seeds for
patients child#004, child#005, child#006, subject to hard safety constraints:
TBR70 <= 4%, TBR54 <= 1%, and no minute with glucose < 40 mg/dL.

## Design choice
Responsive mode: rate = theta_a * TDI * (relative_leak + Hill(filtered interstitial glucose)).
- theta_a sets overall insulin amplitude relative to native TDI.
- relative_leak provides a basal-like floor so insulin continues during lows.
- ec50/hill_n shape the glucose-dependent feedback; tau_min smooths the signal.
- theta_L scales the meal load from the same finite reservoir.

## Search
Coarse grid over the 6 responsive parameters (see search.py), scored by
mean TIR minus heavy penalties for constraint violations. Best design saved
to design.json via gri_bench.api.save_design.

## Status
Initial checkpoint; refined after local search.
