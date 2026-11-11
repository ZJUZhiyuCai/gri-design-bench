# GRI static formulation design (dev-02)

## Objective
Maximize mean post-warmup TIR (70-180 mg/dL) across 3 known adolescent patients
on NEW meal seeds, with hard safety: TBR70 <= 4%, TBR54 <= 1%, min glucose >= 40 mg/dL.

## Approach
- Responsive mode: rate = theta_a * TDI * (relative_leak + Hill(filtered interstitial glucose)).
- Search: random sampling in log-space for scale parameters + local refinement,
  scored by mean TIR with hard safety penalties.
- Initial design is the documented example; refined by search.py.

## Current design
See design.json. (To be updated after search.)
