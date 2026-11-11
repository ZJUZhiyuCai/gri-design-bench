# GRI static formulation — rationale (initial)

## Task
Maximize mean post-warmup TIR (plasma glucose in [70,180] mg/dL) for the known cohort
(child#004, child#005, child#006) under a hard safety gate: every patient/scenario must
satisfy TBR70 <= 4%, TBR54 <= 1%, and minimum glucose over the full 3-day horizon >= 40 mg/dL.

## Formulation family
Responsive (closed-loop) release: rate = theta_a * TDI * [relative_leak + Hill(filtered glucose)],
midpoint flux every 3 minutes, first-order glucose filter with time constant tau_min, and a
finite reservoir of theta_L * TDI units (mass-conserving cap).

## Initial guess
A responsive design with moderate amplitude, a basal leak around 1.5, EC50 near 140 mg/dL,
Hill exponent 2, 10-minute filter time constant and a large enough load (theta_L = 3) so the
reservoir does not run out over the 3-day horizon.

## Status
Search in progress: objective = mean TIR with hard safety veto, robustness checked on
additional RandomScenario seeds.
